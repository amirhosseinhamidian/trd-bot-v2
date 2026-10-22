import hashlib
import json
from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.market_context.contracts import (
    MarketContextAssessmentStatus,
    MarketContextFeatureSnapshot,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
    build_market_regime_assessment_id,
)
from trd_bot.market_context.features import market_context_feature_set_v1

MARKET_REGIME_ALGORITHM_V1 = "market-regime-v1"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class MarketRegimePolicyV1(BaseModel):
    """Frozen thresholds, weights, confidence precision and expiry for regime v1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-regime-policy-v1"] = "market-regime-policy-v1"
    algorithm_version: Literal["market-regime-v1"] = "market-regime-v1"
    trend_slope_1h_threshold: Decimal = Field(gt=0)
    trend_slope_4h_threshold: Decimal = Field(gt=0)
    trend_slope_1d_threshold: Decimal = Field(gt=0)
    trend_weight_1h: Decimal = Field(gt=0, le=1)
    trend_weight_4h: Decimal = Field(gt=0, le=1)
    trend_weight_1d: Decimal = Field(gt=0, le=1)
    minimum_trending_score: Decimal = Field(gt=0, le=1)
    minimum_directional_votes: int = Field(ge=2, le=3)
    volatility_1h_low_max: Decimal = Field(gt=0)
    volatility_1h_high_min: Decimal = Field(gt=0)
    volatility_1d_low_max: Decimal = Field(gt=0)
    volatility_1d_high_min: Decimal = Field(gt=0)
    volatility_weight_1h: Decimal = Field(gt=0, le=1)
    volatility_weight_1d: Decimal = Field(gt=0, le=1)
    minimum_extreme_volatility_score: Decimal = Field(gt=0, le=1)
    confidence_quantum: Decimal = Field(gt=0, le=1)
    expires_after_seconds: int = Field(ge=60, le=86_400)
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.trend_weight_1h + self.trend_weight_4h + self.trend_weight_1d != 1:
            raise ValueError("trend weights must sum to one")
        if self.volatility_weight_1h + self.volatility_weight_1d != 1:
            raise ValueError("volatility weights must sum to one")
        if self.volatility_1h_low_max >= self.volatility_1h_high_min:
            raise ValueError("1h volatility thresholds must define an ordered normal band")
        if self.volatility_1d_low_max >= self.volatility_1d_high_min:
            raise ValueError("1d volatility thresholds must define an ordered normal band")
        if self.definition_checksum != _checksum(self._checksum_payload()):
            raise ValueError("market-regime policy checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, str | int]:
        return {
            "algorithm_version": self.algorithm_version,
            "confidence_quantum": str(self.confidence_quantum),
            "expires_after_seconds": self.expires_after_seconds,
            "minimum_directional_votes": self.minimum_directional_votes,
            "minimum_extreme_volatility_score": str(self.minimum_extreme_volatility_score),
            "minimum_trending_score": str(self.minimum_trending_score),
            "schema_version": self.schema_version,
            "trend_slope_1d_threshold": str(self.trend_slope_1d_threshold),
            "trend_slope_1h_threshold": str(self.trend_slope_1h_threshold),
            "trend_slope_4h_threshold": str(self.trend_slope_4h_threshold),
            "trend_weight_1d": str(self.trend_weight_1d),
            "trend_weight_1h": str(self.trend_weight_1h),
            "trend_weight_4h": str(self.trend_weight_4h),
            "volatility_1d_high_min": str(self.volatility_1d_high_min),
            "volatility_1d_low_max": str(self.volatility_1d_low_max),
            "volatility_1h_high_min": str(self.volatility_1h_high_min),
            "volatility_1h_low_max": str(self.volatility_1h_low_max),
            "volatility_weight_1d": str(self.volatility_weight_1d),
            "volatility_weight_1h": str(self.volatility_weight_1h),
        }


def market_regime_policy_v1() -> MarketRegimePolicyV1:
    """Return a new immutable copy of the canonical regime v1 policy."""

    unvalidated = MarketRegimePolicyV1.model_construct(
        trend_slope_1h_threshold=Decimal("0.0005"),
        trend_slope_4h_threshold=Decimal("0.0010"),
        trend_slope_1d_threshold=Decimal("0.0020"),
        trend_weight_1h=Decimal("0.20"),
        trend_weight_4h=Decimal("0.30"),
        trend_weight_1d=Decimal("0.50"),
        minimum_trending_score=Decimal("0.50"),
        minimum_directional_votes=2,
        volatility_1h_low_max=Decimal("0.0030"),
        volatility_1h_high_min=Decimal("0.0120"),
        volatility_1d_low_max=Decimal("0.0120"),
        volatility_1d_high_min=Decimal("0.0400"),
        volatility_weight_1h=Decimal("0.60"),
        volatility_weight_1d=Decimal("0.40"),
        minimum_extreme_volatility_score=Decimal("0.50"),
        confidence_quantum=Decimal("0.0001"),
        expires_after_seconds=3600,
        definition_checksum="0" * 64,
    )
    payload = unvalidated.model_dump()
    payload["definition_checksum"] = _checksum(unvalidated._checksum_payload())
    return MarketRegimePolicyV1.model_validate(payload)


def evaluate_market_regime_v1(
    snapshot: MarketContextFeatureSnapshot,
) -> MarketRegimeAssessment:
    """Convert one exact v1 feature snapshot into a deterministic regime assessment."""

    policy = market_regime_policy_v1()
    feature_set = market_context_feature_set_v1()
    if (
        snapshot.feature_set_version != feature_set.feature_set_version
        or snapshot.feature_set_checksum != feature_set.definition_checksum
    ):
        raise ValueError("regime v1 requires the canonical v1 feature set")

    expected_keys = tuple(item.feature_key for item in feature_set.requirements)
    actual_keys = tuple(item.feature_key for item in snapshot.features)
    if actual_keys != expected_keys:
        raise ValueError("regime v1 requires every canonical feature exactly once")
    for evidence, requirement in zip(
        snapshot.features,
        feature_set.requirements,
        strict=True,
    ):
        if (
            evidence.timeframe is not requirement.timeframe
            or evidence.calculation_version != requirement.calculation_version
            or len(evidence.window_reference_checksums) != requirement.lookback_windows
        ):
            raise ValueError("regime v1 feature evidence does not match its requirement")
    features = {item.feature_key: item.value for item in snapshot.features}
    if any(not value.is_finite() for value in features.values()):
        raise ValueError("regime v1 requires finite feature values")
    if any(features[key] < 0 for key in ("realized_volatility_1h", "realized_volatility_1d")):
        raise ValueError("regime v1 requires non-negative volatility features")

    trend, trend_confidence = _classify_trend(features=features, policy=policy)
    volatility, volatility_confidence = _classify_volatility(
        features=features,
        policy=policy,
    )
    confidence = ((trend_confidence + volatility_confidence) / Decimal(2)).quantize(
        policy.confidence_quantum,
        rounding=ROUND_HALF_EVEN,
    )
    assessed_at = snapshot.calculated_at
    expires_at = assessed_at + timedelta(seconds=policy.expires_after_seconds)
    assessment_id = build_market_regime_assessment_id(
        source=snapshot.source,
        pair=snapshot.pair,
        as_of=snapshot.as_of,
        input_checksum=snapshot.input_checksum,
        feature_set_version=snapshot.feature_set_version,
        algorithm_version=policy.algorithm_version,
    )
    return MarketRegimeAssessment(
        assessment_id=assessment_id,
        source=snapshot.source,
        pair=snapshot.pair,
        as_of=snapshot.as_of,
        input_manifest_id=snapshot.input_manifest_id,
        input_checksum=snapshot.input_checksum,
        feature_set_version=snapshot.feature_set_version,
        feature_set_checksum=snapshot.feature_set_checksum,
        feature_snapshot_id=snapshot.snapshot_id,
        feature_snapshot_checksum=snapshot.snapshot_checksum,
        algorithm_version=policy.algorithm_version,
        status=MarketContextAssessmentStatus.READY,
        trend=trend,
        volatility=volatility,
        confidence=confidence,
        evidence=snapshot.features,
        assessed_at=assessed_at,
        expires_at=expires_at,
    )


def _classify_trend(
    *,
    features: dict[str, Decimal],
    policy: MarketRegimePolicyV1,
) -> tuple[MarketTrendRegime, Decimal]:
    inputs = (
        (
            features["trend_slope_1h"],
            policy.trend_slope_1h_threshold,
            policy.trend_weight_1h,
        ),
        (
            features["trend_slope_4h"],
            policy.trend_slope_4h_threshold,
            policy.trend_weight_4h,
        ),
        (
            features["trend_slope_1d"],
            policy.trend_slope_1d_threshold,
            policy.trend_weight_1d,
        ),
    )
    votes = tuple(_directional_vote(value, threshold) for value, threshold, _ in inputs)
    score = sum(
        (Decimal(vote) * weight for vote, (_, _, weight) in zip(votes, inputs, strict=True)),
        start=Decimal(0),
    )
    positive_votes = sum(vote > 0 for vote in votes)
    negative_votes = sum(vote < 0 for vote in votes)
    if (
        score >= policy.minimum_trending_score
        and positive_votes >= policy.minimum_directional_votes
    ):
        return MarketTrendRegime.TRENDING_UP, abs(score)
    if (
        score <= -policy.minimum_trending_score
        and negative_votes >= policy.minimum_directional_votes
    ):
        return MarketTrendRegime.TRENDING_DOWN, abs(score)
    return MarketTrendRegime.RANGING, Decimal(1) - abs(score)


def _classify_volatility(
    *,
    features: dict[str, Decimal],
    policy: MarketRegimePolicyV1,
) -> tuple[MarketVolatilityRegime, Decimal]:
    classifications = (
        (
            _volatility_vote(
                features["realized_volatility_1h"],
                low_max=policy.volatility_1h_low_max,
                high_min=policy.volatility_1h_high_min,
            ),
            policy.volatility_weight_1h,
        ),
        (
            _volatility_vote(
                features["realized_volatility_1d"],
                low_max=policy.volatility_1d_low_max,
                high_min=policy.volatility_1d_high_min,
            ),
            policy.volatility_weight_1d,
        ),
    )
    low_weight = sum(
        (weight for vote, weight in classifications if vote < 0),
        start=Decimal(0),
    )
    normal_weight = sum(
        (weight for vote, weight in classifications if vote == 0),
        start=Decimal(0),
    )
    high_weight = sum(
        (weight for vote, weight in classifications if vote > 0),
        start=Decimal(0),
    )
    score = high_weight - low_weight
    if score >= policy.minimum_extreme_volatility_score:
        return MarketVolatilityRegime.HIGH, high_weight
    if score <= -policy.minimum_extreme_volatility_score:
        return MarketVolatilityRegime.LOW, low_weight
    return MarketVolatilityRegime.NORMAL, max(Decimal("0.50"), normal_weight)


def _directional_vote(value: Decimal, threshold: Decimal) -> int:
    if value >= threshold:
        return 1
    if value <= -threshold:
        return -1
    return 0


def _volatility_vote(value: Decimal, *, low_max: Decimal, high_min: Decimal) -> int:
    if value <= low_max:
        return -1
    if value >= high_min:
        return 1
    return 0
