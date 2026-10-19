from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from trd_bot.core.config import Settings
from trd_bot.db import (
    DatabaseBase,
    DatasetSnapshotRow,
    DecisionEvaluationIntentRow,
    DecisionPolicyDefinitionRow,
    DecisionStageOutcomeRow,
    MarketContextFeatureSnapshotRow,
    MarketContextInputManifestRow,
    MarketRegimeAssessmentRow,
    SqlAlchemyDatasetRepository,
    SqlAlchemyDecisionIntelligenceStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.decision_intelligence import (
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionMode,
    DecisionPolicyDefinition,
    DecisionPolicyState,
    DecisionReasonCode,
    DecisionStage,
    DecisionStageOutcome,
    build_decision_evaluation_idempotency_key,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextEvidence,
    MarketContextProductView,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
    build_market_regime_assessment_id,
)
from trd_bot.research import DatasetBuilder, DatasetSnapshot
from trd_bot.strategies import build_default_strategy_registry

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"
AS_OF = datetime(2026, 10, 19, 12, tzinfo=UTC)
REQUESTED_AT = AS_OF + timedelta(minutes=20)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def dataset() -> DatasetSnapshot:
    candles = tuple(
        OHLCVCandle(
            source=SOURCE,
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=AS_OF - timedelta(hours=3 - index),
            close_time=AS_OF - timedelta(hours=2 - index),
            received_at=AS_OF - timedelta(hours=2 - index) + timedelta(minutes=1),
            open_price=Decimal(100 + index),
            high_price=Decimal(102 + index),
            low_price=Decimal(99 + index),
            close_price=Decimal(101 + index),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index in range(3)
    )
    return DatasetBuilder().build(
        name="Decision persistence fixture",
        candles=candles,
        created_at=AS_OF + timedelta(minutes=2),
    )


def assessment() -> MarketRegimeAssessment:
    input_checksum = "a" * 64
    return MarketRegimeAssessment(
        assessment_id=build_market_regime_assessment_id(
            source=SOURCE,
            pair=PAIR,
            as_of=AS_OF,
            input_checksum=input_checksum,
            feature_set_version="market-context-features-v1",
            algorithm_version="market-regime-v1",
        ),
        source=SOURCE,
        pair=PAIR,
        as_of=AS_OF,
        input_manifest_id=f"market-context-input-{input_checksum[:16]}",
        input_checksum=input_checksum,
        feature_set_version="market-context-features-v1",
        feature_set_checksum="b" * 64,
        feature_snapshot_id="market-context-features-cccccccccccccccc",
        feature_snapshot_checksum="c" * 64,
        algorithm_version="market-regime-v1",
        status=MarketContextAssessmentStatus.READY,
        trend=MarketTrendRegime.TRENDING_UP,
        volatility=MarketVolatilityRegime.NORMAL,
        confidence=Decimal("0.82"),
        evidence=(
            MarketContextEvidence(
                feature_key="trend_slope_1h",
                timeframe=Timeframe.HOUR_1,
                value=Decimal("0.013"),
                calculation_version="trend-slope-v1",
                window_reference_checksums=("d" * 64,),
            ),
        ),
        assessed_at=AS_OF + timedelta(minutes=1),
        expires_at=AS_OF + timedelta(hours=1),
    )


def policy(*, version: int = 1) -> DecisionPolicyDefinition:
    return DecisionPolicyDefinition.build(
        policy_key="default-context-aware-decision",
        policy_version=version,
        name="Default context-aware decision policy",
        description="Admit only traceable offline strategy decisions.",
        state=DecisionPolicyState.ENABLED,
        allowed_modes=tuple(DecisionMode),
        created_at=AS_OF + timedelta(minutes=version + 1),
    )


def evaluation_intent(
    *,
    input_dataset: DatasetSnapshot | None = None,
    input_assessment: MarketRegimeAssessment | None = None,
    input_policy: DecisionPolicyDefinition | None = None,
) -> DecisionEvaluationIntent:
    strategy = build_default_strategy_registry().get_metadata(
        name="sma-crossover",
        version="1.0.0",
    )
    assert strategy is not None
    context = MarketContextProductView.from_assessment(
        input_assessment or assessment(),
        evaluated_at=REQUESTED_AT,
    )
    return DecisionEvaluationIntent.build(
        mode=DecisionMode.SHADOW,
        dataset=input_dataset or dataset(),
        strategy=strategy,
        strategy_parameters={"slow_period": 21, "fast_period": 9},
        market_context=context,
        policy=input_policy or policy(),
        requested_at=REQUESTED_AT,
    )


def seed_assessment(session: Session, value: MarketRegimeAssessment) -> None:
    session.add(
        MarketRegimeAssessmentRow(
            assessment_id=value.assessment_id,
            schema_version=value.schema_version,
            manifest_id=value.input_manifest_id,
            feature_snapshot_id=value.feature_snapshot_id,
            source=value.source,
            base_asset=value.pair.base_asset,
            quote_asset=value.pair.quote_asset,
            market_type=value.pair.market_type.value,
            as_of=value.as_of,
            input_checksum=value.input_checksum,
            feature_set_version=value.feature_set_version,
            feature_set_checksum=value.feature_set_checksum,
            feature_snapshot_checksum=value.feature_snapshot_checksum,
            algorithm_version=value.algorithm_version,
            status=value.status.value,
            trend=value.trend.value,
            volatility=value.volatility.value,
            confidence=value.confidence,
            evidence_count=len(value.evidence),
            issue_count=len(value.issue_codes),
            payload_json=value.model_dump_json(),
            assessed_at=value.assessed_at,
            expires_at=value.expires_at,
        )
    )


def seed_assessment_dependencies(
    session: Session,
    value: MarketRegimeAssessment,
) -> None:
    session.add(
        MarketContextInputManifestRow(
            manifest_id=value.input_manifest_id,
            schema_version="market-context-input-manifest-v1",
            policy_version="market-context-alignment-v1",
            source=value.source,
            base_asset=value.pair.base_asset,
            quote_asset=value.pair.quote_asset,
            market_type=value.pair.market_type.value,
            as_of=value.as_of,
            input_checksum=value.input_checksum,
            window_count=3,
            payload_json="{}",
            created_at=value.assessed_at,
        )
    )
    assert value.feature_snapshot_id is not None
    assert value.feature_snapshot_checksum is not None
    session.add(
        MarketContextFeatureSnapshotRow(
            snapshot_id=value.feature_snapshot_id,
            schema_version="market-context-feature-snapshot-v1",
            manifest_id=value.input_manifest_id,
            source=value.source,
            base_asset=value.pair.base_asset,
            quote_asset=value.pair.quote_asset,
            market_type=value.pair.market_type.value,
            as_of=value.as_of,
            input_checksum=value.input_checksum,
            feature_set_version=value.feature_set_version,
            feature_set_checksum=value.feature_set_checksum,
            feature_count=len(value.evidence),
            snapshot_checksum=value.feature_snapshot_checksum,
            payload_json="{}",
            calculated_at=value.assessed_at,
        )
    )


def seed_intent_lineage(
    session: Session,
    *,
    input_dataset: DatasetSnapshot,
    input_assessment: MarketRegimeAssessment,
    input_policy: DecisionPolicyDefinition,
) -> SqlAlchemyDecisionIntelligenceStore:
    SqlAlchemyDatasetRepository(session).stage(input_dataset)
    seed_assessment(session, input_assessment)
    store = SqlAlchemyDecisionIntelligenceStore(session)
    store.stage_policy_definition(input_policy)
    session.flush()
    return store


def test_policy_versions_are_durable_idempotent_and_contiguous() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    first = policy()
    second = policy(version=2)
    skipped = policy(version=3)

    try:
        with factory.begin() as session:
            store = SqlAlchemyDecisionIntelligenceStore(session)
            assert store.stage_policy_definition(first) == (first, True)
            assert store.stage_policy_definition(first) == (first, False)
            with pytest.raises(ValueError, match="immediate predecessor"):
                store.stage_policy_definition(skipped)
            assert store.stage_policy_definition(second) == (second, True)

        with factory() as session:
            store = SqlAlchemyDecisionIntelligenceStore(session)
            assert store.get_policy_definition(first.policy_id, 1) == first
            assert store.get_latest_policy_definition(first.policy_id) == second
            assert (
                session.scalar(select(func.count()).select_from(DecisionPolicyDefinitionRow)) == 2
            )
    finally:
        engine.dispose()


def test_intent_is_durable_idempotent_and_resolves_by_queue_key() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    intent = evaluation_intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )

    try:
        with factory.begin() as session:
            store = seed_intent_lineage(
                session,
                input_dataset=input_dataset,
                input_assessment=input_assessment,
                input_policy=input_policy,
            )
            assert store.stage_evaluation_intent(intent) == (intent, True)
            assert store.stage_evaluation_intent(intent) == (intent, False)

        with factory() as session:
            store = SqlAlchemyDecisionIntelligenceStore(session)
            key = build_decision_evaluation_idempotency_key(intent)
            assert store.get_evaluation_intent(intent.evaluation_id) == intent
            assert store.get_evaluation_intent_by_idempotency_key(key) == intent
            assert (
                session.scalar(select(func.count()).select_from(DecisionEvaluationIntentRow)) == 1
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("seed_dataset", "seed_context", "seed_policy", "message"),
    (
        (False, True, True, "dataset does not exist"),
        (True, False, True, "market context does not exist"),
        (True, True, False, "policy version does not exist"),
    ),
)
def test_intent_requires_all_persisted_lineage(
    seed_dataset: bool,
    seed_context: bool,
    seed_policy: bool,
    message: str,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    intent = evaluation_intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )

    try:
        with factory() as session:
            if seed_dataset:
                SqlAlchemyDatasetRepository(session).stage(input_dataset)
            if seed_context:
                seed_assessment(session, input_assessment)
            store = SqlAlchemyDecisionIntelligenceStore(session)
            if seed_policy:
                store.stage_policy_definition(input_policy)
            session.flush()

            with pytest.raises(ValueError, match=message):
                store.stage_evaluation_intent(intent)
            assert session.get(DecisionEvaluationIntentRow, intent.evaluation_id) is None
    finally:
        engine.dispose()


def test_stage_outcomes_are_append_only_ordered_and_idempotent() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    intent = evaluation_intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )
    strategy_outcome = DecisionStageOutcome.build(
        evaluation_id=intent.evaluation_id,
        stage=DecisionStage.STRATEGY_EVALUATION,
        disposition=DecisionDisposition.ACCEPTED,
        reason_codes=(),
        evaluated_at=REQUESTED_AT + timedelta(seconds=1),
    )
    ranking_outcome = DecisionStageOutcome.build(
        evaluation_id=intent.evaluation_id,
        stage=DecisionStage.CANDIDATE_RANKING,
        disposition=DecisionDisposition.DEFERRED,
        reason_codes=(DecisionReasonCode.SIGNAL_NEUTRAL,),
        evaluated_at=REQUESTED_AT + timedelta(seconds=2),
    )

    try:
        with factory.begin() as session:
            store = seed_intent_lineage(
                session,
                input_dataset=input_dataset,
                input_assessment=input_assessment,
                input_policy=input_policy,
            )
            store.stage_evaluation_intent(intent)
            assert store.stage_outcome(strategy_outcome) == (strategy_outcome, True)
            assert store.stage_outcome(strategy_outcome) == (strategy_outcome, False)
            assert store.stage_outcome(ranking_outcome) == (ranking_outcome, True)

        with factory() as session:
            store = SqlAlchemyDecisionIntelligenceStore(session)
            assert store.list_stage_outcomes(intent.evaluation_id) == (
                strategy_outcome,
                ranking_outcome,
            )
            assert session.scalar(select(func.count()).select_from(DecisionStageOutcomeRow)) == 2
    finally:
        engine.dispose()


def test_stage_outcome_rejects_skipped_or_terminal_predecessor() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    intent = evaluation_intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )
    ranking = DecisionStageOutcome.build(
        evaluation_id=intent.evaluation_id,
        stage=DecisionStage.CANDIDATE_RANKING,
        disposition=DecisionDisposition.ACCEPTED,
        reason_codes=(),
        evaluated_at=REQUESTED_AT + timedelta(seconds=2),
    )
    rejected_strategy = DecisionStageOutcome.build(
        evaluation_id=intent.evaluation_id,
        stage=DecisionStage.STRATEGY_EVALUATION,
        disposition=DecisionDisposition.REJECTED,
        reason_codes=(DecisionReasonCode.STRATEGY_CONTEXT_INCOMPATIBLE,),
        evaluated_at=REQUESTED_AT + timedelta(seconds=1),
    )

    try:
        with factory.begin() as session:
            store = seed_intent_lineage(
                session,
                input_dataset=input_dataset,
                input_assessment=input_assessment,
                input_policy=input_policy,
            )
            store.stage_evaluation_intent(intent)
            with pytest.raises(ValueError, match="immediate predecessor"):
                store.stage_outcome(ranking)
            store.stage_outcome(rejected_strategy)
            with pytest.raises(ValueError, match="accepted immediate predecessor"):
                store.stage_outcome(ranking)
    finally:
        engine.dispose()


def test_caller_rollback_removes_intent_and_outcome_atomically() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    intent = evaluation_intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )
    outcome = DecisionStageOutcome.build(
        evaluation_id=intent.evaluation_id,
        stage=DecisionStage.STRATEGY_EVALUATION,
        disposition=DecisionDisposition.ACCEPTED,
        reason_codes=(),
        evaluated_at=REQUESTED_AT + timedelta(seconds=1),
    )

    try:
        with factory.begin() as session:
            store = seed_intent_lineage(
                session,
                input_dataset=input_dataset,
                input_assessment=input_assessment,
                input_policy=input_policy,
            )

        with pytest.raises(RuntimeError, match="rollback"), factory.begin() as session:
            store = SqlAlchemyDecisionIntelligenceStore(session)
            store.stage_evaluation_intent(intent)
            store.stage_outcome(outcome)
            raise RuntimeError("force rollback")

        with factory() as session:
            assert session.get(DecisionEvaluationIntentRow, intent.evaluation_id) is None
            assert session.get(DecisionStageOutcomeRow, outcome.outcome_id) is None
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgresql_decision_evidence_round_trip() -> None:
    database_url = Settings().test_database_url
    if database_url is None:
        pytest.skip("TRD_BOT_TEST_DATABASE_URL is not configured")
    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "postgresql":
        raise AssertionError("decision integration tests require PostgreSQL")
    if parsed_url.database != "trd_bot_test":
        raise AssertionError("decision integration tests may run only against trd_bot_test")

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    input_dataset = dataset()
    input_assessment = assessment()
    input_policy = policy()
    intent = evaluation_intent(
        input_dataset=input_dataset,
        input_assessment=input_assessment,
        input_policy=input_policy,
    )
    outcome = DecisionStageOutcome.build(
        evaluation_id=intent.evaluation_id,
        stage=DecisionStage.STRATEGY_EVALUATION,
        disposition=DecisionDisposition.ACCEPTED,
        reason_codes=(),
        evaluated_at=REQUESTED_AT + timedelta(seconds=1),
    )

    try:
        with factory.begin() as session:
            SqlAlchemyDatasetRepository(session).stage(input_dataset)
            seed_assessment_dependencies(session, input_assessment)
            seed_assessment(session, input_assessment)
            store = SqlAlchemyDecisionIntelligenceStore(session)
            store.stage_policy_definition(input_policy)
            store.stage_evaluation_intent(intent)
            store.stage_outcome(outcome)

        with factory() as session:
            store = SqlAlchemyDecisionIntelligenceStore(session)
            assert store.get_evaluation_intent(intent.evaluation_id) == intent
            assert store.list_stage_outcomes(intent.evaluation_id) == (outcome,)
    finally:
        with factory.begin() as session:
            session.execute(
                delete(DecisionStageOutcomeRow).where(
                    DecisionStageOutcomeRow.evaluation_id == intent.evaluation_id
                )
            )
            session.execute(
                delete(DecisionEvaluationIntentRow).where(
                    DecisionEvaluationIntentRow.evaluation_id == intent.evaluation_id
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
