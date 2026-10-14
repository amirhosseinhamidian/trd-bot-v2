from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.api.dependencies import get_market_data_monitoring_reader
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyMarketDataEventStore,
    SqlAlchemyMarketDataMonitoringReader,
    SqlAlchemyMarketDataReplayRequestRepository,
    SqlAlchemyMarketDataWatchlistRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.market_data_connection_repositories import (
    SqlAlchemyMarketDataConnectionRepository,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.jobs import BackgroundJobBuilder, BackgroundJobKind
from trd_bot.main import app
from trd_bot.market_data import (
    MarketDataBacklogSummary,
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataEvent,
    MarketDataEventReason,
    MarketDataFreshnessStatus,
    MarketDataMonitoringOverallStatus,
    MarketDataMonitoringSummary,
    MarketDataReplayRequest,
    MarketDataStreamHealthStatus,
    MarketDataWatchlistEntry,
    MarketDataWatchlistRoute,
    MarketDataWatermark,
    MarketDataWindowSnapshot,
    VersionedMarketDataWatermark,
    build_market_data_replay_idempotency_key,
)

NOW = datetime(2026, 10, 14, 12, 5, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
KRAKEN_CONNECTION_ID = "market-data-connection-kraken"
BINANCE_CONNECTION_ID = "market-data-connection-binance"


def _factory() -> tuple[object, sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    return engine, create_session_factory(engine)


def _watchlist() -> MarketDataWatchlistEntry:
    entry = MarketDataWatchlistEntry.build(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        routes=(
            MarketDataWatchlistRoute(
                connection_id=KRAKEN_CONNECTION_ID,
                provider_id="kraken-public",
            ),
            MarketDataWatchlistRoute(
                connection_id=BINANCE_CONNECTION_ID,
                provider_id="binance-public",
            ),
        ),
        polling_interval_seconds=120,
        lookback_candles=3,
        now=NOW - timedelta(minutes=5),
    )
    return MarketDataWatchlistEntry.model_validate(
        entry.model_copy(
            update={
                "next_poll_at": NOW + timedelta(minutes=1),
                "updated_at": NOW,
            }
        ).model_dump()
    )


def _connection(connection_id: str, provider_id: str) -> MarketDataConnection:
    return MarketDataConnection(
        connection_id=connection_id,
        provider_id=provider_id,
        display_name=provider_id,
        state=MarketDataConnectionState.ENABLED,
        health_status=MarketDataConnectionHealth.HEALTHY,
        created_at=NOW - timedelta(days=1),
        updated_at=NOW,
        last_tested_at=NOW,
    )


def _finalized_window() -> tuple[MarketDataWindowSnapshot, VersionedMarketDataWatermark]:
    candle = OHLCVCandle(
        source="kraken-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 10, 14, 10, tzinfo=UTC),
        close_time=datetime(2026, 10, 14, 11, tzinfo=UTC),
        received_at=datetime(2026, 10, 14, 11, 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1000"),
        is_closed=True,
    )
    event = MarketDataEvent.from_candle(candle)
    watermark = VersionedMarketDataWatermark.build(
        watermark=MarketDataWatermark.build(
            source="kraken-public",
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            high_water_event_time=datetime(2026, 10, 14, 12, tzinfo=UTC),
            allowed_lateness_seconds=300,
            calculated_at=NOW - timedelta(minutes=4),
        ),
        version=1,
        policy_version="market-data-service-level-policy-v1",
        stored_at=NOW - timedelta(minutes=4),
    )
    provisional = MarketDataWindowSnapshot.from_event(
        event,
        version=1,
        created_at=event.observed_at,
    )
    return (
        provisional.finalize(
            watermark.watermark,
            finalized_at=NOW - timedelta(minutes=3),
        ),
        watermark,
    )


def _seed_stream(factory: sessionmaker[Session]) -> None:
    finalized, watermark = _finalized_window()
    with factory() as session:
        SqlAlchemyMarketDataWatchlistRepository(session).save(_watchlist())
        connections = SqlAlchemyMarketDataConnectionRepository(session)
        connections.save(_connection(KRAKEN_CONNECTION_ID, "kraken-public"))
        connections.save(_connection(BINANCE_CONNECTION_ID, "binance-public"))
        store = SqlAlchemyMarketDataEventStore(session)
        store.stage_watermark(watermark)
        store.stage_window_version(finalized)
        session.commit()


def test_reader_reports_fresh_healthy_stream_from_finalized_data() -> None:
    engine, factory = _factory()
    try:
        _seed_stream(factory)
        with factory() as session:
            summary = SqlAlchemyMarketDataMonitoringReader(session).read(generated_at=NOW)

        assert summary.overall_status is MarketDataMonitoringOverallStatus.HEALTHY
        assert summary.stream_count == 1
        assert summary.healthy_count == 1
        stream = summary.streams[0]
        assert stream.health_status is MarketDataStreamHealthStatus.HEALTHY
        assert stream.freshness_status is MarketDataFreshnessStatus.FRESH
        assert stream.selected_provider_id == "kraken-public"
        assert stream.data_age_seconds == 3900
        assert stream.lag_seconds == 300
        assert stream.freshness_target_seconds == 600
        assert stream.finalization_backlog_count == 0
        assert summary.backlog.overdue_watchlists == 0
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_reader_reports_no_data_when_watchlist_is_empty() -> None:
    engine, factory = _factory()
    try:
        with factory() as session:
            summary = SqlAlchemyMarketDataMonitoringReader(session).read(generated_at=NOW)

        assert summary.overall_status is MarketDataMonitoringOverallStatus.NO_DATA
        assert summary.stream_count == 0
        assert summary.streams == ()
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_reader_marks_old_finalized_data_stale_and_degraded() -> None:
    engine, factory = _factory()
    try:
        _seed_stream(factory)
        observed_at = NOW + timedelta(hours=2)
        with factory() as session:
            summary = SqlAlchemyMarketDataMonitoringReader(session).read(generated_at=observed_at)

        assert summary.overall_status is MarketDataMonitoringOverallStatus.CRITICAL
        assert summary.stale_count == 1
        assert summary.degraded_count == 1
        assert summary.streams[0].lag_seconds == 7500
        assert summary.backlog.overdue_watchlists == 1
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_reader_reports_poll_and_replay_backlog_without_exposing_job_payload() -> None:
    engine, factory = _factory()
    decision_id = "market-decision-1234567890abcdef"
    request = MarketDataReplayRequest(
        replay_id=MarketDataReplayRequest.build_replay_id(decision_id),
        decision_id=decision_id,
        observation_id="market-raw-1234567890abcdef",
        event_id="market-event-1234567890abcdef",
        window_id="market-window-1234567890abcdef",
        reason=MarketDataEventReason.LATE_ARRIVAL,
        requested_by="operator:test",
        requested_at=NOW,
    )
    try:
        with factory() as session:
            SqlAlchemyMarketDataReplayRequestRepository(session).stage(request)
            jobs = SqlAlchemyBackgroundJobRepository(session)
            jobs.stage(
                BackgroundJobBuilder().build(
                    kind=BackgroundJobKind.MARKET_DATA_REPLAY,
                    payload={"replay_id": request.replay_id, "private": "must-not-leak"},
                    idempotency_key=build_market_data_replay_idempotency_key(decision_id),
                    now=NOW,
                )
            )
            jobs.stage(
                BackgroundJobBuilder().build(
                    kind=BackgroundJobKind.MARKET_DATA_POLL,
                    payload={"watchlist_id": "private-payload"},
                    now=NOW,
                )
            )
            session.commit()

        with factory() as session:
            summary = SqlAlchemyMarketDataMonitoringReader(session).read(generated_at=NOW)

        assert summary.backlog.poll_jobs == 1
        assert summary.backlog.replay_jobs == 1
        assert summary.backlog.pending_replays == 1
        assert len(summary.recent_replays) == 1
        serialized = summary.model_dump(mode="json")
        replay = serialized["recent_replays"][0]
        assert "payload" not in replay
        assert "worker_id" not in replay
        assert "must-not-leak" not in str(serialized)
    finally:
        engine.dispose()  # type: ignore[attr-defined]


class StaticMarketDataMonitoringReader:
    def __init__(self, summary: MarketDataMonitoringSummary) -> None:
        self._summary = summary

    def read(self, *, generated_at: datetime | None = None) -> MarketDataMonitoringSummary:
        del generated_at
        return self._summary


@pytest.fixture
def market_data_api() -> Iterator[TestClient]:
    summary = MarketDataMonitoringSummary(
        generated_at=NOW,
        overall_status=MarketDataMonitoringOverallStatus.NO_DATA,
        stream_count=0,
        healthy_count=0,
        degraded_count=0,
        stale_count=0,
        no_data_count=0,
        paused_count=0,
        backlog=MarketDataBacklogSummary(
            poll_jobs=0,
            replay_jobs=0,
            overdue_watchlists=0,
            finalization_windows=0,
            unrequested_revisions=0,
            pending_replays=0,
            failed_replays=0,
            completed_revisions=0,
        ),
        streams=(),
        recent_replays=(),
    )
    app.dependency_overrides[get_market_data_monitoring_reader] = lambda: (
        StaticMarketDataMonitoringReader(summary)
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_market_data_monitoring_reader, None)


def test_api_exposes_read_only_market_data_monitoring_projection(
    market_data_api: TestClient,
) -> None:
    response = market_data_api.get("/api/v1/monitoring/market-data")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "market-data-monitoring-v1",
        "generated_at": "2026-10-14T12:05:00Z",
        "overall_status": "no_data",
        "stream_count": 0,
        "healthy_count": 0,
        "degraded_count": 0,
        "stale_count": 0,
        "no_data_count": 0,
        "paused_count": 0,
        "backlog": {
            "poll_jobs": 0,
            "replay_jobs": 0,
            "overdue_watchlists": 0,
            "finalization_windows": 0,
            "unrequested_revisions": 0,
            "pending_replays": 0,
            "failed_replays": 0,
            "completed_revisions": 0,
        },
        "streams": [],
        "recent_replays": [],
    }
    assert market_data_api.post("/api/v1/monitoring/market-data").status_code == 405
