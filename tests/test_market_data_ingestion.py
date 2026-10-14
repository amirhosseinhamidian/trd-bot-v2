from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyMarketDataEventStore,
    SqlAlchemyMarketDataIngestor,
)
from trd_bot.db.models import (
    MarketDataEventDecisionRow,
    MarketDataEventInboxRow,
    MarketDataEventRow,
    MarketDataOutboxRow,
    MarketDataRawObservationRow,
    MarketDataWatermarkRow,
    MarketDataWindowVersionRow,
)
from trd_bot.db.session import create_database_engine, create_session_factory
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    MarketDataEvent,
    MarketDataEventDisposition,
    MarketDataEventReason,
    MarketDataIngestionWatermarkMissingError,
    MarketDataRawObservation,
    MarketDataWatermark,
    VersionedMarketDataWatermark,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
WINDOW_START = datetime(2026, 10, 14, 8, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 14, 9, tzinfo=UTC)
FIRST_OBSERVED_AT = datetime(2026, 10, 14, 9, 0, 5, tzinfo=UTC)
FIRST_DECIDED_AT = datetime(2026, 10, 14, 9, 0, 6, tzinfo=UTC)


def create_event(
    *,
    close_price: str = "105",
    observed_at: datetime = FIRST_OBSERVED_AT,
) -> MarketDataEvent:
    return MarketDataEvent.from_candle(
        OHLCVCandle(
            source="kraken-public",
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=WINDOW_START,
            close_time=WINDOW_END,
            received_at=observed_at,
            open_price=Decimal("100"),
            high_price=Decimal("110"),
            low_price=Decimal("95"),
            close_price=Decimal(close_price),
            volume=Decimal("1250.5"),
            is_closed=True,
        )
    )


def create_observation(
    event: MarketDataEvent,
    *,
    created_at: datetime | None = None,
) -> MarketDataRawObservation:
    return MarketDataRawObservation.build(
        source=event.source,
        pair=event.pair,
        timeframe=event.timeframe,
        window_start=event.candle.open_time,
        window_end=event.candle.close_time,
        observed_at=event.observed_at,
        payload={
            "close": str(event.candle.close_price),
            "volume": str(event.candle.volume),
        },
        created_at=created_at or event.observed_at,
    )


def stage_watermark(
    factory: object,
    *,
    high_water_event_time: datetime,
) -> VersionedMarketDataWatermark:
    record = VersionedMarketDataWatermark.build(
        watermark=MarketDataWatermark.build(
            source="kraken-public",
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            high_water_event_time=high_water_event_time,
            allowed_lateness_seconds=0,
            calculated_at=FIRST_DECIDED_AT,
        ),
        version=1,
        policy_version="market-data-service-level-policy-v1",
        stored_at=FIRST_DECIDED_AT,
    )
    with factory.begin() as session:  # type: ignore[attr-defined]
        SqlAlchemyMarketDataEventStore(session).stage_watermark(record)
    return record


def table_count(session: object, row_type: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(row_type)))  # type: ignore[attr-defined]


def test_ingestion_commits_one_complete_accepted_unit_and_exact_retry_is_stable() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    watermark = stage_watermark(
        factory,
        high_water_event_time=datetime(2026, 10, 14, 8, 30, tzinfo=UTC),
    )
    event = create_event()
    observation = create_observation(event)

    try:
        with factory() as session:
            first = SqlAlchemyMarketDataIngestor(session).ingest(
                observation=observation,
                event=event,
                decided_at=FIRST_DECIDED_AT,
            )
        with factory() as session:
            retried = SqlAlchemyMarketDataIngestor(session).ingest(
                observation=observation,
                event=event,
                decided_at=datetime(2026, 10, 14, 9, 1, tzinfo=UTC),
            )

            assert first.created is True
            assert first.decision.disposition is MarketDataEventDisposition.ACCEPTED
            assert first.decision.reason is MarketDataEventReason.NEW_WINDOW
            assert first.watermark_id == watermark.watermark_id
            assert first.window_version == 1
            assert first.outbox_id is not None
            assert retried.model_copy(update={"created": True}) == first
            assert retried.created is False
            assert table_count(session, MarketDataRawObservationRow) == 1
            assert table_count(session, MarketDataEventRow) == 1
            assert table_count(session, MarketDataEventInboxRow) == 1
            assert table_count(session, MarketDataEventDecisionRow) == 1
            assert table_count(session, MarketDataWindowVersionRow) == 1
            assert table_count(session, MarketDataOutboxRow) == 1
    finally:
        engine.dispose()


def test_redelivery_records_evidence_without_repeating_window_or_outbox() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    stage_watermark(
        factory,
        high_water_event_time=datetime(2026, 10, 14, 8, 30, tzinfo=UTC),
    )
    first_event = create_event()
    second_event = create_event(
        observed_at=datetime(2026, 10, 14, 9, 2, tzinfo=UTC),
    )

    try:
        with factory() as session:
            SqlAlchemyMarketDataIngestor(session).ingest(
                observation=create_observation(first_event),
                event=first_event,
                decided_at=FIRST_DECIDED_AT,
            )
        with factory() as session:
            result = SqlAlchemyMarketDataIngestor(session).ingest(
                observation=create_observation(second_event),
                event=second_event,
                decided_at=datetime(2026, 10, 14, 9, 2, 1, tzinfo=UTC),
            )

            assert result.created is True
            assert result.inbox_delivery_count == 2
            assert result.decision.disposition is MarketDataEventDisposition.DUPLICATE
            assert result.decision.reason is MarketDataEventReason.DUPLICATE_PAYLOAD
            assert table_count(session, MarketDataRawObservationRow) == 2
            assert table_count(session, MarketDataEventRow) == 1
            assert table_count(session, MarketDataEventInboxRow) == 1
            assert table_count(session, MarketDataEventDecisionRow) == 2
            assert table_count(session, MarketDataWindowVersionRow) == 1
            assert table_count(session, MarketDataOutboxRow) == 1
    finally:
        engine.dispose()


def test_correction_creates_next_provisional_window_version() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    stage_watermark(
        factory,
        high_water_event_time=datetime(2026, 10, 14, 8, 30, tzinfo=UTC),
    )
    first_event = create_event()
    correction = create_event(
        close_price="106",
        observed_at=datetime(2026, 10, 14, 9, 3, tzinfo=UTC),
    )

    try:
        with factory() as session:
            SqlAlchemyMarketDataIngestor(session).ingest(
                observation=create_observation(first_event),
                event=first_event,
                decided_at=FIRST_DECIDED_AT,
            )
        with factory() as session:
            result = SqlAlchemyMarketDataIngestor(session).ingest(
                observation=create_observation(correction),
                event=correction,
                decided_at=datetime(2026, 10, 14, 9, 3, 1, tzinfo=UTC),
            )

            assert result.decision.disposition is MarketDataEventDisposition.ACCEPTED
            assert result.decision.reason is MarketDataEventReason.PROVISIONAL_UPDATE
            assert result.decision.existing_window_version == 1
            assert result.window_version == 2
            assert table_count(session, MarketDataWindowVersionRow) == 2
            assert table_count(session, MarketDataOutboxRow) == 2
    finally:
        engine.dispose()


def test_late_event_persists_replay_decision_without_window_or_outbox() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    stage_watermark(
        factory,
        high_water_event_time=datetime(2026, 10, 14, 10, tzinfo=UTC),
    )
    event = create_event()

    try:
        with factory() as session:
            result = SqlAlchemyMarketDataIngestor(session).ingest(
                observation=create_observation(event),
                event=event,
                decided_at=FIRST_DECIDED_AT,
            )

            assert result.decision.disposition is MarketDataEventDisposition.REVISION_REQUIRED
            assert result.decision.reason is MarketDataEventReason.LATE_ARRIVAL
            assert result.decision.requires_replay is True
            assert result.window_version is None
            assert result.outbox_id is None
            assert table_count(session, MarketDataRawObservationRow) == 1
            assert table_count(session, MarketDataEventRow) == 1
            assert table_count(session, MarketDataEventInboxRow) == 1
            assert table_count(session, MarketDataEventDecisionRow) == 1
            assert table_count(session, MarketDataWindowVersionRow) == 0
            assert table_count(session, MarketDataOutboxRow) == 0
    finally:
        engine.dispose()


def test_missing_watermark_and_downstream_failure_roll_back_the_whole_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    event = create_event()
    observation = create_observation(event)

    try:
        with factory() as session, pytest.raises(MarketDataIngestionWatermarkMissingError):
            SqlAlchemyMarketDataIngestor(session).ingest(
                observation=observation,
                event=event,
                decided_at=FIRST_DECIDED_AT,
            )

        stage_watermark(
            factory,
            high_water_event_time=datetime(2026, 10, 14, 8, 30, tzinfo=UTC),
        )

        def fail_outbox(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated downstream persistence failure")

        monkeypatch.setattr(
            SqlAlchemyMarketDataEventStore,
            "stage_outbox_message",
            fail_outbox,
        )
        with factory() as session, pytest.raises(RuntimeError, match="simulated downstream"):
            SqlAlchemyMarketDataIngestor(session).ingest(
                observation=observation,
                event=event,
                decided_at=FIRST_DECIDED_AT,
            )

        with factory() as session:
            assert table_count(session, MarketDataWatermarkRow) == 1
            assert table_count(session, MarketDataRawObservationRow) == 0
            assert table_count(session, MarketDataEventRow) == 0
            assert table_count(session, MarketDataEventInboxRow) == 0
            assert table_count(session, MarketDataEventDecisionRow) == 0
            assert table_count(session, MarketDataWindowVersionRow) == 0
            assert table_count(session, MarketDataOutboxRow) == 0
    finally:
        engine.dispose()
