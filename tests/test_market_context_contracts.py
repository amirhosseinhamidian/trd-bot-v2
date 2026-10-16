from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextEvidence,
    MarketContextFeatureRequirement,
    MarketContextFeatureSetDefinition,
    MarketContextFeatureSnapshot,
    MarketContextInputManifest,
    MarketContextWindowReference,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
    build_market_regime_assessment_id,
    default_market_context_alignment_policy,
)
from trd_bot.market_data import MarketDataEvent, MarketDataWatermark, MarketDataWindowSnapshot

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"


def finalized_reference(
    timeframe: Timeframe,
    window_start: datetime,
    *,
    close_price: str = "105",
) -> MarketContextWindowReference:
    candle = OHLCVCandle(
        source=SOURCE,
        pair=PAIR,
        timeframe=timeframe,
        open_time=window_start,
        close_time=window_start + timeframe.duration,
        received_at=window_start + timeframe.duration + timedelta(minutes=1),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal(close_price),
        volume=Decimal("1250.5"),
    )
    event = MarketDataEvent.from_candle(candle)
    provisional = MarketDataWindowSnapshot.from_event(
        event,
        version=1,
        created_at=candle.received_at,
    )
    watermark = MarketDataWatermark.build(
        source=SOURCE,
        pair=PAIR,
        timeframe=timeframe,
        high_water_event_time=candle.close_time,
        allowed_lateness_seconds=0,
        calculated_at=candle.received_at,
    )
    finalized = provisional.finalize(
        watermark,
        finalized_at=candle.received_at + timedelta(minutes=1),
    )
    return MarketContextWindowReference.from_snapshot(finalized)


def complete_windows() -> tuple[MarketContextWindowReference, ...]:
    return (
        finalized_reference(Timeframe.HOUR_1, datetime(2026, 10, 16, 11, tzinfo=UTC)),
        finalized_reference(Timeframe.HOURS_4, datetime(2026, 10, 16, 8, tzinfo=UTC)),
        finalized_reference(Timeframe.DAY_1, datetime(2026, 10, 15, tzinfo=UTC)),
    )


def complete_manifest() -> MarketContextInputManifest:
    return MarketContextInputManifest.build(
        source=SOURCE,
        pair=PAIR,
        as_of=datetime(2026, 10, 16, 12, tzinfo=UTC),
        windows=complete_windows(),
        created_at=datetime(2026, 10, 16, 12, 5, tzinfo=UTC),
    )


def feature_definition() -> MarketContextFeatureSetDefinition:
    return MarketContextFeatureSetDefinition.build(
        feature_set_version="market-context-features-v1",
        requirements=(
            MarketContextFeatureRequirement(
                feature_key="trend_slope_1h",
                timeframe=Timeframe.HOUR_1,
                lookback_windows=24,
                calculation_version="trend-slope-v1",
            ),
            MarketContextFeatureRequirement(
                feature_key="volatility_1d",
                timeframe=Timeframe.DAY_1,
                lookback_windows=30,
                calculation_version="realized-volatility-v1",
            ),
        ),
    )


def test_v1_alignment_policy_is_frozen_and_public_read_only() -> None:
    policy = default_market_context_alignment_policy()

    assert policy.timeframes == (
        Timeframe.HOUR_1,
        Timeframe.HOURS_4,
        Timeframe.DAY_1,
    )
    assert policy.scope == "crypto-spot-public-read-only"
    assert policy.finalized_windows_only is True
    assert policy.same_source_only is True

    payload = policy.model_dump()
    payload["context_timeframes"] = [Timeframe.DAY_1, Timeframe.HOURS_4]
    with pytest.raises(ValidationError, match="ordered as 4h then 1d"):
        type(policy).model_validate(payload)


def test_provisional_window_cannot_become_a_context_reference() -> None:
    candle = OHLCVCandle(
        source=SOURCE,
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 10, 16, 11, tzinfo=UTC),
        close_time=datetime(2026, 10, 16, 12, tzinfo=UTC),
        received_at=datetime(2026, 10, 16, 12, 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("10"),
    )
    provisional = MarketDataWindowSnapshot.from_event(
        MarketDataEvent.from_candle(candle),
        version=1,
        created_at=candle.received_at,
    )

    with pytest.raises(ValueError, match="requires a finalized window"):
        MarketContextWindowReference.from_snapshot(provisional)


def test_window_reference_detects_lineage_tampering() -> None:
    reference = complete_windows()[0]
    payload = reference.model_dump()
    payload["payload_checksum"] = "0" * 64

    with pytest.raises(ValidationError, match="reference checksum is inconsistent"):
        MarketContextWindowReference.model_validate(payload)


def test_complete_manifest_is_deterministic_for_unordered_input() -> None:
    windows = complete_windows()
    first = MarketContextInputManifest.build(
        source=SOURCE,
        pair=PAIR,
        as_of=datetime(2026, 10, 16, 12, tzinfo=UTC),
        windows=tuple(reversed(windows)),
        created_at=datetime(2026, 10, 16, 12, 5, tzinfo=UTC),
    )
    second = complete_manifest()

    assert first.manifest_id == second.manifest_id
    assert first.input_checksum == second.input_checksum
    assert tuple(item.timeframe for item in first.windows) == (
        Timeframe.HOUR_1,
        Timeframe.HOURS_4,
        Timeframe.DAY_1,
    )


def test_manifest_rejects_missing_required_timeframe() -> None:
    windows = complete_windows()[:-1]

    with pytest.raises(ValidationError, match="at least 3 items"):
        MarketContextInputManifest.build(
            source=SOURCE,
            pair=PAIR,
            as_of=datetime(2026, 10, 16, 12, tzinfo=UTC),
            windows=windows,
            created_at=datetime(2026, 10, 16, 12, 5, tzinfo=UTC),
        )


def test_manifest_rejects_incomplete_higher_timeframe_boundary() -> None:
    windows = list(complete_windows())
    windows[1] = finalized_reference(
        Timeframe.HOURS_4,
        datetime(2026, 10, 16, 12, tzinfo=UTC),
    )

    with pytest.raises(ValidationError, match="future event-time window"):
        MarketContextInputManifest.build(
            source=SOURCE,
            pair=PAIR,
            as_of=datetime(2026, 10, 16, 12, tzinfo=UTC),
            windows=tuple(windows),
            created_at=datetime(2026, 10, 16, 12, 5, tzinfo=UTC),
        )


def test_manifest_rejects_tampered_checksum() -> None:
    manifest = complete_manifest()
    payload = manifest.model_dump()
    payload["input_checksum"] = "0" * 64

    with pytest.raises(ValidationError, match="input checksum is inconsistent"):
        MarketContextInputManifest.model_validate(payload)


def test_feature_definition_orders_requirements_and_detects_tampering() -> None:
    definition = feature_definition()

    assert tuple(item.feature_key for item in definition.requirements) == (
        "trend_slope_1h",
        "volatility_1d",
    )

    payload = definition.model_dump()
    payload["requirements"][0]["lookback_windows"] = 25
    with pytest.raises(ValidationError, match="definition checksum is inconsistent"):
        MarketContextFeatureSetDefinition.model_validate(payload)


def test_feature_snapshot_rejects_an_incomplete_feature_set() -> None:
    manifest = complete_manifest()
    evidence = MarketContextEvidence(
        feature_key="trend_slope_1h",
        timeframe=Timeframe.HOUR_1,
        value=Decimal("0.013"),
        calculation_version="trend-slope-v1",
        window_reference_checksums=(manifest.windows[0].reference_checksum,),
    )

    with pytest.raises(ValueError, match="every feature-set requirement"):
        MarketContextFeatureSnapshot.build(
            manifest=manifest,
            feature_set=feature_definition(),
            features=(evidence,),
            calculated_at=datetime(2026, 10, 16, 12, 5, tzinfo=UTC),
        )


def test_ready_regime_requires_determinate_evidence_and_expiry() -> None:
    manifest = complete_manifest()
    definition = MarketContextFeatureSetDefinition.build(
        feature_set_version="market-context-features-v1",
        requirements=(
            MarketContextFeatureRequirement(
                feature_key="trend_slope_1h",
                timeframe=Timeframe.HOUR_1,
                lookback_windows=1,
                calculation_version="trend-slope-v1",
            ),
        ),
    )
    assessed_at = datetime(2026, 10, 16, 12, 6, tzinfo=UTC)
    assessment_id = build_market_regime_assessment_id(
        source=SOURCE,
        pair=PAIR,
        as_of=manifest.as_of,
        input_checksum=manifest.input_checksum,
        feature_set_version=definition.feature_set_version,
        algorithm_version="market-regime-v1",
    )
    evidence = MarketContextEvidence(
        feature_key="trend_slope_1h",
        timeframe=Timeframe.HOUR_1,
        value=Decimal("0.013"),
        calculation_version="trend-slope-v1",
        window_reference_checksums=(manifest.windows[0].reference_checksum,),
    )
    feature_snapshot = MarketContextFeatureSnapshot.build(
        manifest=manifest,
        feature_set=definition,
        features=(evidence,),
        calculated_at=assessed_at,
    )

    assessment = MarketRegimeAssessment(
        assessment_id=assessment_id,
        source=SOURCE,
        pair=PAIR,
        as_of=manifest.as_of,
        input_manifest_id=manifest.manifest_id,
        input_checksum=manifest.input_checksum,
        feature_set_version=definition.feature_set_version,
        feature_set_checksum=definition.definition_checksum,
        feature_snapshot_id=feature_snapshot.snapshot_id,
        feature_snapshot_checksum=feature_snapshot.snapshot_checksum,
        algorithm_version="market-regime-v1",
        status=MarketContextAssessmentStatus.READY,
        trend=MarketTrendRegime.TRENDING_UP,
        volatility=MarketVolatilityRegime.NORMAL,
        confidence=Decimal("0.82"),
        evidence=(evidence,),
        assessed_at=assessed_at,
        expires_at=assessed_at + timedelta(hours=1),
    )

    assert assessment.status is MarketContextAssessmentStatus.READY
    assert assessment.confidence == Decimal("0.82")

    payload = assessment.model_dump()
    payload["evidence"] = []
    with pytest.raises(ValidationError, match="ready assessment requires"):
        MarketRegimeAssessment.model_validate(payload)

    payload = assessment.model_dump()
    payload["input_manifest_id"] = "market-context-input-0000000000000000"
    with pytest.raises(ValidationError, match="manifest identity is inconsistent"):
        MarketRegimeAssessment.model_validate(payload)


@pytest.mark.parametrize(
    "status",
    [MarketContextAssessmentStatus.INSUFFICIENT_DATA, MarketContextAssessmentStatus.STALE],
)
def test_non_ready_regime_cannot_expose_a_partial_decision(
    status: MarketContextAssessmentStatus,
) -> None:
    manifest = complete_manifest()
    definition = feature_definition()
    assessed_at = datetime(2026, 10, 16, 12, 6, tzinfo=UTC)
    common = {
        "assessment_id": build_market_regime_assessment_id(
            source=SOURCE,
            pair=PAIR,
            as_of=manifest.as_of,
            input_checksum=manifest.input_checksum,
            feature_set_version=definition.feature_set_version,
            algorithm_version="market-regime-v1",
        ),
        "source": SOURCE,
        "pair": PAIR,
        "as_of": manifest.as_of,
        "input_manifest_id": manifest.manifest_id,
        "input_checksum": manifest.input_checksum,
        "feature_set_version": definition.feature_set_version,
        "feature_set_checksum": definition.definition_checksum,
        "algorithm_version": "market-regime-v1",
        "status": status,
        "volatility": MarketVolatilityRegime.UNDETERMINED,
        "confidence": Decimal("0"),
        "issue_codes": ("missing_finalized_windows",),
        "assessed_at": assessed_at,
        "expires_at": assessed_at,
    }

    assessment = MarketRegimeAssessment.model_validate(
        {"trend": MarketTrendRegime.UNDETERMINED, **common}
    )
    assert assessment.status is status

    with pytest.raises(ValidationError, match="cannot expose a partial regime"):
        MarketRegimeAssessment.model_validate({"trend": MarketTrendRegime.RANGING, **common})
