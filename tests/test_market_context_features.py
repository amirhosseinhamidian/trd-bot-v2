from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trd_bot.db import (
    DatabaseBase,
    MarketContextFeatureSnapshotRow,
    SqlAlchemyMarketContextFeatureCalculator,
    SqlAlchemyMarketContextStore,
    SqlAlchemyMarketDataEventStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_context import (
    CLOSE_RETURN_VOLATILITY_V1,
    MARKET_CONTEXT_FEATURE_DECIMAL_PLACES,
    MARKET_CONTEXT_FEATURE_QUANTUM,
    MARKET_CONTEXT_FEATURE_SET_V1_VERSION,
    NORMALIZED_CLOSE_SLOPE_V1,
    MarketContextInputManifest,
    MarketContextWindowReference,
    calculate_close_return_volatility,
    calculate_market_context_feature_snapshot_v1,
    calculate_normalized_close_slope,
    market_context_feature_set_v1,
)
from trd_bot.market_data import MarketDataEvent, MarketDataWindowSnapshot, MarketDataWindowState

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"
AS_OF = datetime(2026, 10, 16, 12, tzinfo=UTC)


def finalized_window(
    *,
    timeframe: Timeframe,
    window_start: datetime,
    close_price: Decimal,
) -> MarketDataWindowSnapshot:
    window_end = window_start + timeframe.duration
    candle = OHLCVCandle(
        source=SOURCE,
        pair=PAIR,
        timeframe=timeframe,
        open_time=window_start,
        close_time=window_end,
        received_at=window_end + timedelta(seconds=30),
        open_price=close_price,
        high_price=close_price + Decimal(1),
        low_price=close_price - Decimal(1),
        close_price=close_price,
        volume=Decimal("1250"),
    )
    event = MarketDataEvent.from_candle(candle)
    return MarketDataWindowSnapshot(
        window_id=event.window_id,
        version=2,
        state=MarketDataWindowState.FINALIZED,
        source=SOURCE,
        pair=PAIR,
        timeframe=timeframe,
        window_start=window_start,
        window_end=window_end,
        event_id=event.event_id,
        payload_checksum=event.payload_checksum,
        candle=candle,
        created_at=window_end + timedelta(seconds=30),
        finalized_at=window_end + timedelta(minutes=1),
    )


def geometric_windows(
    *,
    timeframe: Timeframe,
    count: int,
    expected_end: datetime,
    first_close: str,
    factor: str,
) -> tuple[MarketDataWindowSnapshot, ...]:
    base = Decimal(first_close)
    growth = Decimal(factor)
    return tuple(
        finalized_window(
            timeframe=timeframe,
            window_start=expected_end - timeframe.duration * (count - index),
            close_price=base * growth**index,
        )
        for index in range(count)
    )


def complete_input() -> tuple[
    tuple[MarketDataWindowSnapshot, ...],
    MarketContextInputManifest,
]:
    windows = (
        *geometric_windows(
            timeframe=Timeframe.HOUR_1,
            count=24,
            expected_end=AS_OF,
            first_close="100",
            factor="1.01",
        ),
        *geometric_windows(
            timeframe=Timeframe.HOURS_4,
            count=18,
            expected_end=AS_OF,
            first_close="200",
            factor="1.005",
        ),
        *geometric_windows(
            timeframe=Timeframe.DAY_1,
            count=14,
            expected_end=datetime(2026, 10, 16, tzinfo=UTC),
            first_close="300",
            factor="0.99",
        ),
    )
    manifest = MarketContextInputManifest.build(
        source=SOURCE,
        pair=PAIR,
        as_of=AS_OF,
        windows=tuple(MarketContextWindowReference.from_snapshot(item) for item in windows),
        created_at=AS_OF,
    )
    return windows, manifest


def test_v1_feature_definition_is_frozen_with_exact_versions_and_precision() -> None:
    definition = market_context_feature_set_v1()

    assert definition.feature_set_version == MARKET_CONTEXT_FEATURE_SET_V1_VERSION
    assert definition.definition_checksum == (
        "50b734675aa69382002e87e0d2a512d28182dc24048d708874936715c70ac683"
    )
    assert MARKET_CONTEXT_FEATURE_DECIMAL_PLACES == 12
    assert Decimal("0.000000000001") == MARKET_CONTEXT_FEATURE_QUANTUM
    assert tuple(
        (
            item.feature_key,
            item.timeframe,
            item.lookback_windows,
            item.calculation_version,
        )
        for item in definition.requirements
    ) == (
        ("realized_volatility_1d", Timeframe.DAY_1, 14, CLOSE_RETURN_VOLATILITY_V1),
        ("realized_volatility_1h", Timeframe.HOUR_1, 24, CLOSE_RETURN_VOLATILITY_V1),
        ("trend_slope_1d", Timeframe.DAY_1, 14, NORMALIZED_CLOSE_SLOPE_V1),
        ("trend_slope_1h", Timeframe.HOUR_1, 24, NORMALIZED_CLOSE_SLOPE_V1),
        ("trend_slope_4h", Timeframe.HOURS_4, 18, NORMALIZED_CLOSE_SLOPE_V1),
    )


def test_feature_formulas_match_small_golden_vectors() -> None:
    assert calculate_normalized_close_slope(
        (Decimal("100"), Decimal("110"), Decimal("120"))
    ) == Decimal("0.100000000000")
    assert calculate_normalized_close_slope(
        (Decimal("100"), Decimal("100"), Decimal("100"))
    ) == Decimal("0E-12")
    assert calculate_close_return_volatility(
        (Decimal("100"), Decimal("110"), Decimal("99"))
    ) == Decimal("0.100000000000")
    assert calculate_close_return_volatility(
        (Decimal("100"), Decimal("101"), Decimal("102.01"))
    ) == Decimal("0E-12")


@pytest.mark.parametrize(
    "calculator",
    [calculate_normalized_close_slope, calculate_close_return_volatility],
)
def test_feature_formulas_fail_closed_for_invalid_values(
    calculator: Callable[[tuple[Decimal, ...]], Decimal],
) -> None:
    with pytest.raises(ValueError, match="at least two closes"):
        calculator((Decimal("100"),))
    with pytest.raises(ValueError, match="positive finite closes"):
        calculator((Decimal("100"), Decimal("0")))
    with pytest.raises(ValueError, match="positive finite closes"):
        calculator((Decimal("100"), Decimal("NaN")))


def test_complete_v1_snapshot_is_deterministic_and_carries_exact_lineage() -> None:
    windows, manifest = complete_input()

    first = calculate_market_context_feature_snapshot_v1(
        manifest=manifest,
        windows=tuple(reversed(windows)),
    )
    second = calculate_market_context_feature_snapshot_v1(
        manifest=manifest,
        windows=windows,
    )

    assert first == second
    assert first.calculated_at == AS_OF + timedelta(minutes=1)
    assert first.feature_set_checksum == market_context_feature_set_v1().definition_checksum
    assert first.snapshot_id == "market-context-features-da0510397d66162a"
    assert first.snapshot_checksum == (
        "da0510397d66162a14cadb604ca7b51b6478f105849e12923637ace37fdc515a"
    )
    assert tuple(item.feature_key for item in first.features) == (
        "realized_volatility_1d",
        "realized_volatility_1h",
        "trend_slope_1d",
        "trend_slope_1h",
        "trend_slope_4h",
    )
    values = {item.feature_key: item.value for item in first.features}
    assert values == {
        "realized_volatility_1d": Decimal("0E-12"),
        "realized_volatility_1h": Decimal("0E-12"),
        "trend_slope_1d": Decimal("-0.009419366987"),
        "trend_slope_1h": Decimal("0.011172487385"),
        "trend_slope_4h": Decimal("0.005204570820"),
    }
    requirement_by_key = {
        item.feature_key: item for item in market_context_feature_set_v1().requirements
    }
    assert all(
        len(item.window_reference_checksums)
        == requirement_by_key[item.feature_key].lookback_windows
        for item in first.features
    )


def test_feature_snapshot_rejects_missing_extra_or_changed_window_lineage() -> None:
    windows, manifest = complete_input()

    with pytest.raises(ValueError, match="exactly match"):
        calculate_market_context_feature_snapshot_v1(
            manifest=manifest,
            windows=windows[:-1],
        )
    with pytest.raises(ValueError, match="duplicate window version"):
        calculate_market_context_feature_snapshot_v1(
            manifest=manifest,
            windows=(*windows, windows[0]),
        )

    changed = finalized_window(
        timeframe=windows[0].timeframe,
        window_start=windows[0].window_start,
        close_price=windows[0].candle.close_price + Decimal("2"),
    )
    with pytest.raises(ValueError, match="lineage does not match"):
        calculate_market_context_feature_snapshot_v1(
            manifest=manifest,
            windows=(changed, *windows[1:]),
        )


def test_sqlalchemy_calculator_stages_one_idempotent_snapshot() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    windows, manifest = complete_input()

    try:
        with factory.begin() as session:
            window_store = SqlAlchemyMarketDataEventStore(session)
            for item in windows:
                window_store.stage_window_version(item)
            SqlAlchemyMarketContextStore(session).stage_input_manifest(manifest)

        with factory.begin() as session:
            calculator = SqlAlchemyMarketContextFeatureCalculator(session)
            first, first_created = calculator.calculate_and_stage(manifest_id=manifest.manifest_id)
            second, second_created = calculator.calculate_and_stage(
                manifest_id=manifest.manifest_id
            )

            assert first_created is True
            assert second_created is False
            assert first == second
            assert (
                session.scalar(select(func.count()).select_from(MarketContextFeatureSnapshotRow))
                == 1
            )
    finally:
        engine.dispose()


def test_sqlalchemy_calculator_requires_a_persisted_manifest() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with (
            factory() as session,
            pytest.raises(ValueError, match="input manifest does not exist"),
        ):
            SqlAlchemyMarketContextFeatureCalculator(session).calculate_and_stage(
                manifest_id="market-context-input-0000000000000000"
            )
    finally:
        engine.dispose()
