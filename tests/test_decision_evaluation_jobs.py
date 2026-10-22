from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from tests.test_context_aware_strategy_evaluation import (
    assessment,
    dataset,
    intent,
    policy,
    seed_assessment,
)
from tests.test_decision_intelligence_persistence import seed_assessment_dependencies
from trd_bot.api import job_handlers
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.core.config import Settings
from trd_bot.db import (
    BackgroundJobRow,
    DatabaseBase,
    DatasetSnapshotRow,
    DecisionCandidateRankingRow,
    DecisionEvaluationIntentRow,
    DecisionPolicyDefinitionRow,
    DecisionPortfolioIntelligenceRow,
    DecisionRiskGateRow,
    DecisionStageOutcomeRow,
    DecisionStrategyEvaluationRow,
    MarketContextFeatureSnapshotRow,
    MarketContextInputManifestRow,
    MarketRegimeAssessmentRow,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyDecisionEvaluationEnqueuer,
    SqlAlchemyDecisionEvaluationRunner,
    SqlAlchemyDecisionIntelligenceStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.decision_intelligence import (
    DecisionDisposition,
    DecisionEvaluationEnqueueResult,
    DecisionEvaluationIntent,
    DecisionEvaluationIntentNotFoundError,
    DecisionEvaluationJobCancelled,
    DecisionEvaluationJobPayload,
    DecisionPolicyDefinition,
    StrategyEvaluationRecord,
    build_decision_evaluation_idempotency_key,
    strategy_context_compatibility_policy_v1,
)
from trd_bot.jobs import BackgroundJobKind, BackgroundJobStatus, BackgroundJobWorker
from trd_bot.market_context import MarketRegimeAssessment
from trd_bot.market_data import InMemoryMarketDataConnectionRepository
from trd_bot.market_data.import_history import InMemoryMarketDataImportRepository
from trd_bot.monitoring import (
    InMemoryArchitectureRecommendationRepository,
    InMemorySystemMetricRepository,
    MonitoringSummaryBuilder,
)
from trd_bot.research import DatasetSnapshot

JOB_REQUESTED_AT = datetime(2026, 10, 19, 12, 25, tzinfo=UTC)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def seed_intent(
    factory: sessionmaker[Session],
) -> tuple[
    DatasetSnapshot,
    MarketRegimeAssessment,
    DecisionPolicyDefinition,
    DecisionEvaluationIntent,
]:
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    evaluation_intent = intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )
    with factory.begin() as session:
        SqlAlchemyDatasetRepository(session).stage(input_dataset)
        seed_assessment_dependencies(session, input_assessment)
        seed_assessment(session, input_assessment)
        store = SqlAlchemyDecisionIntelligenceStore(session)
        store.stage_policy_definition(input_policy)
        store.stage_evaluation_intent(evaluation_intent)
    return input_dataset, input_assessment, input_policy, evaluation_intent


def enqueue(
    factory: sessionmaker[Session],
    *,
    requested_at: datetime = JOB_REQUESTED_AT,
) -> tuple[DecisionEvaluationIntent, DecisionEvaluationEnqueueResult]:
    _, _, _, evaluation_intent = seed_intent(factory)
    with factory() as session:
        result = SqlAlchemyDecisionEvaluationEnqueuer(session).enqueue(
            evaluation_id=evaluation_intent.evaluation_id,
            requested_at=requested_at,
        )
    return evaluation_intent, result


def test_payload_is_pinned_to_intent_and_canonical_compatibility_policy() -> None:
    evaluation_intent = intent()
    payload = DecisionEvaluationJobPayload.build(
        intent=evaluation_intent,
        requested_at=JOB_REQUESTED_AT,
    )
    compatibility = strategy_context_compatibility_policy_v1()

    assert payload.evaluation_id == evaluation_intent.evaluation_id
    assert payload.intent_checksum == evaluation_intent.intent_checksum
    assert payload.compatibility_policy_version == compatibility.policy_version
    assert payload.compatibility_policy_checksum == compatibility.definition_checksum
    assert payload.offline_only is True
    assert payload.external_order_submission_allowed is False

    tampered = payload.model_dump()
    tampered["intent_checksum"] = "0" * 64
    with pytest.raises(ValidationError, match="payload checksum is inconsistent"):
        DecisionEvaluationJobPayload.model_validate(tampered)


def test_enqueuer_deduplicates_intent_and_preserves_first_request(
    factory: sessionmaker[Session],
) -> None:
    _, _, _, evaluation_intent = seed_intent(factory)
    with factory() as session:
        enqueuer = SqlAlchemyDecisionEvaluationEnqueuer(session)
        first = enqueuer.enqueue(
            evaluation_id=evaluation_intent.evaluation_id,
            requested_at=JOB_REQUESTED_AT,
        )
        repeated = enqueuer.enqueue(
            evaluation_id=evaluation_intent.evaluation_id,
            requested_at=JOB_REQUESTED_AT + timedelta(minutes=5),
        )

    assert first.created is True
    assert repeated.created is False
    assert repeated.job == first.job
    assert first.job.kind is BackgroundJobKind.DECISION_EVALUATION
    assert first.job.max_attempts == 3
    assert first.job.idempotency_key == build_decision_evaluation_idempotency_key(evaluation_intent)
    payload = DecisionEvaluationJobPayload.model_validate(repeated.job.payload)
    assert payload.requested_at == JOB_REQUESTED_AT
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(BackgroundJobRow)) == 1


def test_enqueuer_rejects_missing_intent(factory: sessionmaker[Session]) -> None:
    with factory() as session, pytest.raises(DecisionEvaluationIntentNotFoundError):
        SqlAlchemyDecisionEvaluationEnqueuer(session).enqueue(
            evaluation_id="decision-evaluation-0000000000000000",
            requested_at=JOB_REQUESTED_AT,
        )


def test_runner_commits_evidence_atomically_and_idempotently(
    factory: sessionmaker[Session],
) -> None:
    evaluation_intent, queued = enqueue(factory)
    payload = DecisionEvaluationJobPayload.model_validate(queued.job.payload)
    runner = SqlAlchemyDecisionEvaluationRunner(factory)

    first = runner.run(payload)
    repeated = runner.run(payload)

    assert repeated == first
    assert first.evaluation_id == evaluation_intent.evaluation_id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DecisionStageOutcomeRow)) == 4
        assert session.scalar(select(func.count()).select_from(DecisionStrategyEvaluationRow)) == 1
        assert session.scalar(select(func.count()).select_from(DecisionCandidateRankingRow)) == 1
        assert session.scalar(select(func.count()).select_from(DecisionRiskGateRow)) == 1
        assert (
            session.scalar(select(func.count()).select_from(DecisionPortfolioIntelligenceRow)) == 1
        )


def test_runner_rolls_back_evidence_on_cooperative_cancellation(
    factory: sessionmaker[Session],
) -> None:
    _, queued = enqueue(factory)
    payload = DecisionEvaluationJobPayload.model_validate(queued.job.payload)
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks == 6

    with pytest.raises(DecisionEvaluationJobCancelled):
        SqlAlchemyDecisionEvaluationRunner(factory).run(
            payload,
            cancellation_requested=cancelled,
        )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DecisionStageOutcomeRow)) == 0
        assert session.scalar(select(func.count()).select_from(DecisionStrategyEvaluationRow)) == 0
        assert session.scalar(select(func.count()).select_from(DecisionCandidateRankingRow)) == 0
        assert session.scalar(select(func.count()).select_from(DecisionRiskGateRow)) == 0
        assert (
            session.scalar(select(func.count()).select_from(DecisionPortfolioIntelligenceRow)) == 0
        )


def test_worker_retries_transient_failure_then_succeeds_without_duplicate_evidence(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluation_intent, queued = enqueue(factory)
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)
    original_run = SqlAlchemyDecisionEvaluationRunner.run
    calls = 0

    def fail_once(
        self: SqlAlchemyDecisionEvaluationRunner,
        payload: DecisionEvaluationJobPayload,
        *,
        cancellation_requested: Callable[[], bool] = lambda: False,
    ) -> StrategyEvaluationRecord:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SQLAlchemyError("temporary database failure")
        return original_run(
            self,
            payload,
            cancellation_requested=cancellation_requested,
        )

    monkeypatch.setattr(SqlAlchemyDecisionEvaluationRunner, "run", fail_once)

    with factory() as session:
        worker = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="decision-retry-worker",
        )
        first = worker.run_once()
        assert first is not None
        assert first.status is BackgroundJobStatus.QUEUED
        assert first.attempt_count == 1
        completed = worker.run_once(now=first.run_after)

    assert completed is not None
    assert completed.job_id == queued.job.job_id
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert completed.attempt_count == 2
    assert completed.result_reference == evaluation_intent.evaluation_id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DecisionStrategyEvaluationRow)) == 1
        assert session.scalar(select(func.count()).select_from(DecisionCandidateRankingRow)) == 1
        assert session.scalar(select(func.count()).select_from(DecisionRiskGateRow)) == 1
        assert (
            session.scalar(select(func.count()).select_from(DecisionPortfolioIntelligenceRow)) == 1
        )


def test_expired_lease_reclaim_reuses_committed_evidence(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluation_intent, queued = enqueue(factory)
    payload = DecisionEvaluationJobPayload.model_validate(queued.job.payload)
    crashed_at = datetime.now(UTC) - timedelta(seconds=2)

    with factory() as session:
        claimed = SqlAlchemyBackgroundJobRepository(session).claim_next(
            worker_id="crashed-decision-worker",
            lease_duration=timedelta(seconds=1),
            now=crashed_at,
        )
        assert claimed is not None
        assert claimed.attempt_count == 1

    committed = SqlAlchemyDecisionEvaluationRunner(factory).run(payload)
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)
    with factory() as session:
        completed = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="reclaim-decision-worker",
        ).run_once()

    assert completed is not None
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert completed.attempt_count == 2
    assert completed.result_reference == evaluation_intent.evaluation_id
    assert committed.evaluation_id == completed.result_reference
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DecisionStrategyEvaluationRow)) == 1
        assert session.scalar(select(func.count()).select_from(DecisionCandidateRankingRow)) == 1
        assert session.scalar(select(func.count()).select_from(DecisionRiskGateRow)) == 1
        assert (
            session.scalar(select(func.count()).select_from(DecisionPortfolioIntelligenceRow)) == 1
        )


def test_decision_job_is_visible_in_safe_operational_monitoring(
    factory: sessionmaker[Session],
) -> None:
    _, queued = enqueue(factory)
    with factory() as session:
        summary = MonitoringSummaryBuilder().build(
            metrics=InMemorySystemMetricRepository(),
            recommendations=InMemoryArchitectureRecommendationRepository(),
            jobs=SqlAlchemyBackgroundJobRepository(session),
            connections=InMemoryMarketDataConnectionRepository(),
            imports=InMemoryMarketDataImportRepository(),
            generated_at=JOB_REQUESTED_AT,
        )

    assert summary.operations is not None
    visible = next(
        item for item in summary.operations.jobs.recent_jobs if item.job_id == queued.job.job_id
    )
    assert visible.kind is BackgroundJobKind.DECISION_EVALUATION
    assert visible.status is BackgroundJobStatus.QUEUED
    assert "payload" not in visible.model_dump()
    assert "lease_owner" not in visible.model_dump()


@pytest.mark.integration
def test_postgresql_decision_evaluation_worker_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = Settings().test_database_url
    if database_url is None:
        pytest.skip("TRD_BOT_TEST_DATABASE_URL is not configured")
    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "postgresql":
        raise AssertionError("decision job integration tests require PostgreSQL")
    if parsed_url.database != "trd_bot_test":
        raise AssertionError("decision job integration tests may run only against trd_bot_test")

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_database_engine(database_url)
    database_factory = create_session_factory(engine)
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    evaluation_intent = intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )
    job_id: str | None = None

    try:
        with database_factory.begin() as session:
            SqlAlchemyDatasetRepository(session).stage(input_dataset)
            seed_assessment_dependencies(session, input_assessment)
            seed_assessment(session, input_assessment)
            store = SqlAlchemyDecisionIntelligenceStore(session)
            store.stage_policy_definition(input_policy)
            store.stage_evaluation_intent(evaluation_intent)

        with database_factory() as session:
            queued = SqlAlchemyDecisionEvaluationEnqueuer(session).enqueue(
                evaluation_id=evaluation_intent.evaluation_id,
                requested_at=JOB_REQUESTED_AT,
            )
            job_id = queued.job.job_id

        monkeypatch.setattr(job_handlers, "get_session_factory", lambda: database_factory)
        with database_factory() as session:
            completed = BackgroundJobWorker(
                repository=SqlAlchemyBackgroundJobRepository(session),
                handlers=build_background_job_handler_registry(),
                worker_id="postgresql-decision-worker",
            ).run_once()

        assert completed is not None
        assert completed.status is BackgroundJobStatus.SUCCEEDED
        assert completed.result_reference == evaluation_intent.evaluation_id
        with database_factory() as session:
            store = SqlAlchemyDecisionIntelligenceStore(session)
            stored = store.get_strategy_evaluation(evaluation_intent.evaluation_id)
            assert stored is not None
            assert stored.offline_only is True
            assert stored.external_order_submission_allowed is False
            ranking = store.get_candidate_ranking(evaluation_intent.evaluation_id)
            assert ranking is not None
            assert ranking.outcome.disposition is DecisionDisposition.ACCEPTED
            risk_gate = store.get_risk_gate(evaluation_intent.evaluation_id)
            assert risk_gate is not None
            assert risk_gate.outcome.disposition is DecisionDisposition.ACCEPTED
            portfolio = store.get_portfolio_intelligence(evaluation_intent.evaluation_id)
            assert portfolio is not None
            assert portfolio.outcome.disposition is DecisionDisposition.ACCEPTED
    finally:
        with database_factory.begin() as session:
            if job_id is not None:
                session.execute(delete(BackgroundJobRow).where(BackgroundJobRow.job_id == job_id))
            session.execute(
                delete(DecisionPortfolioIntelligenceRow).where(
                    DecisionPortfolioIntelligenceRow.evaluation_id
                    == evaluation_intent.evaluation_id
                )
            )
            session.execute(
                delete(DecisionRiskGateRow).where(
                    DecisionRiskGateRow.evaluation_id == evaluation_intent.evaluation_id
                )
            )
            session.execute(
                delete(DecisionCandidateRankingRow).where(
                    DecisionCandidateRankingRow.evaluation_id == evaluation_intent.evaluation_id
                )
            )
            session.execute(
                delete(DecisionStrategyEvaluationRow).where(
                    DecisionStrategyEvaluationRow.evaluation_id == evaluation_intent.evaluation_id
                )
            )
            session.execute(
                delete(DecisionStageOutcomeRow).where(
                    DecisionStageOutcomeRow.evaluation_id == evaluation_intent.evaluation_id
                )
            )
            session.execute(
                delete(DecisionEvaluationIntentRow).where(
                    DecisionEvaluationIntentRow.evaluation_id == evaluation_intent.evaluation_id
                )
            )
            session.execute(
                delete(DecisionPolicyDefinitionRow).where(
                    DecisionPolicyDefinitionRow.policy_id == input_policy.policy_id
                )
            )
            session.execute(
                delete(MarketRegimeAssessmentRow).where(
                    MarketRegimeAssessmentRow.assessment_id == input_assessment.assessment_id
                )
            )
            session.execute(
                delete(MarketContextFeatureSnapshotRow).where(
                    MarketContextFeatureSnapshotRow.snapshot_id
                    == input_assessment.feature_snapshot_id
                )
            )
            session.execute(
                delete(MarketContextInputManifestRow).where(
                    MarketContextInputManifestRow.manifest_id == input_assessment.input_manifest_id
                )
            )
            session.execute(
                delete(DatasetSnapshotRow).where(
                    DatasetSnapshotRow.dataset_id == input_dataset.dataset_id
                )
            )
        engine.dispose()
