from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.api import job_handlers
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import (
    DatabaseBase,
    MarketDataReplayRejectedError,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyMarketDataEventStore,
    SqlAlchemyMarketDataIngestor,
    SqlAlchemyMarketDataReplayEnqueuer,
    SqlAlchemyMarketDataReplayRunner,
    SqlAlchemyMarketDataWindowRevisionRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.models import (
    BackgroundJobRow,
    MarketDataReplayRequestRow,
    MarketDataWindowRevisionRow,
    MarketDataWindowVersionRow,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.jobs import BackgroundJobKind, BackgroundJobStatus, BackgroundJobWorker
from trd_bot.market_data import (
    MarketDataEvent,
    MarketDataEventDisposition,
    MarketDataEventReason,
    MarketDataRawObservation,
    MarketDataRevisionKind,
    MarketDataWatermark,
    MarketDataWindowSnapshot,
    MarketDataWindowState,
    VersionedMarketDataWatermark,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"
WINDOW_START = datetime(2026, 10, 14, 10, tzinfo=UTC)
REQUESTED_AT = datetime(2026, 10, 14, 12, 8, tzinfo=UTC)
APPLIED_AT = datetime(2026, 10, 14, 12, 9, tzinfo=UTC)


def build_event(*, close_price: str, received_at: datetime) -> MarketDataEvent:
    return MarketDataEvent.from_candle(
        OHLCVCandle(
            source=SOURCE,
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=WINDOW_START,
            close_time=WINDOW_START + timedelta(hours=1),
            received_at=received_at,
            open_price=Decimal("100"),
            high_price=Decimal("110"),
            low_price=Decimal("95"),
            close_price=Decimal(close_price),
            volume=Decimal("1000"),
            is_closed=True,
        )
    )


def build_watermark() -> VersionedMarketDataWatermark:
    return VersionedMarketDataWatermark.build(
        watermark=MarketDataWatermark.build(
            source=SOURCE,
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            high_water_event_time=datetime(2026, 10, 14, 12, 5, tzinfo=UTC),
            allowed_lateness_seconds=300,
            calculated_at=datetime(2026, 10, 14, 12, 6, tzinfo=UTC),
        ),
        version=1,
        policy_version="market-data-service-level-policy-v1",
        stored_at=datetime(2026, 10, 14, 12, 6, tzinfo=UTC),
    )


def ingest_revision_required(factory: sessionmaker[Session], event: MarketDataEvent) -> str:
    observation = MarketDataRawObservation.from_candle(event.candle, created_at=event.observed_at)
    with factory() as session:
        result = SqlAlchemyMarketDataIngestor(session).ingest(
            observation=observation,
            event=event,
            decided_at=event.observed_at + timedelta(seconds=1),
        )
    assert result.decision.disposition is MarketDataEventDisposition.REVISION_REQUIRED
    return result.decision_id


def test_late_event_replay_creates_one_finalized_first_version_and_audit_lineage() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    watermark = build_watermark()
    event = build_event(
        close_price="105",
        received_at=datetime(2026, 10, 14, 12, 7, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            SqlAlchemyMarketDataEventStore(session).stage_watermark(watermark)
        decision_id = ingest_revision_required(factory, event)

        with factory() as session:
            queued = SqlAlchemyMarketDataReplayEnqueuer(session).enqueue(
                decision_id=decision_id,
                requested_by="operator:test",
                requested_at=REQUESTED_AT,
            )
        assert queued.created is True
        assert queued.job.kind is BackgroundJobKind.MARKET_DATA_REPLAY
        assert queued.request.reason is MarketDataEventReason.LATE_ARRIVAL

        with factory() as session:
            revision = SqlAlchemyMarketDataReplayRunner(session).apply(
                queued.request.replay_id,
                applied_at=APPLIED_AT,
            )
        assert revision.kind is MarketDataRevisionKind.LATE_INSERT
        assert revision.previous_version is None
        assert revision.revised_version == 1
        assert revision.watermark_id == watermark.watermark_id

        with factory() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            latest = store.get_latest_window(event.window_id)
            assert latest is not None
            assert latest.state is MarketDataWindowState.FINALIZED
            assert latest.event_id == event.event_id
            assert latest.version == 1
            assert (
                store.get_latest_watermark(
                    source=SOURCE,
                    pair=PAIR,
                    timeframe=Timeframe.HOUR_1,
                )
                == watermark
            )
            assert session.scalar(select(func.count()).select_from(MarketDataReplayRequestRow)) == 1
            assert (
                session.scalar(select(func.count()).select_from(MarketDataWindowRevisionRow)) == 1
            )
    finally:
        engine.dispose()


def test_replay_correction_appends_finalized_version_without_mutating_prior_versions() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    watermark = build_watermark()
    original = build_event(
        close_price="105",
        received_at=datetime(2026, 10, 14, 11, 1, tzinfo=UTC),
    )
    provisional = MarketDataWindowSnapshot.from_event(
        original,
        version=1,
        created_at=original.observed_at,
    )
    finalized = provisional.finalize(
        watermark.watermark,
        finalized_at=datetime(2026, 10, 14, 12, 7, tzinfo=UTC),
    )
    correction = build_event(
        close_price="106",
        received_at=datetime(2026, 10, 14, 12, 7, 30, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            store.stage_watermark(watermark)
            store.stage_window_version(provisional)
            store.stage_window_version(finalized)
        decision_id = ingest_revision_required(factory, correction)
        with factory() as session:
            queued = SqlAlchemyMarketDataReplayEnqueuer(session).enqueue(
                decision_id=decision_id,
                requested_by="operator:test",
                requested_at=REQUESTED_AT,
            )
        with factory() as session:
            revision = SqlAlchemyMarketDataReplayRunner(session).apply(
                queued.request.replay_id,
                applied_at=APPLIED_AT,
            )

        assert revision.kind is MarketDataRevisionKind.CORRECTION
        assert revision.reason is MarketDataEventReason.FINALIZED_WINDOW_CONFLICT
        assert revision.previous_version == 2
        assert revision.previous_event_id == original.event_id
        assert revision.revised_version == 3
        assert revision.event_id == correction.event_id

        with factory() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            assert store.get_window_version(original.window_id, 1) == provisional
            assert store.get_window_version(original.window_id, 2) == finalized
            latest = store.get_window_version(original.window_id, 3)
            assert latest is not None
            assert latest.state is MarketDataWindowState.FINALIZED
            assert latest.payload_checksum == correction.payload_checksum
            assert session.scalar(select(func.count()).select_from(MarketDataWindowVersionRow)) == 3
    finally:
        engine.dispose()


def test_enqueue_and_apply_are_idempotent_for_worker_retry() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    event = build_event(
        close_price="105",
        received_at=datetime(2026, 10, 14, 12, 7, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            SqlAlchemyMarketDataEventStore(session).stage_watermark(build_watermark())
        decision_id = ingest_revision_required(factory, event)
        with factory() as session:
            first = SqlAlchemyMarketDataReplayEnqueuer(session).enqueue(
                decision_id=decision_id,
                requested_by="operator:test",
                requested_at=REQUESTED_AT,
            )
        with factory() as session:
            repeated = SqlAlchemyMarketDataReplayEnqueuer(session).enqueue(
                decision_id=decision_id,
                requested_by="another-operator",
                requested_at=REQUESTED_AT + timedelta(minutes=1),
            )
        assert repeated.created is False
        assert repeated.request == first.request
        assert repeated.job == first.job

        with factory() as session:
            revision = SqlAlchemyMarketDataReplayRunner(session).apply(
                first.request.replay_id,
                applied_at=APPLIED_AT,
            )
        with factory() as session:
            retry = SqlAlchemyMarketDataReplayRunner(session).apply(
                first.request.replay_id,
                applied_at=APPLIED_AT + timedelta(minutes=1),
            )
            assert retry == revision
            assert session.scalar(select(func.count()).select_from(BackgroundJobRow)) == 1
            assert (
                session.scalar(select(func.count()).select_from(MarketDataWindowRevisionRow)) == 1
            )
    finally:
        engine.dispose()


def test_replay_rejects_stale_source_version_instead_of_overwriting_newer_window() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    watermark = build_watermark()
    event = build_event(
        close_price="105",
        received_at=datetime(2026, 10, 14, 12, 7, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            SqlAlchemyMarketDataEventStore(session).stage_watermark(watermark)
        decision_id = ingest_revision_required(factory, event)
        with factory() as session:
            queued = SqlAlchemyMarketDataReplayEnqueuer(session).enqueue(
                decision_id=decision_id,
                requested_by="operator:test",
                requested_at=REQUESTED_AT,
            )
        unexpected = MarketDataWindowSnapshot.from_event(
            event,
            version=1,
            created_at=REQUESTED_AT,
        ).finalize(watermark.watermark, finalized_at=APPLIED_AT)
        with factory.begin() as session:
            SqlAlchemyMarketDataEventStore(session).stage_window_version(unexpected)

        with (
            factory() as session,
            pytest.raises(
                MarketDataReplayRejectedError,
                match="source version is no longer current",
            ),
        ):
            SqlAlchemyMarketDataReplayRunner(session).apply(
                queued.request.replay_id,
                applied_at=APPLIED_AT + timedelta(minutes=1),
            )
        with factory() as session:
            assert (
                SqlAlchemyMarketDataWindowRevisionRepository(session).get_by_replay(
                    queued.request.replay_id
                )
                is None
            )
    finally:
        engine.dispose()


def test_replay_enqueuer_rejects_an_accepted_decision() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    event = build_event(
        close_price="105",
        received_at=datetime(2026, 10, 14, 11, 3, tzinfo=UTC),
    )
    on_time_watermark = VersionedMarketDataWatermark.build(
        watermark=MarketDataWatermark.build(
            source=SOURCE,
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            high_water_event_time=datetime(2026, 10, 14, 11, 2, tzinfo=UTC),
            allowed_lateness_seconds=300,
            calculated_at=datetime(2026, 10, 14, 11, 2, 1, tzinfo=UTC),
        ),
        version=1,
        policy_version="market-data-service-level-policy-v1",
        stored_at=datetime(2026, 10, 14, 11, 2, 1, tzinfo=UTC),
    )
    observation = MarketDataRawObservation.from_candle(
        event.candle,
        created_at=event.observed_at,
    )

    try:
        with factory.begin() as session:
            SqlAlchemyMarketDataEventStore(session).stage_watermark(on_time_watermark)
        with factory() as session:
            result = SqlAlchemyMarketDataIngestor(session).ingest(
                observation=observation,
                event=event,
                decided_at=event.observed_at + timedelta(seconds=1),
            )
        assert result.decision.disposition is MarketDataEventDisposition.ACCEPTED
        with (
            factory() as session,
            pytest.raises(
                MarketDataReplayRejectedError,
                match="not authorized",
            ),
        ):
            SqlAlchemyMarketDataReplayEnqueuer(session).enqueue(
                decision_id=result.decision_id,
                requested_by="operator:test",
                requested_at=REQUESTED_AT,
            )
    finally:
        engine.dispose()


def test_background_worker_applies_replay_and_publishes_revision_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    event = build_event(
        close_price="105",
        received_at=datetime(2026, 10, 14, 12, 7, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            SqlAlchemyMarketDataEventStore(session).stage_watermark(build_watermark())
        decision_id = ingest_revision_required(factory, event)
        with factory() as session:
            queued = SqlAlchemyMarketDataReplayEnqueuer(session).enqueue(
                decision_id=decision_id,
                requested_by="operator:test",
                requested_at=REQUESTED_AT,
            )
        monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)

        with factory() as session:
            completed = BackgroundJobWorker(
                repository=SqlAlchemyBackgroundJobRepository(session),
                handlers=build_background_job_handler_registry(),
                worker_id="market-data-replay-worker",
            ).run_once(now=datetime.now(UTC))

        assert completed is not None
        assert completed.job_id == queued.job.job_id
        assert completed.status is BackgroundJobStatus.SUCCEEDED
        assert completed.result_reference is not None
        assert completed.result_reference.startswith("market-revision-")
        with factory() as session:
            stored = SqlAlchemyMarketDataWindowRevisionRepository(session).get_by_replay(
                queued.request.replay_id
            )
            assert stored is not None
            assert stored.revision_id == completed.result_reference
    finally:
        engine.dispose()
