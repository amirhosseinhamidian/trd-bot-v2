from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from trd_bot.db import (
    DatabaseBase,
    MarketRegimeAssessmentRow,
    SqlAlchemyContextAwareStrategyEvaluator,
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
    StrategyContextCompatibilityPolicyV1,
    StrategyEvaluationIntegrityError,
    StrategyEvaluationRecord,
    evaluate_strategy_intent,
    strategy_context_compatibility_policy_v1,
)
from trd_bot.domain import OHLCVCandle, Timeframe, TradingPair
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
from trd_bot.strategies import (
    StrategyLifecycleStatus,
    build_default_strategy_registry,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"
AS_OF = datetime(2026, 10, 19, 12, tzinfo=UTC)
REQUESTED_AT = AS_OF + timedelta(minutes=20)


def dataset(*, closes: tuple[int, ...] = (3, 2, 1, 2, 3)) -> DatasetSnapshot:
    candles = tuple(
        OHLCVCandle(
            source=SOURCE,
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=AS_OF - timedelta(hours=len(closes) - index),
            close_time=AS_OF - timedelta(hours=len(closes) - index - 1),
            received_at=(AS_OF - timedelta(hours=len(closes) - index - 1) + timedelta(minutes=1)),
            open_price=Decimal(close + 100),
            high_price=Decimal(close + 101),
            low_price=Decimal(close + 99),
            close_price=Decimal(close + 100),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index, close in enumerate(closes)
    )
    return DatasetBuilder().build(
        name="Context-aware strategy fixture",
        candles=candles,
        created_at=AS_OF + timedelta(minutes=2),
    )


def assessment(
    *,
    trend: MarketTrendRegime = MarketTrendRegime.TRENDING_UP,
    volatility: MarketVolatilityRegime = MarketVolatilityRegime.NORMAL,
    confidence: Decimal = Decimal("0.82"),
    status: MarketContextAssessmentStatus = MarketContextAssessmentStatus.READY,
    expires_at: datetime = AS_OF + timedelta(hours=1),
) -> MarketRegimeAssessment:
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
        status=status,
        trend=trend,
        volatility=volatility,
        confidence=confidence,
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
        expires_at=expires_at,
    )


def policy(
    *,
    state: DecisionPolicyState = DecisionPolicyState.ENABLED,
) -> DecisionPolicyDefinition:
    return DecisionPolicyDefinition.build(
        policy_key="default-context-aware-decision",
        policy_version=1,
        name="Default context-aware decision policy",
        description="Admit only traceable offline strategy decisions.",
        state=state,
        allowed_modes=tuple(DecisionMode),
        created_at=AS_OF + timedelta(minutes=2),
    )


def intent(
    *,
    input_dataset: DatasetSnapshot | None = None,
    input_assessment: MarketRegimeAssessment | None = None,
    input_policy: DecisionPolicyDefinition | None = None,
    lifecycle_status: StrategyLifecycleStatus = StrategyLifecycleStatus.ACTIVE,
) -> DecisionEvaluationIntent:
    metadata = build_default_strategy_registry().get_metadata(
        name="sma-crossover",
        version="1.0.0",
    )
    assert metadata is not None
    metadata = metadata.model_copy(update={"lifecycle_status": lifecycle_status})
    context = MarketContextProductView.from_assessment(
        input_assessment or assessment(),
        evaluated_at=REQUESTED_AT,
    )
    return DecisionEvaluationIntent.build(
        mode=DecisionMode.SHADOW,
        dataset=input_dataset or dataset(),
        strategy=metadata,
        strategy_parameters={"fast_period": 2, "slow_period": 3},
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


def test_compatibility_policy_is_frozen_and_tamper_evident() -> None:
    compatibility = strategy_context_compatibility_policy_v1()

    assert compatibility.definition_checksum == (
        "161c8908d5a54bc42e561d5d6a4d9b3678d6d27245d769ccd45af19ec5d42fa8"
    )
    assert [item.strategy_name for item in compatibility.rules] == [
        "ema-crossover",
        "rsi-threshold",
        "sma-crossover",
    ]

    payload = compatibility.model_dump()
    payload["rules"][0]["minimum_confidence"] = Decimal("0.61")
    with pytest.raises(ValidationError, match="policy checksum is inconsistent"):
        StrategyContextCompatibilityPolicyV1.model_validate(payload)


def test_compatible_intent_produces_deterministic_accepted_signal_evidence() -> None:
    evaluation_intent = intent()
    registry = build_default_strategy_registry()

    first = evaluate_strategy_intent(
        intent=evaluation_intent,
        dataset=dataset(),
        registry=registry,
    )
    repeated = evaluate_strategy_intent(
        intent=evaluation_intent,
        dataset=dataset(),
        registry=registry,
    )

    assert first == repeated
    assert first.outcome.disposition is DecisionDisposition.ACCEPTED
    assert first.outcome.evaluated_at == evaluation_intent.requested_at
    assert first.signal_count == 1
    assert first.latest_signal_id == first.signals[0].signal_id
    assert first.signals[0].direction == "long"
    assert first.offline_only is True
    assert first.external_order_submission_allowed is False
    assert StrategyEvaluationRecord.model_validate_json(first.model_dump_json()) == first


def test_compatible_but_neutral_evaluation_is_deferred_without_signal() -> None:
    neutral_dataset = dataset(closes=(1, 2, 3, 4, 5))
    evaluation = evaluate_strategy_intent(
        intent=intent(input_dataset=neutral_dataset),
        dataset=neutral_dataset,
        registry=build_default_strategy_registry(),
    )

    assert evaluation.outcome.disposition is DecisionDisposition.DEFERRED
    assert evaluation.outcome.reason_codes == (DecisionReasonCode.SIGNAL_NEUTRAL,)
    assert evaluation.signals == ()


def test_incompatible_or_uncertain_context_rejects_before_strategy_execution() -> None:
    incompatible_assessment = assessment(
        trend=MarketTrendRegime.RANGING,
        confidence=Decimal("0.50"),
    )
    evaluation = evaluate_strategy_intent(
        intent=intent(input_assessment=incompatible_assessment),
        dataset=dataset(),
        registry=build_default_strategy_registry(),
    )

    assert evaluation.outcome.disposition is DecisionDisposition.REJECTED
    assert evaluation.outcome.reason_codes == (
        DecisionReasonCode.STRATEGY_CONTEXT_INCOMPATIBLE,
        DecisionReasonCode.UNCERTAINTY_ABOVE_LIMIT,
    )
    assert evaluation.signals == ()


def test_disabled_policy_inactive_strategy_and_expired_context_fail_closed() -> None:
    expired = assessment(expires_at=REQUESTED_AT)
    evaluation = evaluate_strategy_intent(
        intent=intent(
            input_assessment=expired,
            input_policy=policy(state=DecisionPolicyState.DISABLED),
            lifecycle_status=StrategyLifecycleStatus.DEPRECATED,
        ),
        dataset=dataset(),
        registry=build_default_strategy_registry(),
    )

    assert evaluation.outcome.disposition is DecisionDisposition.UNAVAILABLE
    assert evaluation.outcome.reason_codes == (
        DecisionReasonCode.MARKET_CONTEXT_EXPIRED,
        DecisionReasonCode.MARKET_CONTEXT_NOT_CONSUMABLE,
        DecisionReasonCode.POLICY_DISABLED,
        DecisionReasonCode.STRATEGY_NOT_ACTIVE,
    )
    assert evaluation.signals == ()


def test_evaluator_rejects_dataset_that_does_not_match_pinned_intent() -> None:
    evaluation_intent = intent()

    with pytest.raises(StrategyEvaluationIntegrityError, match="pinned reference"):
        evaluate_strategy_intent(
            intent=evaluation_intent,
            dataset=dataset(closes=(3, 2, 1, 2, 4)),
            registry=build_default_strategy_registry(),
        )


def test_sqlalchemy_evaluator_persists_one_idempotent_record() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
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
            seed_assessment(session, input_assessment)
            store = SqlAlchemyDecisionIntelligenceStore(session)
            store.stage_policy_definition(input_policy)
            store.stage_evaluation_intent(evaluation_intent)

            evaluator = SqlAlchemyContextAwareStrategyEvaluator(session)
            first, first_created = evaluator.evaluate(evaluation_intent.evaluation_id)
            repeated, repeated_created = evaluator.evaluate(evaluation_intent.evaluation_id)

            assert first_created is True
            assert repeated_created is False
            assert repeated == first

        with factory() as session:
            stored = SqlAlchemyDecisionIntelligenceStore(session).get_strategy_evaluation(
                evaluation_intent.evaluation_id
            )
            assert stored == first
            assert stored is not None
            assert stored.outcome.disposition is DecisionDisposition.ACCEPTED
    finally:
        engine.dispose()
