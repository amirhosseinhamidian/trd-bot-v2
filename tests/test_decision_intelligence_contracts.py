from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.decision_intelligence import (
    DecisionDatasetReference,
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionMode,
    DecisionPolicyDefinition,
    DecisionPolicyState,
    DecisionReasonCode,
    DecisionStage,
    DecisionStageOutcome,
    DecisionStrategyReference,
    MarketContextDecisionReference,
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
from trd_bot.strategies import StrategyMetadata, build_default_strategy_registry

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"
AS_OF = datetime(2026, 10, 19, 12, tzinfo=UTC)
REQUESTED_AT = AS_OF + timedelta(minutes=20)


def dataset(
    *,
    source: str = SOURCE,
    pair: TradingPair = PAIR,
) -> DatasetSnapshot:
    candles = tuple(
        OHLCVCandle(
            source=source,
            pair=pair,
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
        name="Decision contract fixture",
        candles=candles,
        created_at=AS_OF + timedelta(minutes=2),
    )


def assessment(*, expires_at: datetime | None = None) -> MarketRegimeAssessment:
    input_checksum = "a" * 64
    assessment_id = build_market_regime_assessment_id(
        source=SOURCE,
        pair=PAIR,
        as_of=AS_OF,
        input_checksum=input_checksum,
        feature_set_version="market-context-features-v1",
        algorithm_version="market-regime-v1",
    )
    return MarketRegimeAssessment(
        assessment_id=assessment_id,
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
        expires_at=expires_at or AS_OF + timedelta(hours=1),
    )


def context_view(*, expires_at: datetime | None = None) -> MarketContextProductView:
    return MarketContextProductView.from_assessment(
        assessment(expires_at=expires_at),
        evaluated_at=REQUESTED_AT,
    )


def strategy_metadata() -> StrategyMetadata:
    metadata = build_default_strategy_registry().get_metadata(
        name="sma-crossover",
        version="1.0.0",
    )
    assert metadata is not None
    return metadata


def policy(
    *,
    version: int = 1,
    state: DecisionPolicyState = DecisionPolicyState.ENABLED,
    allowed_modes: tuple[DecisionMode, ...] = tuple(DecisionMode),
) -> DecisionPolicyDefinition:
    return DecisionPolicyDefinition.build(
        policy_key="default-context-aware-decision",
        policy_version=version,
        name="Default context-aware decision policy",
        description="Admit only traceable offline strategy decisions.",
        state=state,
        allowed_modes=allowed_modes,
        created_at=AS_OF + timedelta(minutes=2),
    )


def intent(
    *,
    input_dataset: DatasetSnapshot | None = None,
    input_policy: DecisionPolicyDefinition | None = None,
    mode: DecisionMode = DecisionMode.SHADOW,
    view: MarketContextProductView | None = None,
) -> DecisionEvaluationIntent:
    return DecisionEvaluationIntent.build(
        mode=mode,
        dataset=input_dataset or dataset(),
        strategy=strategy_metadata(),
        strategy_parameters={"slow_period": 21, "fast_period": 9},
        market_context=view or context_view(),
        policy=input_policy or policy(),
        requested_at=REQUESTED_AT,
    )


def test_policy_is_versioned_deterministic_and_offline_only() -> None:
    first = policy()
    repeated = policy()
    second = policy(version=2)

    assert first == repeated
    assert first.policy_id == second.policy_id
    assert first.supersedes_version is None
    assert second.supersedes_version == 1
    assert first.offline_only is True
    assert first.external_order_submission_allowed is False
    assert first.allowed_modes == (
        DecisionMode.RESEARCH,
        DecisionMode.SHADOW,
        DecisionMode.PAPER,
    )

    payload = second.model_dump()
    payload["description"] = "Tampered policy"
    with pytest.raises(ValidationError, match="checksum is inconsistent"):
        DecisionPolicyDefinition.model_validate(payload)


def test_policy_rejects_skipped_lineage_and_unordered_modes() -> None:
    definition = policy(version=2)
    payload = definition.model_dump()
    payload["supersedes_version"] = None
    with pytest.raises(ValidationError, match="immediate predecessor"):
        DecisionPolicyDefinition.model_validate(payload)

    payload = policy().model_dump()
    payload["allowed_modes"] = [DecisionMode.PAPER, DecisionMode.RESEARCH]
    with pytest.raises(ValidationError, match="deterministic order"):
        DecisionPolicyDefinition.model_validate(payload)


def test_dataset_and_strategy_references_are_deterministic_and_tamper_evident() -> None:
    input_dataset = dataset()
    first_dataset = DecisionDatasetReference.from_dataset(input_dataset)
    second_dataset = DecisionDatasetReference.from_dataset(input_dataset)
    strategy = DecisionStrategyReference.from_metadata(
        strategy_metadata(),
        parameters={"slow_period": 21, "fast_period": 9},
    )

    assert first_dataset == second_dataset
    assert tuple(item.name for item in strategy.parameters) == (
        "fast_period",
        "slow_period",
    )

    dataset_payload = first_dataset.model_dump()
    dataset_payload["candle_count"] = 4
    with pytest.raises(ValidationError, match="dataset reference checksum"):
        DecisionDatasetReference.model_validate(dataset_payload)

    strategy_payload = strategy.model_dump()
    strategy_payload["parameters"][0]["value"] = "10"
    with pytest.raises(ValidationError, match="strategy reference checksum"):
        DecisionStrategyReference.model_validate(strategy_payload)


def test_strategy_reference_rejects_missing_and_noncanonical_parameters() -> None:
    with pytest.raises(ValueError, match="parameter set is incomplete"):
        DecisionStrategyReference.from_metadata(
            strategy_metadata(),
            parameters={"fast_period": 9},
        )

    with pytest.raises(ValueError, match="must be an integer"):
        DecisionStrategyReference.from_metadata(
            strategy_metadata(),
            parameters={"fast_period": "9", "slow_period": 21},
        )


def test_market_context_reference_preserves_availability_and_detects_tampering() -> None:
    reference = MarketContextDecisionReference.from_product_view(context_view())

    assert reference.consumable is True
    assert reference.unavailable_reasons == ()
    assert reference.as_of == AS_OF

    payload = reference.model_dump()
    payload["confidence"] = Decimal("0.91")
    with pytest.raises(ValidationError, match="context reference checksum"):
        MarketContextDecisionReference.model_validate(payload)


def test_non_consumable_context_is_captured_for_auditable_fail_closed_evaluation() -> None:
    stale_view = context_view(expires_at=REQUESTED_AT)
    evaluation = intent(view=stale_view)

    assert evaluation.market_context.consumable is False
    assert evaluation.market_context.unavailable_reasons


def test_intent_is_deterministic_idempotent_and_round_trips() -> None:
    first = intent()
    repeated = intent()

    assert first == repeated
    assert first.offline_only is True
    assert first.external_order_submission_allowed is False
    assert first.stage is DecisionStage.STRATEGY_EVALUATION
    assert build_decision_evaluation_idempotency_key(first) == (
        build_decision_evaluation_idempotency_key(repeated)
    )
    assert DecisionEvaluationIntent.model_validate_json(first.model_dump_json()) == first

    payload = first.model_dump()
    payload["strategy"]["behavior_fingerprint"] = f"sha256:{'f' * 64}"
    with pytest.raises(ValidationError, match="strategy reference checksum"):
        DecisionEvaluationIntent.model_validate(payload)


def test_intent_rejects_mode_pair_source_and_lookahead_mismatches() -> None:
    research_only = policy(allowed_modes=(DecisionMode.RESEARCH,))
    with pytest.raises(ValidationError, match=DecisionReasonCode.MODE_NOT_ALLOWED.value):
        intent(input_policy=research_only, mode=DecisionMode.PAPER)

    other_pair = TradingPair(base_asset="ETH", quote_asset="USDT")
    with pytest.raises(ValidationError, match=DecisionReasonCode.DATASET_PAIR_MISMATCH.value):
        intent(input_dataset=dataset(pair=other_pair))

    with pytest.raises(ValidationError, match=DecisionReasonCode.DATASET_SOURCE_MISMATCH.value):
        intent(input_dataset=dataset(source="binance-public"))

    lookahead_dataset = dataset().model_copy(update={"end_time": AS_OF + timedelta(hours=1)})
    with pytest.raises(ValidationError, match=DecisionReasonCode.DATASET_LOOKAHEAD.value):
        intent(input_dataset=lookahead_dataset)


def test_stage_outcome_has_stable_semantics_and_detects_tampering() -> None:
    evaluation = intent()
    accepted = DecisionStageOutcome.build(
        evaluation_id=evaluation.evaluation_id,
        stage=DecisionStage.STRATEGY_EVALUATION,
        disposition=DecisionDisposition.ACCEPTED,
        reason_codes=(),
        evaluated_at=REQUESTED_AT + timedelta(seconds=1),
    )
    unavailable = DecisionStageOutcome.build(
        evaluation_id=evaluation.evaluation_id,
        stage=DecisionStage.RISK_GATE,
        disposition=DecisionDisposition.UNAVAILABLE,
        reason_codes=(
            DecisionReasonCode.STRATEGY_NOT_ACTIVE,
            DecisionReasonCode.MARKET_CONTEXT_NOT_CONSUMABLE,
        ),
        evaluated_at=REQUESTED_AT + timedelta(seconds=2),
    )

    assert accepted.reason_codes == ()
    assert unavailable.reason_codes == tuple(
        sorted(unavailable.reason_codes, key=lambda item: item.value)
    )
    assert unavailable.offline_only is True
    assert unavailable.external_order_submission_allowed is False

    with pytest.raises(ValidationError, match="accepted decision outcome"):
        DecisionStageOutcome.build(
            evaluation_id=evaluation.evaluation_id,
            stage=DecisionStage.STRATEGY_EVALUATION,
            disposition=DecisionDisposition.ACCEPTED,
            reason_codes=(DecisionReasonCode.SIGNAL_NEUTRAL,),
            evaluated_at=REQUESTED_AT,
        )

    with pytest.raises(ValidationError, match="requires at least one reason"):
        DecisionStageOutcome.build(
            evaluation_id=evaluation.evaluation_id,
            stage=DecisionStage.RISK_GATE,
            disposition=DecisionDisposition.REJECTED,
            reason_codes=(),
            evaluated_at=REQUESTED_AT,
        )

    payload = unavailable.model_dump()
    payload["evaluated_at"] = REQUESTED_AT + timedelta(minutes=1)
    with pytest.raises(ValidationError, match="outcome checksum"):
        DecisionStageOutcome.model_validate(payload)


def test_decision_contracts_forbid_unknown_or_live_execution_fields() -> None:
    evaluation = intent()
    payload = evaluation.model_dump()
    payload["exchange_api_key"] = "forbidden"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DecisionEvaluationIntent.model_validate(payload)

    payload = evaluation.model_dump()
    payload["external_order_submission_allowed"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        DecisionEvaluationIntent.model_validate(payload)
