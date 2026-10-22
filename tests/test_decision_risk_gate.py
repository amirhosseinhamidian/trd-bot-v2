from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from tests.test_context_aware_strategy_evaluation import (
    assessment,
    dataset,
    intent,
    policy,
    seed_assessment,
)
from tests.test_decision_intelligence_persistence import seed_assessment_dependencies
from trd_bot.core.config import Settings
from trd_bot.db import (
    DatabaseBase,
    DatasetSnapshotRow,
    DecisionCandidateRankingRow,
    DecisionEvaluationIntentRow,
    DecisionPolicyDefinitionRow,
    DecisionRiskGateRow,
    DecisionStageOutcomeRow,
    DecisionStrategyEvaluationRow,
    MarketContextFeatureSnapshotRow,
    MarketContextInputManifestRow,
    MarketRegimeAssessmentRow,
    SqlAlchemyContextAwareStrategyEvaluator,
    SqlAlchemyDatasetRepository,
    SqlAlchemyDecisionCandidateRanker,
    SqlAlchemyDecisionIntelligenceStore,
    SqlAlchemyDecisionRiskGate,
    create_database_engine,
    create_session_factory,
)
from trd_bot.decision_intelligence import (
    DecisionCandidateRankingRecord,
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionReasonCode,
    DecisionRiskDecision,
    DecisionRiskGateRecord,
    DecisionRiskIntegrityError,
    DecisionRiskPolicyV1,
    DecisionStage,
    StrategyEvaluationRecord,
    build_decision_candidate_ranking,
    decision_risk_policy_v1,
    evaluate_decision_risk,
    evaluate_strategy_intent,
)
from trd_bot.research import DatasetSnapshot
from trd_bot.strategies import build_default_strategy_registry

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def ranking_fixture(
    *,
    low_context_confidence: bool = False,
) -> tuple[
    DecisionEvaluationIntent,
    DatasetSnapshot,
    StrategyEvaluationRecord,
    DecisionCandidateRankingRecord,
]:
    input_dataset = dataset()
    evaluation_intent = intent(
        input_dataset=input_dataset,
        input_assessment=(
            assessment(confidence=Decimal("0.60")) if low_context_confidence else assessment()
        ),
    )
    strategy_record = evaluate_strategy_intent(
        intent=evaluation_intent,
        dataset=input_dataset,
        registry=build_default_strategy_registry(),
    )
    ranking = build_decision_candidate_ranking(
        intent=evaluation_intent,
        strategy_evaluation=strategy_record,
        dataset=input_dataset,
    )
    return evaluation_intent, input_dataset, strategy_record, ranking


def seed_accepted_ranking(factory: sessionmaker[Session]) -> str:
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
        SqlAlchemyContextAwareStrategyEvaluator(session).evaluate(evaluation_intent.evaluation_id)
        ranking, _ = SqlAlchemyDecisionCandidateRanker(session).rank(
            evaluation_intent.evaluation_id
        )
        assert ranking.outcome.disposition is DecisionDisposition.ACCEPTED
    return evaluation_intent.evaluation_id


def test_risk_policy_is_frozen_and_tamper_evident() -> None:
    risk_policy = decision_risk_policy_v1()

    assert risk_policy.reference_equity == Decimal("10000.00000000")
    assert risk_policy.max_risk_fraction == Decimal("0.010000")
    assert risk_policy.max_notional_fraction == Decimal("0.100000")
    assert risk_policy.minimum_ranking_score == Decimal("0.300000")
    assert risk_policy.minimum_reward_risk_ratio == Decimal("1.500000")
    assert risk_policy.definition_checksum == (
        "519ea991781ee8e6416ebf2a6786ff9f6448f357d744dc1475baa87c913f91dd"
    )

    payload = risk_policy.model_dump()
    payload["definition_checksum"] = "0" * 64
    with pytest.raises(ValidationError, match="policy checksum is inconsistent"):
        DecisionRiskPolicyV1.model_validate(payload)


def test_top_candidate_is_approved_with_capped_offline_position_size() -> None:
    _, _, _, ranking = ranking_fixture()

    first = evaluate_decision_risk(ranking=ranking)
    repeated = evaluate_decision_risk(ranking=ranking)

    assert repeated == first
    assert first.outcome.disposition is DecisionDisposition.ACCEPTED
    assert first.approved_candidate_id == ranking.top_candidate_id
    assert first.assessment.decision is DecisionRiskDecision.APPROVED
    assert all(item.passed for item in first.assessment.checks)
    sizing = first.assessment.position_sizing
    assert sizing is not None
    assert sizing.reference_equity == Decimal("10000.00000000")
    assert sizing.risk_budget == Decimal("100.00000000")
    assert sizing.notional_cap == Decimal("1000.00000000")
    assert sizing.reward_risk_ratio == Decimal("2.000000")
    assert sizing.quantity == Decimal("9.70873786")
    assert sizing.notional == Decimal("999.99999958")
    assert sizing.maximum_loss == Decimal("9.70873786")
    assert sizing.offline_only is True
    assert sizing.external_order_submission_allowed is False
    assert DecisionRiskGateRecord.model_validate_json(first.model_dump_json()) == first


def test_low_ranking_score_is_rejected_without_position_sizing() -> None:
    _, _, _, ranking = ranking_fixture(low_context_confidence=True)

    record = evaluate_decision_risk(ranking=ranking)

    assert ranking.entries[0].total_score < Decimal("0.300000")
    assert record.outcome.disposition is DecisionDisposition.REJECTED
    assert record.outcome.reason_codes == (DecisionReasonCode.RISK_POLICY_REJECTED,)
    assert record.assessment.decision is DecisionRiskDecision.REJECTED
    assert record.assessment.position_sizing is None
    assert record.approved_candidate_id is None
    score_check = next(
        item for item in record.assessment.checks if item.name.value == "ranking_score"
    )
    assert score_check.passed is False


def test_risk_gate_rejects_unaccepted_candidate_ranking() -> None:
    _, _, _, ranking = ranking_fixture()
    rejected_ranking = ranking.model_copy(
        update={
            "outcome": ranking.outcome.model_copy(
                update={"disposition": DecisionDisposition.DEFERRED}
            )
        }
    )

    with pytest.raises(DecisionRiskIntegrityError, match="accepted candidate ranking"):
        evaluate_decision_risk(ranking=rejected_ranking)


def test_risk_gate_detects_payload_tampering() -> None:
    _, _, _, ranking = ranking_fixture()
    record = evaluate_decision_risk(ranking=ranking)
    payload = record.model_dump()
    assert payload["assessment"]["position_sizing"] is not None
    payload["assessment"]["position_sizing"]["quantity"] = Decimal("999")

    with pytest.raises(ValidationError):
        DecisionRiskGateRecord.model_validate(payload)


def test_sqlalchemy_risk_gate_persists_atomic_idempotent_evidence(
    factory: sessionmaker[Session],
) -> None:
    evaluation_id = seed_accepted_ranking(factory)

    with factory.begin() as session:
        gate = SqlAlchemyDecisionRiskGate(session)
        first, first_created = gate.evaluate(evaluation_id)
        repeated, repeated_created = gate.evaluate(evaluation_id)

        assert first_created is True
        assert repeated_created is False
        assert repeated == first

    with factory() as session:
        store = SqlAlchemyDecisionIntelligenceStore(session)
        assert store.get_risk_gate(evaluation_id) == first
        assert session.scalar(select(func.count()).select_from(DecisionRiskGateRow)) == 1
        outcomes = store.list_stage_outcomes(evaluation_id)
        assert tuple(item.stage.value for item in outcomes) == (
            "strategy_evaluation",
            "candidate_ranking",
            "risk_gate",
        )


def test_sqlalchemy_risk_gate_rolls_back_with_caller_transaction(
    factory: sessionmaker[Session],
) -> None:
    evaluation_id = seed_accepted_ranking(factory)

    with pytest.raises(RuntimeError, match="rollback"), factory.begin() as session:
        SqlAlchemyDecisionRiskGate(session).evaluate(evaluation_id)
        raise RuntimeError("rollback")

    with factory() as session:
        assert session.get(DecisionRiskGateRow, evaluation_id) is None
        assert (
            SqlAlchemyDecisionIntelligenceStore(session).get_stage_outcome(
                evaluation_id,
                stage=DecisionStage.RISK_GATE,
            )
            is None
        )


@pytest.mark.integration
def test_postgresql_risk_gate_round_trip() -> None:
    database_url = Settings().test_database_url
    if database_url is None:
        pytest.skip("TRD_BOT_TEST_DATABASE_URL is not configured")
    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "postgresql":
        raise AssertionError("risk gate integration tests require PostgreSQL")
    if parsed_url.database != "trd_bot_test":
        raise AssertionError("risk gate integration tests may run only against trd_bot_test")

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    evaluation_intent = intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )

    try:
        with factory.begin() as session:
            SqlAlchemyDatasetRepository(session).stage(input_dataset)
            seed_assessment_dependencies(session, input_assessment)
            seed_assessment(session, input_assessment)
            store = SqlAlchemyDecisionIntelligenceStore(session)
            store.stage_policy_definition(input_policy)
            store.stage_evaluation_intent(evaluation_intent)
            SqlAlchemyContextAwareStrategyEvaluator(session).evaluate(
                evaluation_intent.evaluation_id
            )
            SqlAlchemyDecisionCandidateRanker(session).rank(evaluation_intent.evaluation_id)
            first, created = SqlAlchemyDecisionRiskGate(session).evaluate(
                evaluation_intent.evaluation_id
            )
            assert created is True

        with factory() as session:
            stored = SqlAlchemyDecisionIntelligenceStore(session).get_risk_gate(
                evaluation_intent.evaluation_id
            )
            assert stored == first
            assert stored is not None
            assert stored.outcome.disposition is DecisionDisposition.ACCEPTED
            assert stored.assessment.position_sizing is not None
            assert stored.offline_only is True
            assert stored.external_order_submission_allowed is False
    finally:
        with factory.begin() as session:
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
