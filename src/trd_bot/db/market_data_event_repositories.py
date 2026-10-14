from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from trd_bot.db.models import (
    MarketDataEventDecisionRow,
    MarketDataEventInboxRow,
    MarketDataEventRow,
    MarketDataOutboxRow,
    MarketDataRawObservationRow,
    MarketDataWatermarkRow,
    MarketDataWindowVersionRow,
)
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data.events import (
    MarketDataEvent,
    MarketDataWindowSnapshot,
    MarketDataWindowState,
)
from trd_bot.market_data.storage import (
    MarketDataInboxReceipt,
    MarketDataOutboxMessage,
    MarketDataRawObservation,
    PersistedMarketDataEvent,
    PersistedMarketDataEventDecision,
    VersionedMarketDataWatermark,
)


class SqlAlchemyMarketDataEventStore:
    """Stage and query immutable market-data stream records.

    Stage methods deliberately do not commit. P2-02 can therefore combine raw
    observation, event, inbox, window, and outbox writes in one transaction.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def stage_raw_observation(
        self,
        observation: MarketDataRawObservation,
    ) -> tuple[MarketDataRawObservation, bool]:
        existing = self.get_raw_observation(observation.observation_id)
        if existing is not None:
            if existing != observation:
                raise ValueError("raw observation ID already exists with different content")
            return existing, False

        self._session.add(
            MarketDataRawObservationRow(
                observation_id=observation.observation_id,
                schema_version=observation.schema_version,
                source=observation.source,
                base_asset=observation.pair.base_asset,
                quote_asset=observation.pair.quote_asset,
                market_type=observation.pair.market_type.value,
                timeframe=observation.timeframe.value,
                window_start=observation.window_start,
                window_end=observation.window_end,
                observed_at=observation.observed_at,
                payload_checksum=observation.payload_checksum,
                payload_json=observation.model_dump_json(),
                created_at=observation.created_at,
            )
        )
        self._session.flush()
        return observation, True

    def get_raw_observation(self, observation_id: str) -> MarketDataRawObservation | None:
        row = self._session.get(MarketDataRawObservationRow, observation_id)
        if row is None:
            return None
        return MarketDataRawObservation.model_validate_json(row.payload_json)

    def stage_event(
        self,
        event: MarketDataEvent,
        *,
        raw_observation_id: str,
        persisted_at: datetime,
    ) -> tuple[PersistedMarketDataEvent, bool]:
        record = PersistedMarketDataEvent(
            event=event,
            raw_observation_id=raw_observation_id,
            persisted_at=persisted_at,
        )
        existing = self.get_event(event.event_id)
        if existing is not None:
            if existing != record:
                raise ValueError("market-data event ID already exists with different content")
            return existing, False

        existing_identity = self._session.scalar(
            select(MarketDataEventRow).where(
                MarketDataEventRow.idempotency_key == event.idempotency_key
            )
        )
        if existing_identity is not None:
            raise ValueError("market-data event idempotency key already belongs to another event")

        self._session.add(
            MarketDataEventRow(
                event_id=event.event_id,
                raw_observation_id=raw_observation_id,
                schema_version=event.schema_version,
                kind=event.kind.value,
                source=event.source,
                base_asset=event.pair.base_asset,
                quote_asset=event.pair.quote_asset,
                market_type=event.pair.market_type.value,
                timeframe=event.timeframe.value,
                event_time=event.event_time,
                observed_at=event.observed_at,
                window_id=event.window_id,
                payload_version=event.payload_version,
                payload_checksum=event.payload_checksum,
                idempotency_key=event.idempotency_key,
                payload_json=record.model_dump_json(),
                persisted_at=record.persisted_at,
            )
        )
        self._session.flush()
        return record, True

    def get_event(self, event_id: str) -> PersistedMarketDataEvent | None:
        row = self._session.get(MarketDataEventRow, event_id)
        if row is None:
            return None
        return PersistedMarketDataEvent.model_validate_json(row.payload_json)

    def get_event_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> PersistedMarketDataEvent | None:
        row = self._session.scalar(
            select(MarketDataEventRow).where(MarketDataEventRow.idempotency_key == idempotency_key)
        )
        if row is None:
            return None
        return PersistedMarketDataEvent.model_validate_json(row.payload_json)

    def stage_inbox_receipt(
        self,
        receipt: MarketDataInboxReceipt,
    ) -> tuple[MarketDataInboxReceipt, bool]:
        existing = self.get_inbox_receipt(receipt.idempotency_key)
        if existing is not None:
            if existing != receipt:
                raise ValueError("inbox identity already exists with different content")
            return existing, False

        self._session.add(
            MarketDataEventInboxRow(
                idempotency_key=receipt.idempotency_key,
                schema_version=receipt.schema_version,
                event_id=receipt.event_id,
                payload_checksum=receipt.payload_checksum,
                first_seen_at=receipt.first_seen_at,
                last_seen_at=receipt.last_seen_at,
                delivery_count=receipt.delivery_count,
                payload_json=receipt.model_dump_json(),
            )
        )
        self._session.flush()
        return receipt, True

    def get_inbox_receipt(
        self,
        idempotency_key: str,
        *,
        for_update: bool = False,
    ) -> MarketDataInboxReceipt | None:
        statement = select(MarketDataEventInboxRow).where(
            MarketDataEventInboxRow.idempotency_key == idempotency_key
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.scalar(statement)
        if row is None:
            return None
        return MarketDataInboxReceipt.model_validate_json(row.payload_json)

    def record_inbox_redelivery(self, event: MarketDataEvent) -> MarketDataInboxReceipt:
        row = self._session.scalar(
            select(MarketDataEventInboxRow)
            .where(MarketDataEventInboxRow.idempotency_key == event.idempotency_key)
            .with_for_update()
        )
        if row is None:
            raise ValueError("market-data inbox receipt does not exist")

        existing = MarketDataInboxReceipt.model_validate_json(row.payload_json)
        if (
            existing.event_id != event.event_id
            or existing.payload_checksum != event.payload_checksum
        ):
            raise ValueError("market-data redelivery does not match its inbox identity")

        updated = existing.record_redelivery(observed_at=event.observed_at)
        row.last_seen_at = updated.last_seen_at
        row.delivery_count = updated.delivery_count
        row.payload_json = updated.model_dump_json()
        self._session.flush()
        return updated

    def stage_decision(
        self,
        record: PersistedMarketDataEventDecision,
    ) -> tuple[PersistedMarketDataEventDecision, bool]:
        existing = self.get_decision(record.decision_id)
        if existing is not None:
            if existing != record:
                raise ValueError("market-data decision ID already exists with different content")
            return existing, False

        decision = record.decision
        self._session.add(
            MarketDataEventDecisionRow(
                decision_id=record.decision_id,
                observation_id=record.observation_id,
                event_id=decision.event_id,
                watermark_id=record.watermark_id,
                schema_version=decision.schema_version,
                window_id=decision.window_id,
                arrival=decision.arrival.value,
                disposition=decision.disposition.value,
                reason=decision.reason.value,
                existing_window_version=decision.existing_window_version,
                proposed_window_version=decision.proposed_window_version,
                requires_replay=decision.requires_replay,
                decided_at=decision.decided_at,
                payload_json=record.model_dump_json(),
            )
        )
        self._session.flush()
        return record, True

    def get_decision(self, decision_id: str) -> PersistedMarketDataEventDecision | None:
        row = self._session.get(MarketDataEventDecisionRow, decision_id)
        if row is None:
            return None
        return PersistedMarketDataEventDecision.model_validate_json(row.payload_json)

    def get_decision_by_observation(
        self,
        observation_id: str,
    ) -> PersistedMarketDataEventDecision | None:
        row = self._session.scalar(
            select(MarketDataEventDecisionRow).where(
                MarketDataEventDecisionRow.observation_id == observation_id
            )
        )
        if row is None:
            return None
        return PersistedMarketDataEventDecision.model_validate_json(row.payload_json)

    def stage_outbox_message(
        self,
        message: MarketDataOutboxMessage,
    ) -> tuple[MarketDataOutboxMessage, bool]:
        existing = self.get_outbox_message(message.outbox_id)
        if existing is not None:
            if existing != message:
                raise ValueError("outbox ID already exists with different content")
            return existing, False

        self._session.add(
            MarketDataOutboxRow(
                outbox_id=message.outbox_id,
                event_id=message.event_id,
                schema_version=message.schema_version,
                topic=message.topic,
                payload_version=message.payload_version,
                payload_json=message.model_dump_json(),
                status=message.status.value,
                attempt_count=message.attempt_count,
                created_at=message.created_at,
                available_at=message.available_at,
                updated_at=message.updated_at,
                delivered_at=message.delivered_at,
                error_code=message.error_code,
                error_message=message.error_message,
            )
        )
        self._session.flush()
        return message, True

    def get_outbox_message(self, outbox_id: str) -> MarketDataOutboxMessage | None:
        row = self._session.get(MarketDataOutboxRow, outbox_id)
        if row is None:
            return None
        return MarketDataOutboxMessage.model_validate_json(row.payload_json)

    def stage_window_version(
        self,
        snapshot: MarketDataWindowSnapshot,
    ) -> tuple[MarketDataWindowSnapshot, bool]:
        existing = self.get_window_version(snapshot.window_id, snapshot.version)
        if existing is not None:
            if existing != snapshot:
                raise ValueError("window version already exists with different content")
            return existing, False

        self._session.add(
            MarketDataWindowVersionRow(
                window_id=snapshot.window_id,
                version=snapshot.version,
                schema_version=snapshot.schema_version,
                state=snapshot.state.value,
                source=snapshot.source,
                base_asset=snapshot.pair.base_asset,
                quote_asset=snapshot.pair.quote_asset,
                market_type=snapshot.pair.market_type.value,
                timeframe=snapshot.timeframe.value,
                window_start=snapshot.window_start,
                window_end=snapshot.window_end,
                event_id=snapshot.event_id,
                payload_checksum=snapshot.payload_checksum,
                payload_json=snapshot.model_dump_json(),
                created_at=snapshot.created_at,
                finalized_at=snapshot.finalized_at,
            )
        )
        self._session.flush()
        return snapshot, True

    def get_window_version(
        self,
        window_id: str,
        version: int,
    ) -> MarketDataWindowSnapshot | None:
        row = self._session.get(MarketDataWindowVersionRow, (window_id, version))
        if row is None:
            return None
        return MarketDataWindowSnapshot.model_validate_json(row.payload_json)

    def get_latest_window(
        self,
        window_id: str,
        *,
        for_update: bool = False,
    ) -> MarketDataWindowSnapshot | None:
        statement = (
            select(MarketDataWindowVersionRow)
            .where(MarketDataWindowVersionRow.window_id == window_id)
            .order_by(MarketDataWindowVersionRow.version.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.scalar(statement)
        if row is None:
            return None
        return MarketDataWindowSnapshot.model_validate_json(row.payload_json)

    def list_finalization_candidate_ids(
        self,
        *,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        watermark_time: datetime,
        limit: int,
    ) -> tuple[str, ...]:
        if limit <= 0 or limit > 500:
            raise ValueError("window finalization limit must be between 1 and 500")
        stream_filters = (
            MarketDataWindowVersionRow.source == source,
            MarketDataWindowVersionRow.base_asset == pair.base_asset,
            MarketDataWindowVersionRow.quote_asset == pair.quote_asset,
            MarketDataWindowVersionRow.market_type == pair.market_type.value,
            MarketDataWindowVersionRow.timeframe == timeframe.value,
        )
        latest_versions = (
            select(
                MarketDataWindowVersionRow.window_id.label("window_id"),
                func.max(MarketDataWindowVersionRow.version).label("version"),
            )
            .where(*stream_filters)
            .group_by(MarketDataWindowVersionRow.window_id)
            .subquery()
        )
        rows = self._session.scalars(
            select(MarketDataWindowVersionRow.window_id)
            .join(
                latest_versions,
                and_(
                    MarketDataWindowVersionRow.window_id == latest_versions.c.window_id,
                    MarketDataWindowVersionRow.version == latest_versions.c.version,
                ),
            )
            .where(
                *stream_filters,
                MarketDataWindowVersionRow.state == MarketDataWindowState.PROVISIONAL.value,
                MarketDataWindowVersionRow.window_end <= watermark_time,
            )
            .order_by(
                MarketDataWindowVersionRow.window_end,
                MarketDataWindowVersionRow.window_id,
            )
            .limit(limit)
        ).all()
        return tuple(rows)

    def stage_watermark(
        self,
        record: VersionedMarketDataWatermark,
    ) -> tuple[VersionedMarketDataWatermark, bool]:
        existing = self.get_watermark(record.watermark_id)
        if existing is not None:
            if existing != record:
                raise ValueError("watermark ID already exists with different content")
            return existing, False

        stream = record.watermark
        existing_version = self._session.scalar(
            select(MarketDataWatermarkRow).where(
                MarketDataWatermarkRow.source == stream.source,
                MarketDataWatermarkRow.base_asset == stream.pair.base_asset,
                MarketDataWatermarkRow.quote_asset == stream.pair.quote_asset,
                MarketDataWatermarkRow.market_type == stream.pair.market_type.value,
                MarketDataWatermarkRow.timeframe == stream.timeframe.value,
                MarketDataWatermarkRow.version == record.version,
            )
        )
        if existing_version is not None:
            raise ValueError("watermark stream version already exists with different content")

        self._session.add(
            MarketDataWatermarkRow(
                watermark_id=record.watermark_id,
                schema_version=stream.schema_version,
                policy_version=record.policy_version,
                source=stream.source,
                base_asset=stream.pair.base_asset,
                quote_asset=stream.pair.quote_asset,
                market_type=stream.pair.market_type.value,
                timeframe=stream.timeframe.value,
                version=record.version,
                high_water_event_time=stream.high_water_event_time,
                allowed_lateness_seconds=stream.allowed_lateness_seconds,
                watermark_time=stream.watermark_time,
                calculated_at=stream.calculated_at,
                stored_at=record.stored_at,
                payload_json=record.model_dump_json(),
            )
        )
        self._session.flush()
        return record, True

    def get_watermark(self, watermark_id: str) -> VersionedMarketDataWatermark | None:
        row = self._session.get(MarketDataWatermarkRow, watermark_id)
        if row is None:
            return None
        return VersionedMarketDataWatermark.model_validate_json(row.payload_json)

    def get_latest_watermark(
        self,
        *,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        for_update: bool = False,
    ) -> VersionedMarketDataWatermark | None:
        statement = (
            select(MarketDataWatermarkRow)
            .where(
                MarketDataWatermarkRow.source == source,
                MarketDataWatermarkRow.base_asset == pair.base_asset,
                MarketDataWatermarkRow.quote_asset == pair.quote_asset,
                MarketDataWatermarkRow.market_type == pair.market_type.value,
                MarketDataWatermarkRow.timeframe == timeframe.value,
            )
            .order_by(MarketDataWatermarkRow.version.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.scalar(statement)
        if row is None:
            return None
        return VersionedMarketDataWatermark.model_validate_json(row.payload_json)
