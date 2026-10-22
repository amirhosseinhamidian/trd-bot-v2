from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Table, func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateTable

from tests.test_alert_persistence import (
    AS_OF,
    alert_draft,
    alert_rule,
    ready_assessment,
    seed_assessment,
    source_reference,
)
from trd_bot.alerts import (
    AlertEvaluationDisposition,
    AlertEvaluationRecord,
    AlertPublicationPolicy,
    AlertSeverity,
    AlertSuppressionReason,
    build_alert_evaluation_id,
)
from trd_bot.api import dependencies
from trd_bot.api.routes import alerts as alert_routes
from trd_bot.db import (
    AlertExpiryRecordRow,
    AlertPublicationDecisionRow,
    AlertPublicationPolicyRow,
    DatabaseBase,
    SqlAlchemyAlertEvaluationRunner,
    SqlAlchemyAlertInboxRepository,
    SqlAlchemyAlertPublicationRepository,
    SqlAlchemyAlertStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.main import app
from trd_bot.market_context import MarketRegimeAssessment, build_market_regime_assessment_id

REQUESTED_AT = AS_OF + timedelta(minutes=20)


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'publication.db'}")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def later_assessment(*, hours: int = 1) -> MarketRegimeAssessment:
    original = ready_assessment()
    as_of = original.as_of + timedelta(hours=hours)
    input_checksum = f"{hours + 1:x}" * 64
    snapshot_checksum = f"{hours + 2:x}" * 64
    return MarketRegimeAssessment.model_validate(
        {
            **original.model_dump(),
            "assessment_id": build_market_regime_assessment_id(
                source=original.source,
                pair=original.pair,
                as_of=as_of,
                input_checksum=input_checksum,
                feature_set_version=original.feature_set_version,
                algorithm_version=original.algorithm_version,
            ),
            "as_of": as_of,
            "input_manifest_id": f"market-context-input-{input_checksum[:16]}",
            "input_checksum": input_checksum,
            "feature_snapshot_id": f"market-context-features-{snapshot_checksum[:16]}",
            "feature_snapshot_checksum": snapshot_checksum,
            "assessed_at": as_of + timedelta(minutes=1),
            "expires_at": as_of + timedelta(hours=1, minutes=1),
        }
    )


def policy(**overrides: object) -> AlertPublicationPolicy:
    values: dict[str, object] = {
        "policy_version": 1,
        "quiet_hours_enabled": True,
        "quiet_hours_start_minute": 22 * 60,
        "quiet_hours_end_minute": 7 * 60,
        "timezone_name": "Asia/Tehran",
        "critical_bypass_quiet_hours": True,
        "updated_by": "operator:test",
        "updated_at": datetime(2026, 10, 18, tzinfo=UTC),
    }
    values.update(overrides)
    return AlertPublicationPolicy.build(**values)  # type: ignore[arg-type]


def test_publication_constraints_use_cross_database_boolean_predicates() -> None:
    dialects: tuple[Dialect, ...] = (
        postgresql.dialect(),  # type: ignore[no-untyped-call]
        sqlite.dialect(),
    )
    policy_table = cast(Table, AlertPublicationPolicyRow.__table__)
    decision_table = cast(Table, AlertPublicationDecisionRow.__table__)

    for dialect in dialects:
        policy_ddl = str(CreateTable(policy_table).compile(dialect=dialect))
        decision_ddl = str(CreateTable(decision_table).compile(dialect=dialect))

        assert "NOT quiet_hours_enabled" in policy_ddl
        assert "quiet_hours_enabled = 0" not in policy_ddl
        assert "allowed AND suppression_reason_count = 0" in decision_ddl
        assert "NOT allowed AND suppression_reason_count >= 1" in decision_ddl
        assert "allowed = 1" not in decision_ddl
        assert "allowed = 0" not in decision_ddl


def seed_published_alert(factory: sessionmaker[Session]) -> str:
    assessment = ready_assessment()
    rule = alert_rule()
    source = source_reference(assessment, evaluated_at=REQUESTED_AT)
    draft = alert_draft(rule, source)
    with factory.begin() as session:
        seed_assessment(session, assessment)
        store = SqlAlchemyAlertStore(session)
        store.stage_rule_definition(rule)
        store.stage_evaluation(AlertEvaluationRecord.published(draft), draft=draft)
    return draft.alert_id


def test_quiet_hours_support_cross_midnight_timezone_and_critical_bypass() -> None:
    configured = policy()
    during_quiet_hours = datetime(2026, 10, 18, 20, tzinfo=UTC)  # 23:30 Tehran

    assert configured.suppresses(
        severity=AlertSeverity.WARNING,
        evaluated_at=during_quiet_hours,
    )
    assert not configured.suppresses(
        severity=AlertSeverity.CRITICAL,
        evaluated_at=during_quiet_hours,
    )
    assert configured.quiet_hours_end(evaluated_at=during_quiet_hours) == datetime(
        2026,
        10,
        19,
        3,
        30,
        tzinfo=UTC,
    )

    with pytest.raises(ValidationError, match="timezone is unknown"):
        policy(timezone_name="Mars/Olympus")
    with pytest.raises(ValidationError, match="distinct start and end"):
        policy(quiet_hours_start_minute=60, quiet_hours_end_minute=60)


def test_policy_revisions_are_append_only_and_checksummed(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        repository = SqlAlchemyAlertPublicationRepository(session)
        assert repository.get_policy().policy_version == 0
        first = repository.update_policy(
            quiet_hours_enabled=True,
            quiet_hours_start_minute=1320,
            quiet_hours_end_minute=420,
            timezone_name="Asia/Tehran",
            critical_bypass_quiet_hours=True,
            updated_by="operator:first",
            updated_at=AS_OF,
        )
        second = repository.update_policy(
            quiet_hours_enabled=False,
            quiet_hours_start_minute=1320,
            quiet_hours_end_minute=420,
            timezone_name="UTC",
            critical_bypass_quiet_hours=False,
            updated_by="operator:second",
            updated_at=AS_OF + timedelta(minutes=1),
        )

        assert first.policy_version == 1
        assert second.policy_version == 2
        assert repository.get_policy() == second
        assert session.scalar(select(func.count()).select_from(AlertPublicationPolicyRow)) == 2


def test_publication_guard_enforces_duplicate_cooldown_and_active_snooze(
    factory: sessionmaker[Session],
) -> None:
    previous_alert_id = seed_published_alert(factory)
    second = later_assessment(hours=0)
    second_requested_at = second.as_of + timedelta(minutes=25)
    source = source_reference(second, evaluated_at=second_requested_at)
    rule = alert_rule()
    evaluation_id = build_alert_evaluation_id(
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        source_kind=source.source_kind,
        source_event_id=source.source_event_id,
    )

    with factory() as session:
        SqlAlchemyAlertInboxRepository(session).snooze(
            previous_alert_id,
            acted_by="operator:test",
            occurred_at=REQUESTED_AT + timedelta(minutes=5),
            duration_seconds=7200,
        )
        decision = SqlAlchemyAlertPublicationRepository(session).evaluate(
            evaluation_id=evaluation_id,
            rule=rule,
            source=source,
            evaluated_at=second_requested_at,
            policy=AlertPublicationPolicy.default(),
        )

    assert decision.allowed is False
    assert decision.previous_alert_id == previous_alert_id
    assert decision.suppression_reasons == (
        AlertSuppressionReason.COOLDOWN_ACTIVE,
        AlertSuppressionReason.DUPLICATE,
        AlertSuppressionReason.SNOOZED,
    )


def test_runner_persists_policy_suppression_and_decision_atomically(
    factory: sessionmaker[Session],
) -> None:
    previous_alert_id = seed_published_alert(factory)
    second = later_assessment()
    rule = alert_rule()
    requested_at = second.as_of + timedelta(minutes=10)
    with factory.begin() as session:
        seed_assessment(session, second)
    from trd_bot.alerts import AlertEvaluationJobPayload

    payload = AlertEvaluationJobPayload.build(
        rule=rule,
        assessment=second,
        requested_at=requested_at,
    )
    evaluation = SqlAlchemyAlertEvaluationRunner(factory).run(
        payload,
        executed_at=requested_at,
    )

    assert evaluation.disposition is AlertEvaluationDisposition.SUPPRESSED
    assert evaluation.suppression_reasons == (
        AlertSuppressionReason.COOLDOWN_ACTIVE,
        AlertSuppressionReason.DUPLICATE,
    )
    with factory() as session:
        decision = SqlAlchemyAlertPublicationRepository(session).get_decision(
            evaluation.evaluation_id
        )
        assert decision is not None
        assert decision.previous_alert_id == previous_alert_id
        assert session.scalar(select(func.count()).select_from(AlertPublicationDecisionRow)) == 1


def test_execution_time_expiry_fails_closed_without_publishing(
    factory: sessionmaker[Session],
) -> None:
    assessment = ready_assessment()
    rule = alert_rule()
    with factory.begin() as session:
        seed_assessment(session, assessment)
        SqlAlchemyAlertStore(session).stage_rule_definition(rule)
    from trd_bot.alerts import AlertEvaluationJobPayload

    payload = AlertEvaluationJobPayload.build(
        rule=rule,
        assessment=assessment,
        requested_at=REQUESTED_AT,
    )
    evaluation = SqlAlchemyAlertEvaluationRunner(factory).run(
        payload,
        executed_at=assessment.expires_at + timedelta(seconds=1),
    )

    assert evaluation.disposition is AlertEvaluationDisposition.SUPPRESSED
    assert evaluation.suppression_reasons == (AlertSuppressionReason.SOURCE_EXPIRED,)


def test_expiry_sweep_is_bounded_durable_and_idempotent(
    factory: sessionmaker[Session],
) -> None:
    seed_published_alert(factory)
    after_expiry = AS_OF + timedelta(hours=2)
    with factory() as session:
        repository = SqlAlchemyAlertPublicationRepository(session)
        before = repository.expiry_summary(evaluated_at=after_expiry)
        first = repository.sweep_expired(
            evaluated_at=after_expiry,
            recorded_by="operator:expiry",
            limit=1,
        )
        second = repository.sweep_expired(
            evaluated_at=after_expiry,
            recorded_by="operator:expiry",
            limit=1,
        )

        assert before.pending_total == 1
        assert first.recorded_count == 1
        assert first.remaining_pending == 0
        assert second.recorded_count == 0
        assert session.scalar(select(func.count()).select_from(AlertExpiryRecordRow)) == 1


def test_expiry_sweep_locks_only_alert_rows_for_postgresql() -> None:
    session_mock = Mock(spec=Session)
    session_mock.scalars.return_value.all.return_value = []
    session_mock.scalar.return_value = 0

    result = SqlAlchemyAlertPublicationRepository(cast(Session, session_mock)).sweep_expired(
        evaluated_at=AS_OF + timedelta(hours=2),
        recorded_by="operator:expiry",
        limit=10,
    )

    statement = session_mock.scalars.call_args.args[0]
    compiled = str(
        statement.compile(dialect=postgresql.dialect())  # type: ignore[no-untyped-call]
    )

    assert "FOR UPDATE OF alerts" in compiled
    assert result.recorded_count == 0
    assert result.remaining_pending == 0


@pytest.fixture
def publication_api(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    seed_published_alert(factory)
    session = factory()
    publication = SqlAlchemyAlertPublicationRepository(session)
    app.dependency_overrides[dependencies.get_alert_publication_repository] = lambda: publication
    monkeypatch.setattr(alert_routes, "_now", lambda: AS_OF + timedelta(hours=2))
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(dependencies.get_alert_publication_repository, None)
        session.close()


def test_publication_policy_and_expiry_api(publication_api: TestClient) -> None:
    client = publication_api
    default = client.get("/api/v1/alerts/publication-policy")
    updated = client.post(
        "/api/v1/alerts/publication-policy",
        json={
            "acted_by": "operator:alert-center",
            "quiet_hours_enabled": True,
            "quiet_hours_start_minute": 1320,
            "quiet_hours_end_minute": 420,
            "timezone_name": "Asia/Tehran",
            "critical_bypass_quiet_hours": True,
        },
    )
    summary = client.get("/api/v1/alerts/expiry")
    swept = client.post(
        "/api/v1/alerts/expiry/sweep",
        json={"acted_by": "operator:alert-center", "limit": 10},
    )

    assert default.status_code == 200
    assert default.json()["policy_version"] == 0
    assert updated.status_code == 200
    assert updated.json()["policy_version"] == 1
    assert updated.json()["timezone_name"] == "Asia/Tehran"
    assert summary.status_code == 200
    assert summary.json()["pending_total"] == 1
    assert swept.status_code == 200
    assert swept.json()["recorded_count"] == 1

    invalid = client.post(
        "/api/v1/alerts/publication-policy",
        json={
            "acted_by": "<script>",
            "quiet_hours_enabled": True,
            "quiet_hours_start_minute": 0,
            "quiet_hours_end_minute": 0,
            "timezone_name": "Unknown/Zone",
        },
    )
    assert invalid.status_code == 422
    assert "input" not in str(invalid.json())
