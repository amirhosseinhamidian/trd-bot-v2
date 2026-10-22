from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trd_bot.db import (
    DatabaseBase,
    MarketDataWindowFinalizationWatermarkMissingError,
    SqlAlchemyMarketDataEventStore,
    SqlAlchemyMarketDataWindowFinalizationRepository,
    SqlAlchemyMarketDataWindowFinalizer,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.models import (
    MarketDataWindowFinalizationRow,
    MarketDataWindowVersionRow,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    MarketDataEvent,
    MarketDataFinalizationFreshnessOutcome,
    MarketDataWatermark,
    MarketDataWindowSnapshot,
    MarketDataWindowState,
    VersionedMarketDataWatermark,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"
FINALIZED_AT = datetime(2026, 10, 14, 12, 8, tzinfo=UTC)


def build_window(
    *,
    source: str,
    start: datetime,
    is_closed: bool = True,
) -> MarketDataWindowSnapshot:
    candle = OHLCVCandle(
        source=source,
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=start,
        close_time=start + timedelta(hours=1),
        received_at=start + timedelta(hours=1, seconds=30),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1250"),
        is_closed=is_closed,
    )
    event = MarketDataEvent.from_candle(candle)
    return MarketDataWindowSnapshot.from_event(
        event,
        version=1,
        created_at=candle.received_at,
    )


def build_watermark(
    *,
    source: str,
    high_water_event_time: datetime,
) -> VersionedMarketDataWatermark:
    watermark = MarketDataWatermark.build(
        source=source,
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        high_water_event_time=high_water_event_time,
        allowed_lateness_seconds=300,
        calculated_at=high_water_event_time + timedelta(seconds=1),
    )
    return VersionedMarketDataWatermark.build(
        watermark=watermark,
        version=1,
        policy_version="market-data-service-level-policy-v1",
        stored_at=watermark.calculated_at,
    )


def test_finalizer_creates_immutable_versions_and_freshness_evidence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    first = build_window(
        source=SOURCE,
        start=datetime(2026, 10, 14, 10, tzinfo=UTC),
    )
    second = build_window(
        source=SOURCE,
        start=datetime(2026, 10, 14, 11, tzinfo=UTC),
    )
    future = build_window(
        source=SOURCE,
        start=datetime(2026, 10, 14, 12, tzinfo=UTC),
    )
    watermark = build_watermark(
        source=SOURCE,
        high_water_event_time=datetime(2026, 10, 14, 12, 5, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            store.stage_watermark(watermark)
            for snapshot in (first, second, future):
                store.stage_window_version(snapshot)

        with factory() as session:
            evidence = SqlAlchemyMarketDataWindowFinalizer(session).finalize_eligible(
                source=SOURCE,
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                finalized_at=FINALIZED_AT,
            )

        assert [item.window_id for item in evidence] == [first.window_id, second.window_id]
        assert [item.freshness_outcome for item in evidence] == [
            MarketDataFinalizationFreshnessOutcome.MISSED_TARGET,
            MarketDataFinalizationFreshnessOutcome.WITHIN_TARGET,
        ]
        assert evidence[0].freshness_seconds == Decimal("4080.0")
        assert evidence[1].freshness_seconds == Decimal("480.0")
        assert all(item.watermark_id == watermark.watermark_id for item in evidence)

        with factory() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            for provisional in (first, second):
                latest = store.get_latest_window(provisional.window_id)
                assert latest is not None
                assert latest.version == 2
                assert latest.state is MarketDataWindowState.FINALIZED
                assert latest.event_id == provisional.event_id
                assert latest.payload_checksum == provisional.payload_checksum
            untouched = store.get_latest_window(future.window_id)
            assert untouched is not None
            assert untouched.state is MarketDataWindowState.PROVISIONAL
            assert session.scalar(select(func.count()).select_from(MarketDataWindowVersionRow)) == 5
            assert (
                session.scalar(select(func.count()).select_from(MarketDataWindowFinalizationRow))
                == 2
            )

        with factory() as session:
            repeated = SqlAlchemyMarketDataWindowFinalizer(session).finalize_eligible(
                source=SOURCE,
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                finalized_at=FINALIZED_AT + timedelta(seconds=1),
            )
        assert repeated == ()
    finally:
        engine.dispose()


def test_finalizer_skips_open_windows_and_isolates_streams() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    open_window = build_window(
        source=SOURCE,
        start=datetime(2026, 10, 14, 10, tzinfo=UTC),
        is_closed=False,
    )
    other_stream = build_window(
        source="binance-public",
        start=datetime(2026, 10, 14, 10, tzinfo=UTC),
    )
    watermark = build_watermark(
        source=SOURCE,
        high_water_event_time=datetime(2026, 10, 14, 12, 5, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            store.stage_watermark(watermark)
            store.stage_window_version(open_window)
            store.stage_window_version(other_stream)

        with factory() as session:
            result = SqlAlchemyMarketDataWindowFinalizer(session).finalize_eligible(
                source=SOURCE,
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                finalized_at=FINALIZED_AT,
            )
        assert result == ()

        with factory() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            assert store.get_latest_window(open_window.window_id) == open_window
            assert store.get_latest_window(other_stream.window_id) == other_stream
    finally:
        engine.dispose()


def test_finalizer_requires_a_persisted_stream_watermark() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with (
            factory() as session,
            pytest.raises(MarketDataWindowFinalizationWatermarkMissingError),
        ):
            SqlAlchemyMarketDataWindowFinalizer(session).finalize_eligible(
                source=SOURCE,
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                finalized_at=FINALIZED_AT,
            )
    finally:
        engine.dispose()


def test_finalization_repository_reads_evidence_by_window_version() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    provisional = build_window(
        source=SOURCE,
        start=datetime(2026, 10, 14, 11, tzinfo=UTC),
    )
    watermark = build_watermark(
        source=SOURCE,
        high_water_event_time=datetime(2026, 10, 14, 12, 5, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            store.stage_watermark(watermark)
            store.stage_window_version(provisional)
        with factory() as session:
            result = SqlAlchemyMarketDataWindowFinalizer(session).finalize_eligible(
                source=SOURCE,
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                finalized_at=FINALIZED_AT,
            )
        assert len(result) == 1

        with factory() as session:
            stored = SqlAlchemyMarketDataWindowFinalizationRepository(
                session
            ).get_by_window_version(
                window_id=provisional.window_id,
                finalized_version=2,
            )
        assert stored == result[0]
    finally:
        engine.dispose()
