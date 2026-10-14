from datetime import datetime

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from trd_bot.db.market_data_event_repositories import SqlAlchemyMarketDataEventStore
from trd_bot.market_data.events import (
    MarketDataEvent,
    MarketDataEventDecision,
    MarketDataEventDisposition,
    MarketDataEventReason,
    MarketDataWindowSnapshot,
    decide_market_data_event,
)
from trd_bot.market_data.ingestion import (
    MARKET_DATA_WINDOWING_TOPIC,
    MarketDataIngestionConflictError,
    MarketDataIngestionError,
    MarketDataIngestionResult,
    MarketDataIngestionWatermarkMissingError,
)
from trd_bot.market_data.storage import (
    MarketDataInboxReceipt,
    MarketDataOutboxMessage,
    MarketDataRawObservation,
    PersistedMarketDataEventDecision,
)


class SqlAlchemyMarketDataIngestor:
    """Commit one normalized provider observation as a single durable transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._store = SqlAlchemyMarketDataEventStore(session)

    def ingest(
        self,
        *,
        observation: MarketDataRawObservation,
        event: MarketDataEvent,
        decided_at: datetime,
    ) -> MarketDataIngestionResult:
        self._validate_lineage(observation=observation, event=event)

        for attempt in range(2):
            try:
                result = self._ingest_once(
                    observation=observation,
                    event=event,
                    decided_at=decided_at,
                )
                self._session.commit()
                return result
            except IntegrityError as error:
                self._session.rollback()
                if attempt == 0:
                    continue
                recovered = self._load_existing_result(
                    observation=observation,
                    event=event,
                )
                if recovered is not None:
                    return recovered
                raise MarketDataIngestionConflictError(
                    "concurrent market-data ingestion could not be resolved"
                ) from error
            except SQLAlchemyError as error:
                self._session.rollback()
                raise MarketDataIngestionError(
                    "market-data ingestion transaction failed"
                ) from error
            except Exception:
                self._session.rollback()
                raise

        raise AssertionError("market-data ingestion retry loop did not return")

    def _ingest_once(
        self,
        *,
        observation: MarketDataRawObservation,
        event: MarketDataEvent,
        decided_at: datetime,
    ) -> MarketDataIngestionResult:
        existing_result = self._load_existing_result(
            observation=observation,
            event=event,
        )
        if existing_result is not None:
            return existing_result

        self._store.stage_raw_observation(observation)
        watermark_record = self._store.get_latest_watermark(
            source=event.source,
            pair=event.pair,
            timeframe=event.timeframe,
            for_update=True,
        )
        if watermark_record is None:
            raise MarketDataIngestionWatermarkMissingError(
                "market-data stream has no persisted watermark"
            )

        existing_window = self._store.get_latest_window(
            event.window_id,
            for_update=True,
        )
        existing_receipt = self._store.get_inbox_receipt(
            event.idempotency_key,
            for_update=True,
        )

        if existing_receipt is not None:
            receipt = self._store.record_inbox_redelivery(event)
            decision = MarketDataEventDecision(
                event_id=event.event_id,
                window_id=event.window_id,
                arrival=watermark_record.watermark.classify(event),
                disposition=MarketDataEventDisposition.DUPLICATE,
                reason=MarketDataEventReason.DUPLICATE_PAYLOAD,
                existing_window_version=(
                    None if existing_window is None else existing_window.version
                ),
                decided_at=decided_at,
            )
            record = PersistedMarketDataEventDecision.build(
                observation_id=observation.observation_id,
                watermark_id=watermark_record.watermark_id,
                decision=decision,
            )
            self._store.stage_decision(record)
            return self._build_result(
                record=record,
                event=event,
                inbox_delivery_count=receipt.delivery_count,
                created=True,
            )

        self._store.stage_event(
            event,
            raw_observation_id=observation.observation_id,
            persisted_at=decided_at,
        )
        receipt = MarketDataInboxReceipt.from_event(event)
        self._store.stage_inbox_receipt(receipt)

        decision = decide_market_data_event(
            event,
            watermark=watermark_record.watermark,
            existing_window=existing_window,
            decided_at=decided_at,
        )
        record = PersistedMarketDataEventDecision.build(
            observation_id=observation.observation_id,
            watermark_id=watermark_record.watermark_id,
            decision=decision,
        )
        self._store.stage_decision(record)

        if decision.disposition is MarketDataEventDisposition.ACCEPTED:
            if decision.proposed_window_version is None:
                raise AssertionError("accepted decision is missing a proposed window version")
            window = MarketDataWindowSnapshot.from_event(
                event,
                version=decision.proposed_window_version,
                created_at=decided_at,
            )
            self._store.stage_window_version(window)
            self._store.stage_outbox_message(
                MarketDataOutboxMessage.from_event(
                    event,
                    topic=MARKET_DATA_WINDOWING_TOPIC,
                    created_at=decided_at,
                )
            )

        return self._build_result(
            record=record,
            event=event,
            inbox_delivery_count=receipt.delivery_count,
            created=True,
        )

    def _load_existing_result(
        self,
        *,
        observation: MarketDataRawObservation,
        event: MarketDataEvent,
    ) -> MarketDataIngestionResult | None:
        record = self._store.get_decision_by_observation(observation.observation_id)
        if record is None:
            return None
        if record.decision.event_id != event.event_id:
            raise MarketDataIngestionConflictError(
                "raw observation is already bound to a different market-data event"
            )

        receipt = self._store.get_inbox_receipt(event.idempotency_key)
        if receipt is None:
            raise MarketDataIngestionConflictError(
                "persisted ingestion decision is missing its inbox identity"
            )
        return self._build_result(
            record=record,
            event=event,
            inbox_delivery_count=receipt.delivery_count,
            created=False,
        )

    @staticmethod
    def _build_result(
        *,
        record: PersistedMarketDataEventDecision,
        event: MarketDataEvent,
        inbox_delivery_count: int,
        created: bool,
    ) -> MarketDataIngestionResult:
        accepted = record.decision.disposition is MarketDataEventDisposition.ACCEPTED
        return MarketDataIngestionResult(
            observation_id=record.observation_id,
            event_id=record.decision.event_id,
            decision_id=record.decision_id,
            watermark_id=record.watermark_id,
            decision=record.decision,
            inbox_delivery_count=inbox_delivery_count,
            window_version=(record.decision.proposed_window_version if accepted else None),
            outbox_id=(
                MarketDataOutboxMessage.build_outbox_id(
                    event_id=event.event_id,
                    topic=MARKET_DATA_WINDOWING_TOPIC,
                    payload_version=event.schema_version,
                )
                if accepted
                else None
            ),
            created=created,
        )

    @staticmethod
    def _validate_lineage(
        *,
        observation: MarketDataRawObservation,
        event: MarketDataEvent,
    ) -> None:
        if observation.source != event.source:
            raise ValueError("raw observation source does not match normalized event")
        if observation.pair != event.pair or observation.timeframe is not event.timeframe:
            raise ValueError("raw observation stream does not match normalized event")
        if (
            observation.window_start != event.candle.open_time
            or observation.window_end != event.candle.close_time
        ):
            raise ValueError("raw observation window does not match normalized event")
        if observation.observed_at != event.observed_at:
            raise ValueError("raw observation receipt time does not match normalized event")
