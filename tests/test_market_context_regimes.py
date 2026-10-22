from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from tests.test_market_context_features import complete_input
from trd_bot.db import (
    DatabaseBase,
    MarketRegimeAssessmentRow,
    SqlAlchemyMarketContextStore,
    SqlAlchemyMarketDataEventStore,
    SqlAlchemyMarketRegimeEvaluator,
    create_database_engine,
    create_session_factory,
)
from trd_bot.market_context import (
    MARKET_REGIME_ALGORITHM_V1,
    MarketContextAssessmentStatus,
    MarketContextFeatureSnapshot,
    MarketRegimePolicyV1,
    MarketTrendRegime,
    MarketVolatilityRegime,
    calculate_market_context_feature_snapshot_v1,
    evaluate_market_regime_v1,
    market_context_feature_set_v1,
    market_regime_policy_v1,
)


def feature_snapshot(
    *,
    trend_1h: str,
    trend_4h: str,
    trend_1d: str,
    volatility_1h: str,
    volatility_1d: str,
) -> MarketContextFeatureSnapshot:
    windows, manifest = complete_input()
    base = calculate_market_context_feature_snapshot_v1(
        manifest=manifest,
        windows=windows,
    )
    values = {
        "realized_volatility_1d": Decimal(volatility_1d),
        "realized_volatility_1h": Decimal(volatility_1h),
        "trend_slope_1d": Decimal(trend_1d),
        "trend_slope_1h": Decimal(trend_1h),
        "trend_slope_4h": Decimal(trend_4h),
    }
    evidence = tuple(
        item.model_copy(update={"value": values[item.feature_key]}) for item in base.features
    )
    return MarketContextFeatureSnapshot.build(
        manifest=manifest,
        feature_set=market_context_feature_set_v1(),
        features=evidence,
        calculated_at=base.calculated_at,
    )


def test_regime_v1_policy_is_frozen_and_tamper_evident() -> None:
    policy = market_regime_policy_v1()

    assert policy.algorithm_version == MARKET_REGIME_ALGORITHM_V1
    assert policy.definition_checksum == (
        "b8ace4b9c2a53c79f15b2f9da6689aae3dc344c35a178a00a4dd8e7acff153db"
    )
    assert policy.trend_weight_1h + policy.trend_weight_4h + policy.trend_weight_1d == 1
    assert policy.volatility_weight_1h + policy.volatility_weight_1d == 1

    payload = policy.model_dump()
    payload["trend_slope_1h_threshold"] = Decimal("0.0006")
    with pytest.raises(ValidationError, match="policy checksum is inconsistent"):
        MarketRegimePolicyV1.model_validate(payload)


def test_unanimous_positive_low_volatility_features_produce_high_confidence_regime() -> None:
    snapshot = feature_snapshot(
        trend_1h="0.0010",
        trend_4h="0.0020",
        trend_1d="0.0030",
        volatility_1h="0.0020",
        volatility_1d="0.0100",
    )

    assessment = evaluate_market_regime_v1(snapshot)

    assert assessment.status is MarketContextAssessmentStatus.READY
    assert assessment.trend is MarketTrendRegime.TRENDING_UP
    assert assessment.volatility is MarketVolatilityRegime.LOW
    assert assessment.confidence == Decimal("1.0000")
    assert assessment.algorithm_version == MARKET_REGIME_ALGORITHM_V1
    assert assessment.assessment_id == "market-regime-f616222a1a45b5da"
    assert assessment.evidence == snapshot.features
    assert assessment.assessed_at == snapshot.calculated_at
    assert assessment.expires_at == snapshot.calculated_at + timedelta(hours=1)


def test_unanimous_negative_high_volatility_features_produce_down_regime() -> None:
    assessment = evaluate_market_regime_v1(
        feature_snapshot(
            trend_1h="-0.0010",
            trend_4h="-0.0020",
            trend_1d="-0.0030",
            volatility_1h="0.0200",
            volatility_1d="0.0500",
        )
    )

    assert assessment.trend is MarketTrendRegime.TRENDING_DOWN
    assert assessment.volatility is MarketVolatilityRegime.HIGH
    assert assessment.confidence == Decimal("1.0000")


def test_conflicting_trend_and_mid_band_volatility_are_ranging_normal() -> None:
    assessment = evaluate_market_regime_v1(
        feature_snapshot(
            trend_1h="0.0010",
            trend_4h="-0.0020",
            trend_1d="0.0001",
            volatility_1h="0.0060",
            volatility_1d="0.0200",
        )
    )

    assert assessment.trend is MarketTrendRegime.RANGING
    assert assessment.volatility is MarketVolatilityRegime.NORMAL
    assert assessment.confidence == Decimal("0.9500")


def test_one_directional_timeframe_cannot_create_a_trend_by_itself() -> None:
    assessment = evaluate_market_regime_v1(
        feature_snapshot(
            trend_1h="0",
            trend_4h="0",
            trend_1d="0.0020",
            volatility_1h="0.0060",
            volatility_1d="0.0200",
        )
    )

    assert assessment.trend is MarketTrendRegime.RANGING
    assert assessment.confidence == Decimal("0.7500")


def test_threshold_boundaries_and_mixed_volatility_use_documented_inclusive_rules() -> None:
    trending = evaluate_market_regime_v1(
        feature_snapshot(
            trend_1h="0.0005",
            trend_4h="0.0010",
            trend_1d="0",
            volatility_1h="0.0030",
            volatility_1d="0.0120",
        )
    )
    assert trending.trend is MarketTrendRegime.TRENDING_UP
    assert trending.volatility is MarketVolatilityRegime.LOW
    assert trending.confidence == Decimal("0.7500")

    mixed_volatility = evaluate_market_regime_v1(
        feature_snapshot(
            trend_1h="0.0010",
            trend_4h="0.0020",
            trend_1d="0.0030",
            volatility_1h="0.0120",
            volatility_1d="0.0120",
        )
    )
    assert mixed_volatility.volatility is MarketVolatilityRegime.NORMAL
    assert mixed_volatility.confidence == Decimal("0.7500")


def test_regime_rejects_noncanonical_or_invalid_feature_snapshots() -> None:
    canonical = feature_snapshot(
        trend_1h="0.0010",
        trend_4h="0.0020",
        trend_1d="0.0030",
        volatility_1h="0.0060",
        volatility_1d="0.0200",
    )
    changed_definition = canonical.model_copy(update={"feature_set_checksum": "0" * 64})
    with pytest.raises(ValueError, match="canonical v1 feature set"):
        evaluate_market_regime_v1(changed_definition)

    missing_feature = canonical.model_copy(update={"features": canonical.features[:-1]})
    with pytest.raises(ValueError, match="every canonical feature"):
        evaluate_market_regime_v1(missing_feature)

    invalid_features = tuple(
        item.model_copy(update={"value": Decimal("-0.01")})
        if item.feature_key == "realized_volatility_1h"
        else item
        for item in canonical.features
    )
    negative_volatility = canonical.model_copy(update={"features": invalid_features})
    with pytest.raises(ValueError, match="non-negative volatility"):
        evaluate_market_regime_v1(negative_volatility)


def test_sqlalchemy_regime_evaluator_stages_one_reproducible_assessment() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    windows, manifest = complete_input()
    snapshot = calculate_market_context_feature_snapshot_v1(
        manifest=manifest,
        windows=windows,
    )

    try:
        with factory.begin() as session:
            window_store = SqlAlchemyMarketDataEventStore(session)
            for item in windows:
                window_store.stage_window_version(item)
            store = SqlAlchemyMarketContextStore(session)
            store.stage_input_manifest(manifest)
            store.stage_feature_snapshot(snapshot)

        with factory.begin() as session:
            evaluator = SqlAlchemyMarketRegimeEvaluator(session)
            first, first_created = evaluator.evaluate_and_stage(manifest_id=manifest.manifest_id)
            second, second_created = evaluator.evaluate_and_stage(manifest_id=manifest.manifest_id)

            assert first_created is True
            assert second_created is False
            assert first == second
            assert session.scalar(select(func.count()).select_from(MarketRegimeAssessmentRow)) == 1
    finally:
        engine.dispose()


def test_sqlalchemy_regime_evaluator_requires_a_feature_snapshot() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    _, manifest = complete_input()

    try:
        with (
            factory() as session,
            pytest.raises(ValueError, match="feature snapshot does not exist"),
        ):
            SqlAlchemyMarketRegimeEvaluator(session).evaluate_and_stage(
                manifest_id=manifest.manifest_id
            )
    finally:
        engine.dispose()
