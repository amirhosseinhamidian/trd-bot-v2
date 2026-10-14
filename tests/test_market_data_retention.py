from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from scripts.manage_market_data_retention import POLICY_VERSION, parse_args
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyMarketDataRetentionManager,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.models import (
    MarketDataEventDecisionRow,
    MarketDataEventInboxRow,
    MarketDataEventRow,
    MarketDataOutboxRow,
    MarketDataRawObservationRow,
    MarketDataReplayRequestRow,
    MarketDataRetentionHoldRow,
    MarketDataRetentionRunRow,
    MarketDataWatermarkRow,
    MarketDataWindowFinalizationRow,
    MarketDataWindowRevisionRow,
    MarketDataWindowVersionRow,
)
from trd_bot.jobs import (
    BackgroundJob,
    BackgroundJobBuilder,
    BackgroundJobKind,
    BackgroundJobStatus,
)
from trd_bot.market_data import (
    MarketDataRetentionHoldKind,
    MarketDataRetentionMode,
    MarketDataRetentionOutcome,
)

NOW = datetime(2026, 10, 15, 1, tzinfo=UTC)
OLD = NOW - timedelta(days=400)
RECENT = NOW - timedelta(days=1)


def _factory() -> tuple[object, sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    return engine, create_session_factory(engine)


def _event(event_id: str, *, persisted_at: datetime = OLD) -> MarketDataEventRow:
    return MarketDataEventRow(
        event_id=event_id,
        raw_observation_id=f"raw-for-{event_id}",
        schema_version="market-data-event-v1",
        kind="candle_observed",
        source="kraken-public",
        base_asset="BTC",
        quote_asset="USDT",
        market_type="spot",
        timeframe="1h",
        event_time=persisted_at,
        observed_at=persisted_at,
        window_id=f"window-for-{event_id}",
        payload_version="canonical-candle-v1",
        payload_checksum="a" * 64,
        idempotency_key=f"event-key-{event_id}",
        payload_json="{}",
        persisted_at=persisted_at,
    )


def _raw(observation_id: str, *, created_at: datetime = OLD) -> MarketDataRawObservationRow:
    return MarketDataRawObservationRow(
        observation_id=observation_id,
        schema_version="market-data-raw-observation-v1",
        source="kraken-public",
        base_asset="BTC",
        quote_asset="USDT",
        market_type="spot",
        timeframe="1h",
        window_start=created_at - timedelta(hours=1),
        window_end=created_at,
        observed_at=created_at,
        payload_checksum="b" * 64,
        payload_json="{}",
        created_at=created_at,
    )


def _decision(
    decision_id: str,
    event_id: str,
    *,
    requires_replay: bool,
) -> MarketDataEventDecisionRow:
    return MarketDataEventDecisionRow(
        decision_id=decision_id,
        observation_id=f"observation-for-{decision_id}",
        event_id=event_id,
        watermark_id=f"watermark-for-{decision_id}",
        schema_version="market-data-event-decision-v1",
        window_id=f"window-for-{event_id}",
        arrival="late" if requires_replay else "on_time",
        disposition="revision_required" if requires_replay else "accepted",
        reason="late_arrival" if requires_replay else "new_window",
        existing_window_version=None,
        proposed_window_version=1,
        requires_replay=requires_replay,
        decided_at=OLD,
        payload_json="{}",
    )


def _replay_request(replay_id: str, decision_id: str, event_id: str) -> MarketDataReplayRequestRow:
    return MarketDataReplayRequestRow(
        replay_id=replay_id,
        schema_version="market-data-replay-request-v1",
        decision_id=decision_id,
        observation_id=f"observation-for-{decision_id}",
        event_id=event_id,
        window_id=f"window-for-{event_id}",
        reason="late_arrival",
        requested_by="operator:test",
        requested_at=OLD,
        payload_json="{}",
    )


def _replay_job(decision_id: str, *, status: BackgroundJobStatus) -> BackgroundJob:
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.MARKET_DATA_REPLAY,
        payload={"replay_id": f"replay-for-{decision_id}"},
        idempotency_key=f"market-data-replay:{decision_id}",
        now=OLD,
    )
    if status is BackgroundJobStatus.QUEUED:
        return job
    return BackgroundJob.model_validate(
        job.model_copy(
            update={
                "status": status,
                "progress_percent": 100 if status is BackgroundJobStatus.SUCCEEDED else 50,
                "attempt_count": 1,
                "started_at": OLD + timedelta(minutes=1),
                "finished_at": OLD + timedelta(minutes=2),
                "updated_at": OLD + timedelta(minutes=2),
                "result_reference": (
                    "retention-test-result" if status is BackgroundJobStatus.SUCCEEDED else None
                ),
                "error_code": ("replay_failed" if status is BackgroundJobStatus.FAILED else None),
                "error_message": (
                    "sanitized failure" if status is BackgroundJobStatus.FAILED else None
                ),
            }
        ).model_dump()
    )


def _seed_retention_matrix(factory: sessionmaker[Session]) -> dict[str, str]:
    standalone_event_id = "market-event-standalone-old"
    delivered_event_id = "market-event-delivered-old"
    failed_event_id = "market-event-failed-old"
    accepted_event_id = "market-event-decision-old"
    completed_event_id = "market-event-replay-completed-old"
    terminal_event_id = "market-event-replay-terminal-old"
    pending_event_id = "market-event-replay-pending-old"
    completed_decision_id = "market-decision-completed-old"
    terminal_decision_id = "market-decision-terminal-old"
    pending_decision_id = "market-decision-pending-old"
    completed_replay_id = "market-replay-completed-old"
    terminal_replay_id = "market-replay-terminal-old"
    pending_replay_id = "market-replay-pending-old"

    with factory() as session:
        session.add_all(
            [
                _raw("market-raw-old"),
                _raw("market-raw-recent", created_at=RECENT),
                _event(standalone_event_id),
                _event(delivered_event_id),
                _event(failed_event_id),
                _event(accepted_event_id),
                _event(completed_event_id),
                _event(terminal_event_id),
                _event(pending_event_id),
                MarketDataEventInboxRow(
                    idempotency_key="market-data-event:" + "c" * 64,
                    schema_version="market-data-inbox-v1",
                    event_id=standalone_event_id,
                    payload_checksum="c" * 64,
                    first_seen_at=OLD,
                    last_seen_at=OLD,
                    delivery_count=1,
                    payload_json="{}",
                ),
                _decision(
                    "market-decision-accepted-old",
                    accepted_event_id,
                    requires_replay=False,
                ),
                _decision(
                    completed_decision_id,
                    completed_event_id,
                    requires_replay=True,
                ),
                _decision(
                    terminal_decision_id,
                    terminal_event_id,
                    requires_replay=True,
                ),
                _decision(
                    pending_decision_id,
                    pending_event_id,
                    requires_replay=True,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                MarketDataOutboxRow(
                    outbox_id="market-outbox-delivered-old",
                    event_id=delivered_event_id,
                    schema_version="market-data-outbox-v1",
                    topic="market-data.windowing.v1",
                    payload_version="market-data-outbox-payload-v1",
                    payload_json="{}",
                    status="delivered",
                    attempt_count=1,
                    created_at=OLD,
                    available_at=OLD,
                    updated_at=OLD,
                    delivered_at=OLD,
                    error_code=None,
                    error_message=None,
                ),
                MarketDataOutboxRow(
                    outbox_id="market-outbox-failed-old",
                    event_id=failed_event_id,
                    schema_version="market-data-outbox-v1",
                    topic="market-data.windowing.v1",
                    payload_version="market-data-outbox-payload-v1",
                    payload_json="{}",
                    status="failed",
                    attempt_count=20,
                    created_at=OLD,
                    available_at=OLD,
                    updated_at=OLD,
                    delivered_at=None,
                    error_code="delivery_failed",
                    error_message="sanitized failure",
                ),
                _replay_request(
                    completed_replay_id,
                    completed_decision_id,
                    completed_event_id,
                ),
                _replay_request(
                    terminal_replay_id,
                    terminal_decision_id,
                    terminal_event_id,
                ),
                _replay_request(
                    pending_replay_id,
                    pending_decision_id,
                    pending_event_id,
                ),
            ]
        )
        session.flush()
        session.add(
            MarketDataWindowRevisionRow(
                revision_id="market-revision-completed-old",
                schema_version="market-data-window-revision-v1",
                replay_id=completed_replay_id,
                decision_id=completed_decision_id,
                observation_id=f"observation-for-{completed_decision_id}",
                event_id=completed_event_id,
                window_id=f"window-for-{completed_event_id}",
                reason="late_arrival",
                kind="late_insert",
                previous_version=None,
                previous_event_id=None,
                previous_payload_checksum=None,
                revised_version=1,
                revised_payload_checksum="d" * 64,
                watermark_id="market-watermark-revision-old",
                watermark_version=1,
                watermark_time=OLD,
                applied_at=OLD,
                payload_json="{}",
            )
        )
        for decision_id, status in (
            (completed_decision_id, BackgroundJobStatus.SUCCEEDED),
            (terminal_decision_id, BackgroundJobStatus.FAILED),
            (pending_decision_id, BackgroundJobStatus.QUEUED),
        ):
            SqlAlchemyBackgroundJobRepository(session).stage(
                _replay_job(decision_id, status=status)
            )

        session.add_all(
            [
                MarketDataWatermarkRow(
                    watermark_id="market-watermark-orphan-old",
                    schema_version="market-data-watermark-v1",
                    policy_version=POLICY_VERSION,
                    source="kraken-public",
                    base_asset="ETH",
                    quote_asset="USD",
                    market_type="spot",
                    timeframe="1h",
                    version=1,
                    high_water_event_time=OLD,
                    allowed_lateness_seconds=300,
                    watermark_time=OLD - timedelta(minutes=5),
                    calculated_at=OLD,
                    stored_at=OLD,
                    payload_json="{}",
                ),
                MarketDataWatermarkRow(
                    watermark_id="market-watermark-finalized-old",
                    schema_version="market-data-watermark-v1",
                    policy_version=POLICY_VERSION,
                    source="kraken-public",
                    base_asset="BTC",
                    quote_asset="USDT",
                    market_type="spot",
                    timeframe="1h",
                    version=1,
                    high_water_event_time=OLD,
                    allowed_lateness_seconds=300,
                    watermark_time=OLD - timedelta(minutes=5),
                    calculated_at=OLD,
                    stored_at=OLD,
                    payload_json="{}",
                ),
                MarketDataWindowVersionRow(
                    window_id="market-window-finalized-old",
                    version=1,
                    schema_version="market-data-window-v1",
                    state="provisional",
                    source="kraken-public",
                    base_asset="BTC",
                    quote_asset="USDT",
                    market_type="spot",
                    timeframe="1h",
                    window_start=OLD - timedelta(hours=1),
                    window_end=OLD,
                    event_id=accepted_event_id,
                    payload_checksum="e" * 64,
                    payload_json="{}",
                    created_at=OLD,
                    finalized_at=None,
                ),
                MarketDataWindowVersionRow(
                    window_id="market-window-finalized-old",
                    version=2,
                    schema_version="market-data-window-v1",
                    state="finalized",
                    source="kraken-public",
                    base_asset="BTC",
                    quote_asset="USDT",
                    market_type="spot",
                    timeframe="1h",
                    window_start=OLD - timedelta(hours=1),
                    window_end=OLD,
                    event_id=accepted_event_id,
                    payload_checksum="e" * 64,
                    payload_json="{}",
                    created_at=OLD,
                    finalized_at=OLD,
                ),
                MarketDataWindowFinalizationRow(
                    finalization_id="market-finalization-old",
                    schema_version="market-data-window-finalization-v1",
                    window_id="market-window-finalized-old",
                    source="kraken-public",
                    base_asset="BTC",
                    quote_asset="USDT",
                    market_type="spot",
                    timeframe="1h",
                    provisional_version=1,
                    finalized_version=2,
                    event_id=accepted_event_id,
                    payload_checksum="e" * 64,
                    watermark_id="market-watermark-finalized-old",
                    watermark_version=1,
                    policy_version=POLICY_VERSION,
                    window_end=OLD,
                    watermark_time=OLD,
                    finalized_at=OLD,
                    freshness_seconds=Decimal("0"),
                    freshness_target_seconds=600,
                    freshness_outcome="within_target",
                    payload_json="{}",
                ),
            ]
        )
        session.commit()

    return {
        "pending_replay_id": pending_replay_id,
        "completed_replay_id": completed_replay_id,
        "finalized_window_id": "market-window-finalized-old",
        "referenced_watermark_id": "market-watermark-finalized-old",
    }


def test_dry_run_and_execute_share_a_bounded_plan_and_preserve_protected_rows() -> None:
    engine, factory = _factory()
    try:
        ids = _seed_retention_matrix(factory)
        with factory() as session:
            manager = SqlAlchemyMarketDataRetentionManager(session)
            planned = manager.run(
                mode=MarketDataRetentionMode.DRY_RUN,
                requested_by="operator:test",
                batch_limit=100,
                now=NOW,
            )
        assert planned.outcome is MarketDataRetentionOutcome.COMPLETED
        assert planned.deleted_count == 0
        assert planned.selected.total <= 100
        assert planned.selected.raw_observations == 1
        assert planned.selected.delivered_outbox == 1
        assert planned.selected.failed_outbox == 1
        assert planned.selected.provisional_windows == 1
        assert planned.selected.window_revisions == 1
        assert planned.selected.replay_requests == 1
        assert planned.selected.orphan_watermarks == 1

        with factory() as session:
            executed = SqlAlchemyMarketDataRetentionManager(session).run(
                mode=MarketDataRetentionMode.EXECUTE,
                requested_by="operator:test",
                batch_limit=100,
                now=NOW,
            )
        assert executed.selected == planned.selected
        assert executed.deleted_count == executed.selected.total

        with factory() as session:
            assert session.get(MarketDataRawObservationRow, "market-raw-old") is None
            assert session.get(MarketDataRawObservationRow, "market-raw-recent") is not None
            assert (
                session.get(
                    MarketDataWindowVersionRow,
                    (ids["finalized_window_id"], 1),
                )
                is None
            )
            assert (
                session.get(
                    MarketDataWindowVersionRow,
                    (ids["finalized_window_id"], 2),
                )
                is not None
            )
            assert session.get(MarketDataWatermarkRow, ids["referenced_watermark_id"]) is not None
            assert session.get(MarketDataReplayRequestRow, ids["pending_replay_id"]) is not None
            assert session.scalar(select(func.count()).select_from(MarketDataRetentionRunRow)) == 2
            audits = session.scalars(select(MarketDataRetentionRunRow)).all()
            assert all("market-raw-old" not in row.payload_json for row in audits)
            listed = manager.list_runs(limit=1)
            assert len(listed) == 1
            assert listed[0].run_id == executed.run_id

            with pytest.raises(ValueError, match="between 1 and 100"):
                manager.list_runs(limit=0)
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_completed_replay_request_expires_only_after_revision_is_removed() -> None:
    engine, factory = _factory()
    try:
        ids = _seed_retention_matrix(factory)
        with factory() as session:
            manager = SqlAlchemyMarketDataRetentionManager(session)
            first = manager.run(
                mode=MarketDataRetentionMode.EXECUTE,
                requested_by="operator:test",
                batch_limit=100,
                now=NOW,
            )
        assert first.selected.window_revisions == 1

        with factory() as session:
            assert session.get(MarketDataReplayRequestRow, ids["completed_replay_id"]) is not None
            second = SqlAlchemyMarketDataRetentionManager(session).run(
                mode=MarketDataRetentionMode.EXECUTE,
                requested_by="operator:test",
                batch_limit=100,
                now=NOW,
            )
        assert second.selected.replay_requests >= 1
        with factory() as session:
            assert session.get(MarketDataReplayRequestRow, ids["completed_replay_id"]) is None
            assert session.get(MarketDataReplayRequestRow, ids["pending_replay_id"]) is not None
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_active_hold_blocks_every_mode_until_released() -> None:
    engine, factory = _factory()
    try:
        with factory() as session:
            session.add(_raw("market-raw-held-old"))
            session.commit()
            manager = SqlAlchemyMarketDataRetentionManager(session)
            hold = manager.place_hold(
                kind=MarketDataRetentionHoldKind.LEGAL,
                reason="Preserve evidence for case 42.",
                requested_by="operator:legal",
                now=NOW,
            )

        for mode in (MarketDataRetentionMode.DRY_RUN, MarketDataRetentionMode.EXECUTE):
            with factory() as session:
                blocked = SqlAlchemyMarketDataRetentionManager(session).run(
                    mode=mode,
                    requested_by="operator:test",
                    batch_limit=10,
                    now=NOW,
                )
            assert blocked.outcome is MarketDataRetentionOutcome.BLOCKED
            assert blocked.blocking_hold_ids == (hold.hold_id,)
            assert blocked.selected.total == 0

        with factory() as session:
            manager = SqlAlchemyMarketDataRetentionManager(session)
            released = manager.release_hold(
                hold.hold_id,
                requested_by="operator:legal",
                now=NOW + timedelta(minutes=1),
            )
            assert released.active is False
            assert manager.list_active_holds() == ()
            executed = manager.run(
                mode=MarketDataRetentionMode.EXECUTE,
                requested_by="operator:test",
                batch_limit=10,
                now=NOW + timedelta(minutes=1),
            )
        assert executed.outcome is MarketDataRetentionOutcome.COMPLETED
        assert executed.deleted_count == 1
        with factory() as session:
            assert session.get(MarketDataRawObservationRow, "market-raw-held-old") is None
            stored_hold = session.get(MarketDataRetentionHoldRow, hold.hold_id)
            assert stored_hold is not None
            assert stored_hold.released_at is not None
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_transaction_failure_rolls_back_deletes_and_persists_sanitized_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = _factory()
    try:
        with factory() as session:
            session.add(_raw("market-raw-failure-old"))
            session.commit()
            manager = SqlAlchemyMarketDataRetentionManager(session)

            def fail_delete(_: object) -> int:
                raise SQLAlchemyError("private database detail")

            monkeypatch.setattr(manager, "_delete_candidates", fail_delete)
            failed = manager.run(
                mode=MarketDataRetentionMode.EXECUTE,
                requested_by="operator:test",
                batch_limit=10,
                now=NOW,
            )

        assert failed.outcome is MarketDataRetentionOutcome.FAILED
        assert failed.error_code == "retention_transaction_failed"
        assert "private database detail" not in failed.model_dump_json()
        with factory() as session:
            assert session.get(MarketDataRawObservationRow, "market-raw-failure-old") is not None
            audit = session.get(MarketDataRetentionRunRow, failed.run_id)
            assert audit is not None
            assert "private database detail" not in audit.payload_json
    finally:
        engine.dispose()  # type: ignore[attr-defined]


def test_cli_requires_explicit_policy_confirmation_for_execute() -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "execute",
                "--requested-by",
                "operator:test",
                "--batch-limit",
                "10",
            ]
        )

    args = parse_args(
        [
            "execute",
            "--requested-by",
            "operator:test",
            "--batch-limit",
            "10",
            "--confirm-policy-version",
            POLICY_VERSION,
        ]
    )
    assert args.command == "execute"
