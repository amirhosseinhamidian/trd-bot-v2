from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_alert_persistence import AS_OF, alert_rule, ready_assessment, seed_assessment
from trd_bot.alerts import (
    AlertEvaluationDisposition,
    AlertEvaluationEnqueueResult,
    AlertEvaluationJobCancelled,
    AlertEvaluationJobPayload,
    AlertRuleDefinition,
    AlertRuleState,
    AlertSeverity,
    AlertSuppressionReason,
    MarketContextAlertCondition,
    build_alert_evaluation_idempotency_key,
    build_alert_evaluation_job,
    evaluate_alert,
)
from trd_bot.api import job_handlers
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import (
    AlertEvaluationRow,
    AlertRow,
    BackgroundJobRow,
    DatabaseBase,
    SqlAlchemyAlertEvaluationEnqueuer,
    SqlAlchemyAlertEvaluationRunner,
    SqlAlchemyAlertStore,
    SqlAlchemyBackgroundJobRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.jobs import BackgroundJobKind, BackgroundJobStatus, BackgroundJobWorker
from trd_bot.market_context import MarketTrendRegime, MarketVolatilityRegime

REQUESTED_AT = AS_OF + timedelta(minutes=20)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def seed_inputs(factory: sessionmaker[Session]) -> tuple[AlertRuleDefinition, str]:
    assessment = ready_assessment()
    rule = alert_rule()
    with factory.begin() as session:
        seed_assessment(session, assessment)
        SqlAlchemyAlertStore(session).stage_rule_definition(rule)
    return rule, assessment.assessment_id


def enqueue(
    factory: sessionmaker[Session],
    *,
    requested_at: datetime = REQUESTED_AT,
) -> AlertEvaluationEnqueueResult:
    rule = alert_rule()
    assessment = ready_assessment()
    with factory() as session:
        return SqlAlchemyAlertEvaluationEnqueuer(session).enqueue(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            source_event_id=assessment.assessment_id,
            requested_at=requested_at,
        )


def rebuild_rule(
    *,
    version: int = 1,
    state: AlertRuleState = AlertRuleState.ENABLED,
    minimum_confidence: str = "0.75",
) -> AlertRuleDefinition:
    return AlertRuleDefinition.build(
        rule_key="high-volatility-uptrend",
        rule_version=version,
        name="High-volatility uptrend",
        description="Notify when an uptrend has high volatility and enough confidence.",
        state=state,
        severity=AlertSeverity.WARNING,
        condition=MarketContextAlertCondition(
            trends=(MarketTrendRegime.TRENDING_UP,),
            volatilities=(MarketVolatilityRegime.HIGH,),
            minimum_confidence=Decimal(minimum_confidence),
        ),
        expires_after_seconds=1800,
        deduplication_window_seconds=3600,
        cooldown_seconds=7200,
        created_at=AS_OF + timedelta(minutes=2),
    )


def test_payload_captures_exact_lineage_and_builds_stable_intent_key() -> None:
    rule = alert_rule()
    assessment = ready_assessment()
    first = AlertEvaluationJobPayload.build(
        rule=rule,
        assessment=assessment,
        requested_at=REQUESTED_AT,
    )
    later = AlertEvaluationJobPayload.build(
        rule=rule,
        assessment=assessment,
        requested_at=REQUESTED_AT + timedelta(minutes=10),
    )

    assert first.rule.definition_checksum == rule.definition_checksum
    assert first.source.source_event_id == assessment.assessment_id
    assert first.source.evaluated_at == first.requested_at
    assert build_alert_evaluation_idempotency_key(first) == (
        build_alert_evaluation_idempotency_key(later)
    )

    invalid = first.model_dump()
    invalid["requested_at"] = REQUESTED_AT + timedelta(seconds=1)
    with pytest.raises(ValidationError, match="captured at request time"):
        AlertEvaluationJobPayload.model_validate(invalid)


def test_evaluator_publishes_or_records_deterministic_suppression() -> None:
    assessment = ready_assessment()
    source = AlertEvaluationJobPayload.build(
        rule=alert_rule(),
        assessment=assessment,
        requested_at=REQUESTED_AT,
    ).source

    published = evaluate_alert(rule=alert_rule(), source=source)
    assert published.evaluation.disposition is AlertEvaluationDisposition.PUBLISHED
    assert published.draft is not None
    assert published.draft.title == alert_rule().name
    assert published.draft.message == alert_rule().description

    disabled = evaluate_alert(
        rule=rebuild_rule(state=AlertRuleState.DISABLED),
        source=source,
    )
    assert disabled.draft is None
    assert disabled.evaluation.suppression_reasons == (AlertSuppressionReason.RULE_DISABLED,)

    unmatched = evaluate_alert(
        rule=rebuild_rule(minimum_confidence="0.90"),
        source=source,
    )
    assert unmatched.draft is None
    assert unmatched.evaluation.suppression_reasons == (
        AlertSuppressionReason.CONDITION_NOT_MATCHED,
    )

    stale_source = AlertEvaluationJobPayload.build(
        rule=alert_rule(),
        assessment=assessment,
        requested_at=assessment.expires_at + timedelta(minutes=1),
    ).source
    stale = evaluate_alert(rule=alert_rule(), source=stale_source)
    assert stale.draft is None
    assert stale.evaluation.suppression_reasons == (
        AlertSuppressionReason.SOURCE_EXPIRED,
        AlertSuppressionReason.SOURCE_NOT_CONSUMABLE,
    )


def test_enqueuer_deduplicates_rule_source_intent_and_preserves_first_time(
    factory: sessionmaker[Session],
) -> None:
    seed_inputs(factory)
    first = enqueue(factory)
    second = enqueue(factory, requested_at=REQUESTED_AT + timedelta(minutes=10))

    assert first.created is True
    assert second.created is False
    assert second.job == first.job
    assert first.job.kind is BackgroundJobKind.ALERT_EVALUATION
    assert first.job.max_attempts == 3
    assert AlertEvaluationJobPayload.model_validate(second.job.payload).requested_at == REQUESTED_AT

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(BackgroundJobRow)) == 1


def test_source_fanout_targets_only_latest_enabled_rule_versions(
    factory: sessionmaker[Session],
) -> None:
    assessment = ready_assessment()
    first = rebuild_rule()
    disabled = rebuild_rule(version=2, state=AlertRuleState.DISABLED)
    with factory.begin() as session:
        seed_assessment(session, assessment)
        SqlAlchemyAlertStore(session).stage_rule_definition(first)

    with factory() as session:
        enqueuer = SqlAlchemyAlertEvaluationEnqueuer(session)
        initial = enqueuer.enqueue_enabled_for_source(
            source_event_id=assessment.assessment_id,
            requested_at=REQUESTED_AT,
        )
    assert len(initial) == 1
    assert initial[0].created is True

    with factory.begin() as session:
        SqlAlchemyAlertStore(session).stage_rule_definition(disabled)
    with factory() as session:
        after_disable = SqlAlchemyAlertEvaluationEnqueuer(session).enqueue_enabled_for_source(
            source_event_id=assessment.assessment_id,
            requested_at=REQUESTED_AT + timedelta(minutes=1),
        )

    assert after_disable == ()


def test_runner_persists_published_outcome_atomically_and_idempotently(
    factory: sessionmaker[Session],
) -> None:
    seed_inputs(factory)
    payload = AlertEvaluationJobPayload.model_validate(enqueue(factory).job.payload)
    runner = SqlAlchemyAlertEvaluationRunner(factory)

    first = runner.run(payload)
    second = runner.run(payload)

    assert second == first
    assert first.disposition is AlertEvaluationDisposition.PUBLISHED
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AlertEvaluationRow)) == 1
        assert session.scalar(select(func.count()).select_from(AlertRow)) == 1
        assert SqlAlchemyAlertStore(session).get_evaluation(first.evaluation_id) == first


def test_runner_persists_non_matching_condition_as_suppression(
    factory: sessionmaker[Session],
) -> None:
    assessment = ready_assessment()
    rule = rebuild_rule(minimum_confidence="0.90")
    with factory.begin() as session:
        seed_assessment(session, assessment)
        SqlAlchemyAlertStore(session).stage_rule_definition(rule)
    with factory() as session:
        queued = SqlAlchemyAlertEvaluationEnqueuer(session).enqueue(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            source_event_id=assessment.assessment_id,
            requested_at=REQUESTED_AT,
        )

    evaluation = SqlAlchemyAlertEvaluationRunner(factory).run(
        AlertEvaluationJobPayload.model_validate(queued.job.payload)
    )

    assert evaluation.disposition is AlertEvaluationDisposition.SUPPRESSED
    assert evaluation.suppression_reasons == (AlertSuppressionReason.CONDITION_NOT_MATCHED,)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AlertEvaluationRow)) == 1
        assert session.scalar(select(func.count()).select_from(AlertRow)) == 0


def test_runner_rolls_back_when_cooperative_cancellation_is_observed(
    factory: sessionmaker[Session],
) -> None:
    seed_inputs(factory)
    payload = AlertEvaluationJobPayload.model_validate(enqueue(factory).job.payload)
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks == 2

    with pytest.raises(AlertEvaluationJobCancelled):
        SqlAlchemyAlertEvaluationRunner(factory).run(
            payload,
            cancellation_requested=cancelled,
        )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AlertEvaluationRow)) == 0
        assert session.scalar(select(func.count()).select_from(AlertRow)) == 0


def test_worker_returns_evaluation_reference_and_rejects_invalid_payload(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_inputs(factory)
    queued = enqueue(factory).job
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)

    with factory() as session:
        completed = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="alert-evaluation-worker",
        ).run_once()

    assert completed is not None
    assert completed.job_id == queued.job_id
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert completed.result_reference is not None
    assert completed.result_reference.startswith("alert-evaluation-")

    invalid = build_alert_evaluation_job(
        rule=alert_rule(),
        assessment=ready_assessment(),
        requested_at=REQUESTED_AT + timedelta(hours=1),
    ).model_copy(
        update={
            "payload": {"invalid": True},
            "idempotency_key": "invalid-alert-evaluation-payload",
        }
    )
    with factory() as session:
        repository = SqlAlchemyBackgroundJobRepository(session)
        repository.enqueue(invalid)
        failed = BackgroundJobWorker(
            repository=repository,
            handlers=build_background_job_handler_registry(),
            worker_id="invalid-alert-evaluation-worker",
        ).run_once()

    assert failed is not None
    assert failed.status is BackgroundJobStatus.FAILED
    assert failed.error_code == "invalid_alert_evaluation_job_payload"


def test_expired_lease_reclaim_reuses_committed_outcome_without_duplicates(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_inputs(factory)
    queued = enqueue(factory).job
    payload = AlertEvaluationJobPayload.model_validate(queued.payload)
    crashed_at = datetime.now(UTC) - timedelta(seconds=2)

    with factory() as session:
        claimed = SqlAlchemyBackgroundJobRepository(session).claim_next(
            worker_id="crashed-alert-worker",
            lease_duration=timedelta(seconds=1),
            now=crashed_at,
        )
        assert claimed is not None
        assert claimed.attempt_count == 1

    committed = SqlAlchemyAlertEvaluationRunner(factory).run(payload)
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)

    with factory() as session:
        completed = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="reclaim-alert-worker",
        ).run_once()

    assert completed is not None
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert completed.attempt_count == 2
    assert completed.result_reference == committed.evaluation_id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AlertEvaluationRow)) == 1
        assert session.scalar(select(func.count()).select_from(AlertRow)) == 1
