import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from scripts.plan_v0_3_maintenance import validate_maintenance_database_url
from sqlalchemy import func, select

from tests.test_dataset_file_stage_repository import build_stage
from trd_bot.alerts import AlertExpirySummary
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyDatasetFileStageRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.models import MarketDataRetentionRunRow
from trd_bot.db.release_maintenance import SqlAlchemyReleaseMaintenancePlanner
from trd_bot.maintenance import build_parser as build_maintenance_parser
from trd_bot.maintenance import cleanup_expired_dataset_stages
from trd_bot.market_data import (
    MarketDataRetentionCounts,
    MarketDataRetentionCutoffs,
    MarketDataRetentionMode,
    MarketDataRetentionOutcome,
    MarketDataRetentionRun,
)
from trd_bot.release_maintenance import (
    RELEASE_MAINTENANCE_POLICY_VERSION,
    ReleaseMaintenanceActionCode,
    ReleaseMaintenanceDisposition,
    ReleaseMaintenanceReasonCode,
    ReleaseMaintenanceSnapshot,
    build_release_maintenance_plan,
    default_release_maintenance_policy,
    parse_release_maintenance_plan,
    serialize_release_maintenance_plan,
)

_NOW = datetime(2026, 10, 22, 8, tzinfo=UTC)
_COMMIT_SHA = "b" * 40


def _cutoffs() -> MarketDataRetentionCutoffs:
    return MarketDataRetentionCutoffs(
        raw_observations_before=_NOW - timedelta(days=30),
        normalized_events_before=_NOW - timedelta(days=90),
        inbox_receipts_before=_NOW - timedelta(days=180),
        delivered_outbox_before=_NOW - timedelta(days=7),
        failed_outbox_before=_NOW - timedelta(days=30),
        provisional_windows_finalized_before=_NOW - timedelta(days=30),
        revision_evidence_before=_NOW - timedelta(days=365),
        orphan_watermarks_before=_NOW - timedelta(days=365),
    )


def _retention_run(
    *,
    outcome: MarketDataRetentionOutcome = MarketDataRetentionOutcome.COMPLETED,
    selected: MarketDataRetentionCounts | None = None,
    blocking_hold_ids: tuple[str, ...] = (),
) -> MarketDataRetentionRun:
    return MarketDataRetentionRun(
        run_id="market-retention-run-" + "a" * 16,
        mode=MarketDataRetentionMode.DRY_RUN,
        outcome=outcome,
        requested_by="operator:test",
        requested_at=_NOW,
        completed_at=_NOW,
        batch_limit=100,
        cutoffs=_cutoffs(),
        selected=selected or MarketDataRetentionCounts(),
        deleted_count=0,
        blocking_hold_ids=blocking_hold_ids,
        error_code=(
            "retention_transaction_failed" if outcome is MarketDataRetentionOutcome.FAILED else None
        ),
    )


def _snapshot(
    *,
    retention: MarketDataRetentionRun | None = None,
    expired_stages: int = 0,
    alert_pending: int = 0,
    candidate_journals: int = 0,
    candidate_projections: int = 0,
    projection_lagging: bool = False,
) -> ReleaseMaintenanceSnapshot:
    journal_at = _NOW - timedelta(minutes=5) if candidate_journals else None
    projection_at = None
    if candidate_projections:
        projection_at = _NOW - timedelta(minutes=10) if projection_lagging else _NOW
    return ReleaseMaintenanceSnapshot(
        evaluated_at=_NOW,
        market_data_retention_plan=retention or _retention_run(),
        expired_dataset_stages=expired_stages,
        alert_expiry=AlertExpirySummary(
            evaluated_at=_NOW,
            expired_total=alert_pending,
            materialized_total=0,
            pending_total=alert_pending,
        ),
        candidate_journals=candidate_journals,
        candidate_projections=candidate_projections,
        latest_candidate_journal_at=journal_at,
        latest_candidate_projection_at=projection_at,
    )


def test_release_maintenance_policy_is_frozen_and_non_automatic() -> None:
    policy = default_release_maintenance_policy()

    assert policy.market_data_batch_limit == 100
    assert policy.dataset_stage_batch_limit == 100
    assert policy.alert_expiry_batch_limit == 100
    assert policy.automatic_execution_allowed is False
    assert policy.immutable_evidence_deletion_allowed is False
    assert policy.definition_checksum == (
        "37b921b7dc27e7a0cd95f66d4b5276679a5e8a07adae6b07ea0cc810119a4ade"
    )


def test_empty_snapshot_requires_no_maintenance_and_round_trips() -> None:
    plan = build_release_maintenance_plan(
        environment_label="unit-test",
        commit_sha=_COMMIT_SHA,
        generated_at=_NOW,
        snapshot=_snapshot(),
    )

    assert all(
        action.disposition is ReleaseMaintenanceDisposition.NOT_REQUIRED for action in plan.actions
    )
    assert plan.human_approval_required is False
    assert plan.retention_dry_run_audit_written is True
    assert plan.automatic_maintenance_executed is False
    assert plan.immutable_evidence_deletion_allowed is False
    assert plan.external_order_submission_allowed is False
    assert parse_release_maintenance_plan(serialize_release_maintenance_plan(plan)) == plan


def test_due_work_is_bounded_and_requires_human_approval() -> None:
    plan = build_release_maintenance_plan(
        environment_label="unit-test",
        commit_sha=_COMMIT_SHA,
        generated_at=_NOW,
        snapshot=_snapshot(
            retention=_retention_run(selected=MarketDataRetentionCounts(raw_observations=2)),
            expired_stages=3,
            alert_pending=4,
            candidate_journals=2,
            candidate_projections=1,
            projection_lagging=True,
        ),
    )

    actions = {action.code: action for action in plan.actions}
    assert plan.human_approval_required is True
    assert all(
        action.disposition is ReleaseMaintenanceDisposition.REQUIRED for action in actions.values()
    )
    assert actions[ReleaseMaintenanceActionCode.MARKET_DATA_RETENTION].batch_limit == 100
    assert actions[ReleaseMaintenanceActionCode.DATASET_STAGE_CLEANUP].observed_count == 3
    assert actions[ReleaseMaintenanceActionCode.ALERT_EXPIRY_MATERIALIZATION].observed_count == 4
    assert (
        actions[ReleaseMaintenanceActionCode.CANDIDATE_PROJECTION_REBUILD].reason_code
        is ReleaseMaintenanceReasonCode.PROJECTION_LAGGING
    )


def test_retention_hold_blocks_only_the_destructive_retention_action() -> None:
    plan = build_release_maintenance_plan(
        environment_label="unit-test",
        commit_sha=_COMMIT_SHA,
        generated_at=_NOW,
        snapshot=_snapshot(
            retention=_retention_run(
                outcome=MarketDataRetentionOutcome.BLOCKED,
                blocking_hold_ids=("market-retention-hold-" + "c" * 16,),
            ),
            alert_pending=1,
        ),
    )
    actions = {action.code: action for action in plan.actions}

    assert (
        actions[ReleaseMaintenanceActionCode.MARKET_DATA_RETENTION].disposition
        is ReleaseMaintenanceDisposition.BLOCKED
    )
    assert (
        actions[ReleaseMaintenanceActionCode.MARKET_DATA_RETENTION].reason_code
        is ReleaseMaintenanceReasonCode.RETENTION_HOLD_ACTIVE
    )
    assert (
        actions[ReleaseMaintenanceActionCode.ALERT_EXPIRY_MATERIALIZATION].disposition
        is ReleaseMaintenanceDisposition.REQUIRED
    )


def test_plan_rejects_derived_and_checksum_tampering() -> None:
    plan = build_release_maintenance_plan(
        environment_label="unit-test",
        commit_sha=_COMMIT_SHA,
        generated_at=_NOW,
        snapshot=_snapshot(alert_pending=1),
    )
    payload = json.loads(serialize_release_maintenance_plan(plan))
    payload["actions"] = []

    with pytest.raises(ValidationError, match="actions are inconsistent"):
        parse_release_maintenance_plan(json.dumps(payload))

    payload = json.loads(serialize_release_maintenance_plan(plan))
    payload["report_checksum"] = "0" * 64
    with pytest.raises(ValueError, match="report checksum is inconsistent"):
        parse_release_maintenance_plan(json.dumps(payload))


def test_sqlalchemy_planner_writes_only_retention_dry_run_audit_on_empty_database() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            plan = SqlAlchemyReleaseMaintenancePlanner(session).plan(
                environment_label="sqlite-query-test",
                commit_sha=_COMMIT_SHA,
                requested_by="operator:test",
                generated_at=_NOW,
            )
        with factory() as session:
            audit_count = int(
                session.scalar(select(func.count()).select_from(MarketDataRetentionRunRow)) or 0
            )
    finally:
        engine.dispose()

    assert audit_count == 1
    assert plan.snapshot.market_data_retention_plan.deleted_count == 0
    assert plan.human_approval_required is False


def test_expired_dataset_stage_cleanup_is_bounded() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    expired = tuple(build_stage(now=_NOW - timedelta(days=3, minutes=index)) for index in range(3))
    current = build_stage(now=_NOW)
    try:
        with factory() as session:
            repository = SqlAlchemyDatasetFileStageRepository(session)
            for stage in (*expired, current):
                repository.save(stage)

        summary = cleanup_expired_dataset_stages(
            factory,
            requested_by=" operator:test ",
            batch_limit=2,
            now=_NOW,
        )

        with factory() as session:
            repository = SqlAlchemyDatasetFileStageRepository(session)
            assert repository.count_expired(now=_NOW) == 1
            assert repository.get(current.stage_id) == current
            assert repository.get(expired[0].stage_id) == expired[0]
            assert repository.get(expired[1].stage_id) is None
            assert repository.get(expired[2].stage_id) is None
    finally:
        engine.dispose()

    assert summary.requested_by == "operator:test"
    assert summary.expired_before == 3
    assert summary.deleted_count == 2
    assert summary.remaining_expired == 1


@pytest.mark.parametrize("batch_limit", [0, 501])
def test_expired_dataset_stage_cleanup_rejects_unbounded_limits(batch_limit: int) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with pytest.raises(ValueError, match="between 1 and 500"):
            cleanup_expired_dataset_stages(
                factory,
                requested_by="operator:test",
                batch_limit=batch_limit,
                now=_NOW,
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("database_url", ["", " ", "sqlite:///local.sqlite3"])
def test_release_maintenance_plan_rejects_non_postgresql_database(
    database_url: str,
) -> None:
    with pytest.raises(ValueError, match=r"database URL|requires PostgreSQL"):
        validate_maintenance_database_url(database_url)


def test_release_maintenance_plan_accepts_postgresql_database() -> None:
    database_url = "postgresql+psycopg://postgres:postgres@localhost:5432/trd_bot_test"

    assert validate_maintenance_database_url(database_url) == database_url


def test_dataset_cleanup_policy_version_is_explicit() -> None:
    assert RELEASE_MAINTENANCE_POLICY_VERSION == "release-maintenance-policy-v1"

    with pytest.raises(SystemExit):
        build_maintenance_parser().parse_args(
            [
                "cleanup-expired-dataset-stages",
                "--requested-by",
                "operator:test",
            ]
        )
