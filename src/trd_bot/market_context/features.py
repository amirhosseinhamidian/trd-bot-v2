from collections.abc import Callable, Sequence
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from itertools import pairwise
from typing import Final

from trd_bot.domain.market_data import Timeframe
from trd_bot.market_context.contracts import (
    MarketContextEvidence,
    MarketContextFeatureRequirement,
    MarketContextFeatureSetDefinition,
    MarketContextFeatureSnapshot,
    MarketContextInputManifest,
    MarketContextWindowReference,
)
from trd_bot.market_data.events import MarketDataWindowSnapshot

MARKET_CONTEXT_FEATURE_SET_V1_VERSION: Final = "market-context-features-v1"
MARKET_CONTEXT_FEATURE_DECIMAL_PLACES: Final = 12
MARKET_CONTEXT_FEATURE_QUANTUM: Final = Decimal("0.000000000001")
NORMALIZED_CLOSE_SLOPE_V1: Final = "normalized-close-slope-v1"
CLOSE_RETURN_VOLATILITY_V1: Final = "close-return-volatility-v1"


def market_context_feature_set_v1() -> MarketContextFeatureSetDefinition:
    """Return the frozen deterministic feature definition used by P3 v1."""

    return MarketContextFeatureSetDefinition.build(
        feature_set_version=MARKET_CONTEXT_FEATURE_SET_V1_VERSION,
        requirements=(
            MarketContextFeatureRequirement(
                feature_key="realized_volatility_1d",
                timeframe=Timeframe.DAY_1,
                lookback_windows=14,
                calculation_version=CLOSE_RETURN_VOLATILITY_V1,
            ),
            MarketContextFeatureRequirement(
                feature_key="realized_volatility_1h",
                timeframe=Timeframe.HOUR_1,
                lookback_windows=24,
                calculation_version=CLOSE_RETURN_VOLATILITY_V1,
            ),
            MarketContextFeatureRequirement(
                feature_key="trend_slope_1d",
                timeframe=Timeframe.DAY_1,
                lookback_windows=14,
                calculation_version=NORMALIZED_CLOSE_SLOPE_V1,
            ),
            MarketContextFeatureRequirement(
                feature_key="trend_slope_1h",
                timeframe=Timeframe.HOUR_1,
                lookback_windows=24,
                calculation_version=NORMALIZED_CLOSE_SLOPE_V1,
            ),
            MarketContextFeatureRequirement(
                feature_key="trend_slope_4h",
                timeframe=Timeframe.HOURS_4,
                lookback_windows=18,
                calculation_version=NORMALIZED_CLOSE_SLOPE_V1,
            ),
        ),
    )


def calculate_normalized_close_slope(closes: Sequence[Decimal]) -> Decimal:
    """Calculate OLS slope per window after normalizing closes by the first close."""

    values = tuple(closes)
    if len(values) < 2:
        raise ValueError("normalized close slope requires at least two closes")
    if any(not value.is_finite() or value <= 0 for value in values):
        raise ValueError("normalized close slope requires positive finite closes")

    with localcontext() as context:
        context.prec = 50
        first = values[0]
        normalized = tuple(value / first for value in values)
        count = Decimal(len(normalized))
        x_mean = Decimal(len(normalized) - 1) / Decimal(2)
        y_mean = sum(normalized, start=Decimal(0)) / count
        numerator = sum(
            (
                (Decimal(index) - x_mean) * (value - y_mean)
                for index, value in enumerate(normalized)
            ),
            start=Decimal(0),
        )
        denominator = sum(
            ((Decimal(index) - x_mean) ** 2 for index in range(len(normalized))),
            start=Decimal(0),
        )
        return _quantize_feature(numerator / denominator)


def calculate_close_return_volatility(closes: Sequence[Decimal]) -> Decimal:
    """Calculate non-annualized population deviation of simple close returns."""

    values = tuple(closes)
    if len(values) < 2:
        raise ValueError("close-return volatility requires at least two closes")
    if any(not value.is_finite() or value <= 0 for value in values):
        raise ValueError("close-return volatility requires positive finite closes")

    with localcontext() as context:
        context.prec = 50
        returns = tuple(current / previous - Decimal(1) for previous, current in pairwise(values))
        mean = sum(returns, start=Decimal(0)) / Decimal(len(returns))
        variance = sum(
            ((value - mean) ** 2 for value in returns),
            start=Decimal(0),
        ) / Decimal(len(returns))
        return _quantize_feature(variance.sqrt())


def calculate_market_context_feature_snapshot_v1(
    *,
    manifest: MarketContextInputManifest,
    windows: tuple[MarketDataWindowSnapshot, ...],
) -> MarketContextFeatureSnapshot:
    """Calculate the complete v1 feature snapshot from exact manifest lineage."""

    feature_set = market_context_feature_set_v1()
    snapshots = _validate_and_order_manifest_windows(manifest=manifest, windows=windows)
    snapshots_by_timeframe: dict[Timeframe, list[MarketDataWindowSnapshot]] = {
        timeframe: [] for timeframe in Timeframe
    }
    references_by_timeframe: dict[Timeframe, list[MarketContextWindowReference]] = {
        timeframe: [] for timeframe in Timeframe
    }
    for reference, snapshot in zip(manifest.windows, snapshots, strict=True):
        snapshots_by_timeframe[reference.timeframe].append(snapshot)
        references_by_timeframe[reference.timeframe].append(reference)

    formulas: dict[str, Callable[[Sequence[Decimal]], Decimal]] = {
        CLOSE_RETURN_VOLATILITY_V1: calculate_close_return_volatility,
        NORMALIZED_CLOSE_SLOPE_V1: calculate_normalized_close_slope,
    }
    features: list[MarketContextEvidence] = []
    for requirement in feature_set.requirements:
        source_windows = snapshots_by_timeframe[requirement.timeframe]
        source_references = references_by_timeframe[requirement.timeframe]
        if len(source_windows) < requirement.lookback_windows:
            raise ValueError("input manifest does not satisfy the v1 feature lookback")
        selected_windows = source_windows[-requirement.lookback_windows :]
        selected_references = source_references[-requirement.lookback_windows :]
        formula = formulas[requirement.calculation_version]
        value = formula(tuple(item.candle.close_price for item in selected_windows))
        features.append(
            MarketContextEvidence(
                feature_key=requirement.feature_key,
                timeframe=requirement.timeframe,
                value=value,
                calculation_version=requirement.calculation_version,
                window_reference_checksums=tuple(
                    item.reference_checksum for item in selected_references
                ),
            )
        )

    logical_calculation_time = max(
        manifest.created_at,
        max(reference.finalized_at for reference in manifest.windows),
    )
    return MarketContextFeatureSnapshot.build(
        manifest=manifest,
        feature_set=feature_set,
        features=tuple(features),
        calculated_at=logical_calculation_time,
    )


def _validate_and_order_manifest_windows(
    *,
    manifest: MarketContextInputManifest,
    windows: tuple[MarketDataWindowSnapshot, ...],
) -> tuple[MarketDataWindowSnapshot, ...]:
    by_identity: dict[tuple[str, int], MarketDataWindowSnapshot] = {}
    for snapshot in windows:
        identity = (snapshot.window_id, snapshot.version)
        if identity in by_identity:
            raise ValueError("feature calculation received a duplicate window version")
        by_identity[identity] = snapshot

    expected_identities = {(item.window_id, item.version) for item in manifest.windows}
    if set(by_identity) != expected_identities:
        raise ValueError("feature calculation windows do not exactly match the input manifest")

    ordered: list[MarketDataWindowSnapshot] = []
    for reference in manifest.windows:
        snapshot = by_identity[(reference.window_id, reference.version)]
        if MarketContextWindowReference.from_snapshot(snapshot) != reference:
            raise ValueError("feature calculation window lineage does not match the manifest")
        ordered.append(snapshot)
    return tuple(ordered)


def _quantize_feature(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("market-context feature calculation produced a non-finite value")
    return value.quantize(MARKET_CONTEXT_FEATURE_QUANTUM, rounding=ROUND_HALF_EVEN)
