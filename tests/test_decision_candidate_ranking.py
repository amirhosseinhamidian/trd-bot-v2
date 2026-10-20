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
    DecisionStageOutcomeRow,
    DecisionStrategyEvaluationRow,
    MarketContextFeatureSnapshotRow,
    MarketContextInputManifestRow,
    MarketRegimeAssessmentRow,
    SqlAlchemyContextAwareStrategyEvaluator,
    SqlAlchemyDatasetRepository,
    SqlAlchemyDecisionCandidateRanker,
    SqlAlchemyDecisionIntelligenceStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.decision_intelligence import (
    DecisionCandidateIntegrityError,
    DecisionCandidatePolicyV1,
    DecisionCandidateRankingRecord,
    DecisionDisposition,
    DecisionReasonCode,
    DecisionStage,
    build_decision_candidate_ranking,
    decision_candidate_policy_v1,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def seed_accepted_evaluation(
    factory: sessionmaker[Session],
) -> str:
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
        strategy_record, _ = SqlAlchemyContextAwareStrategyEvaluator(session).evaluate(
            evaluation_intent.evaluation_id
        )
        assert strategy_record.outcome.disposition is DecisionDisposition.ACCEPTED
    return evaluation_intent.evaluation_id


def test_candidate_policy_is_frozen_and_tamper_evident() -> None:
    candidate_policy = decision_candidate_policy_v1()

    assert candidate_policy.validity_candles == 4
    assert candidate_policy.reward_risk_ratio == Decimal("2.000000")
    assert candidate_policy.signal_strength_weight == Decimal("0.600000")
    assert candidate_policy.context_confidence_weight == Decimal("0.400000")
    assert candidate_policy.definition_checksum == (
        "1a79b9f9978919bff46914bcc9375c9860a47bd7cd35419c4d59e6d9fddbb7d1"
    )

    payload = candidate_policy.model_dump()
    payload["definition_checksum"] = "0" * 64
    with pytest.raises(ValidationError, match="policy checksum is inconsistent"):
        DecisionCandidatePolicyV1.model_validate(payload)


def test_accepted_strategy_evidence_builds_deterministic_ranked_candidate() -> None:
    input_dataset = dataset()
    evaluation_intent = intent(input_dataset=input_dataset)
    from trd_bot.decision_intelligence import evaluate_strategy_intent
    from trd_bot.strategies import build_default_strategy_registry

    strategy_record = evaluate_strategy_intent(
        intent=evaluation_intent,
        dataset=input_dataset,
        registry=build_default_strategy_registry(),
    )

    first = build_decision_candidate_ranking(
        intent=evaluation_intent,
        strategy_evaluation=strategy_record,
        dataset=input_dataset,
    )
    repeated = build_decision_candidate_ranking(
        intent=evaluation_intent,
        strategy_evaluation=strategy_record,
        dataset=input_dataset,
    )

    assert repeated == first
    assert first.outcome.stage is DecisionStage.CANDIDATE_RANKING
    assert first.outcome.disposition is DecisionDisposition.ACCEPTED
    assert first.source_signal_count == 1
    assert first.candidate_count == 1
    assert first.excluded_signal_count == 0
    assert first.top_candidate_id == first.entries[0].candidate.candidate_id
    candidate = first.entries[0].candidate
    source_candle = input_dataset.candles[-1]
    assert candidate.signal_id == strategy_record.signals[0].signal_id
    assert candidate.trade_plan.entry_price == source_candle.close_price
    assert candidate.trade_plan.invalidation_price == source_candle.low_price
    assert candidate.trade_plan.target_price == (
        source_candle.close_price
        + (source_candle.close_price - source_candle.low_price) * Decimal("2")
    )
    assert candidate.constructed_at == evaluation_intent.requested_at
    assert candidate.valid_until == (
        evaluation_intent.requested_at + input_dataset.timeframe.duration * 4
    )
    assert first.offline_only is True
    assert first.external_order_submission_allowed is False
    assert DecisionCandidateRankingRecord.model_validate_json(first.model_dump_json()) == first


def test_candidate_ranking_rejects_unaccepted_or_mismatched_lineage() -> None:
    input_dataset = dataset()
    evaluation_intent = intent(input_dataset=input_dataset)
    from trd_bot.decision_intelligence import evaluate_strategy_intent
    from trd_bot.strategies import build_default_strategy_registry

    strategy_record = evaluate_strategy_intent(
        intent=evaluation_intent,
        dataset=input_dataset,
        registry=build_default_strategy_registry(),
    )
    rejected = strategy_record.model_copy(
        update={
            "outcome": strategy_record.outcome.model_copy(
                update={"disposition": DecisionDisposition.REJECTED}
            )
        }
    )
    with pytest.raises(DecisionCandidateIntegrityError, match="accepted strategy"):
        build_decision_candidate_ranking(
            intent=evaluation_intent,
            strategy_evaluation=rejected,
            dataset=input_dataset,
        )

    other_dataset = dataset(closes=(4, 3, 2, 3, 4))
    with pytest.raises(DecisionCandidateIntegrityError, match="pinned intent"):
        build_decision_candidate_ranking(
            intent=evaluation_intent,
            strategy_evaluation=strategy_record,
            dataset=other_dataset,
        )


def test_unconstructable_signal_is_deferred_without_fabricated_candidate() -> None:
    from trd_bot.decision_intelligence import (
        DecisionStageOutcome,
        StrategyEvaluationRecord,
        decision_candidate_policy_v1,
        strategy_context_compatibility_policy_v1,
    )
    from trd_bot.research import DatasetBuilder
    from trd_bot.strategies import SignalDirection, StrategySignal, build_signal_id

    original = dataset()
    source_candle = original.candles[-1].model_copy(
        update={
            "open_price": Decimal("1.5"),
            "high_price": Decimal("3"),
            "low_price": Decimal("0.5"),
            "close_price": Decimal("1"),
        }
    )
    input_dataset = DatasetBuilder().build(
        name="Unconstructable short candidate",
        candles=(*original.candles[:-1], source_candle),
        created_at=original.created_at,
    )
    evaluation_intent = intent(input_dataset=input_dataset)
    signal = StrategySignal(
        signal_id=build_signal_id(
            strategy_name=evaluation_intent.strategy.strategy_name,
            strategy_version=evaluation_intent.strategy.strategy_version,
            dataset_id=input_dataset.dataset_id,
            candle_close_time=source_candle.close_time,
            direction=SignalDirection.SHORT,
        ),
        strategy_name=evaluation_intent.strategy.strategy_name,
        strategy_version=evaluation_intent.strategy.strategy_version,
        dataset_id=input_dataset.dataset_id,
        pair=input_dataset.pair,
        timeframe=input_dataset.timeframe,
        candle_open_time=source_candle.open_time,
        candle_close_time=source_candle.close_time,
        generated_at=source_candle.close_time,
        direction=SignalDirection.SHORT,
        score=Decimal("-0.8"),
        reason="Synthetic short signal with a non-positive target.",
    )
    strategy_record = StrategyEvaluationRecord.build(
        outcome=DecisionStageOutcome.build(
            evaluation_id=evaluation_intent.evaluation_id,
            stage=DecisionStage.STRATEGY_EVALUATION,
            disposition=DecisionDisposition.ACCEPTED,
            reason_codes=(),
            evaluated_at=evaluation_intent.requested_at,
        ),
        compatibility_policy=strategy_context_compatibility_policy_v1(),
        signals=(signal,),
    )

    record = build_decision_candidate_ranking(
        intent=evaluation_intent,
        strategy_evaluation=strategy_record,
        dataset=input_dataset,
        policy=decision_candidate_policy_v1(),
    )

    assert record.outcome.disposition is DecisionDisposition.DEFERRED
    assert record.outcome.reason_codes == (DecisionReasonCode.CANDIDATE_NOT_SELECTABLE,)
    assert record.candidate_count == 0
    assert record.excluded_signal_count == 1
    assert record.entries == ()
    assert record.top_candidate_id is None


def test_ranking_record_detects_payload_tampering() -> None:
    input_dataset = dataset()
    evaluation_intent = intent(input_dataset=input_dataset)
    from trd_bot.decision_intelligence import evaluate_strategy_intent
    from trd_bot.strategies import build_default_strategy_registry

    strategy_record = evaluate_strategy_intent(
        intent=evaluation_intent,
        dataset=input_dataset,
        registry=build_default_strategy_registry(),
    )
    record = build_decision_candidate_ranking(
        intent=evaluation_intent,
        strategy_evaluation=strategy_record,
        dataset=input_dataset,
    )
    payload = record.model_dump()
    payload["entries"][0]["total_score"] = Decimal("0.000001")
    with pytest.raises(ValidationError):
        DecisionCandidateRankingRecord.model_validate(payload)


def test_sqlalchemy_ranker_persists_atomic_idempotent_evidence(
    factory: sessionmaker[Session],
) -> None:
    evaluation_id = seed_accepted_evaluation(factory)

    with factory.begin() as session:
        ranker = SqlAlchemyDecisionCandidateRanker(session)
        first, first_created = ranker.rank(evaluation_id)
        repeated, repeated_created = ranker.rank(evaluation_id)

        assert first_created is True
        assert repeated_created is False
        assert repeated == first

    with factory() as session:
        store = SqlAlchemyDecisionIntelligenceStore(session)
        assert store.get_candidate_ranking(evaluation_id) == first
        assert session.scalar(select(func.count()).select_from(DecisionCandidateRankingRow)) == 1
        outcomes = store.list_stage_outcomes(evaluation_id)
        assert tuple(item.stage for item in outcomes) == (
            DecisionStage.STRATEGY_EVALUATION,
            DecisionStage.CANDIDATE_RANKING,
        )


def test_candidate_ranking_rolls_back_with_caller_transaction(
    factory: sessionmaker[Session],
) -> None:
    evaluation_id = seed_accepted_evaluation(factory)

    with pytest.raises(RuntimeError, match="rollback"), factory.begin() as session:
        SqlAlchemyDecisionCandidateRanker(session).rank(evaluation_id)
        raise RuntimeError("rollback")

    with factory() as session:
        assert session.get(DecisionCandidateRankingRow, evaluation_id) is None
        assert (
            SqlAlchemyDecisionIntelligenceStore(session).get_stage_outcome(
                evaluation_id,
                stage=DecisionStage.CANDIDATE_RANKING,
            )
            is None
        )


@pytest.mark.integration
def test_postgresql_candidate_ranking_round_trip() -> None:
    database_url = Settings().test_database_url
    if database_url is None:
        pytest.skip("TRD_BOT_TEST_DATABASE_URL is not configured")
    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "postgresql":
        raise AssertionError("candidate ranking integration tests require PostgreSQL")
    if parsed_url.database != "trd_bot_test":
        raise AssertionError(
            "candidate ranking integration tests may run only against trd_bot_test"
        )

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
            first, created = SqlAlchemyDecisionCandidateRanker(session).rank(
                evaluation_intent.evaluation_id
            )
            assert created is True

        with factory() as session:
            stored = SqlAlchemyDecisionIntelligenceStore(session).get_candidate_ranking(
                evaluation_intent.evaluation_id
            )
            assert stored == first
            assert stored is not None
            assert stored.outcome.disposition is DecisionDisposition.ACCEPTED
            assert stored.offline_only is True
            assert stored.external_order_submission_allowed is False
    finally:
        with factory.begin() as session:
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
