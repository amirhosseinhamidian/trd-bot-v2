from collections.abc import Mapping
from decimal import Decimal

import pytest

from trd_bot.strategies import (
    EMACrossoverStrategy,
    RSIThresholdStrategy,
    SMACrossoverStrategy,
    StrategyDefinition,
    StrategyRegistry,
    build_default_strategy_registry,
)
from trd_bot.strategies.base import BaseStrategy


def test_default_registry_builds_ema_crossover() -> None:
    registry = build_default_strategy_registry()

    strategy = registry.create(
        name="ema-crossover",
        version="1.0.0",
        parameters={
            "fast_period": 2,
            "slow_period": 3,
        },
    )

    assert isinstance(strategy, EMACrossoverStrategy)
    assert strategy.name == "ema-crossover"
    assert strategy.version == "1.0.0"
    assert strategy.fast_period == 2
    assert strategy.slow_period == 3


def test_registry_lists_definitions_deterministically() -> None:
    registry = build_default_strategy_registry()

    definitions = registry.list_definitions()

    assert [(definition.name, definition.version) for definition in definitions] == [
        ("ema-crossover", "1.0.0"),
        ("rsi-threshold", "1.0.0"),
        ("sma-crossover", "1.0.0"),
    ]


def test_default_registry_exposes_versioned_parameter_metadata() -> None:
    metadata = build_default_strategy_registry().list_metadata()

    assert [item.name for item in metadata] == [
        "ema-crossover",
        "rsi-threshold",
        "sma-crossover",
    ]

    ema, rsi, sma = metadata

    assert ema.display_name == "EMA Crossover"
    assert [(item.name, item.default_value) for item in ema.parameters] == [
        ("fast_period", "9"),
        ("slow_period", "21"),
    ]

    assert rsi.display_name == "RSI Threshold"
    assert [item.name for item in rsi.parameters] == [
        "period",
        "oversold_threshold",
        "overbought_threshold",
    ]
    assert rsi.parameters[1].minimum == "0"
    assert rsi.parameters[1].maximum == "50"
    assert rsi.parameters[1].minimum_exclusive is True
    assert rsi.parameters[1].maximum_exclusive is True

    assert sma.display_name == "SMA Crossover"
    assert [(item.name, item.default_value) for item in sma.parameters] == [
        ("fast_period", "9"),
        ("slow_period", "21"),
    ]


def test_default_registry_builds_rsi_threshold() -> None:
    registry = build_default_strategy_registry()

    strategy = registry.create(
        name="rsi-threshold",
        version="1.0.0",
        parameters={
            "period": 14,
            "oversold_threshold": Decimal("30"),
            "overbought_threshold": Decimal("70"),
        },
    )

    assert isinstance(strategy, RSIThresholdStrategy)
    assert strategy.period == 14
    assert strategy.oversold_threshold == Decimal("30")
    assert strategy.overbought_threshold == Decimal("70")


def test_default_registry_builds_sma_crossover() -> None:
    registry = build_default_strategy_registry()

    strategy = registry.create(
        name="sma-crossover",
        version="1.0.0",
        parameters={
            "fast_period": 2,
            "slow_period": 3,
        },
    )

    assert isinstance(strategy, SMACrossoverStrategy)
    assert strategy.fast_period == 2
    assert strategy.slow_period == 3


def test_rsi_factory_accepts_integer_thresholds_without_floats() -> None:
    registry = build_default_strategy_registry()

    strategy = registry.create(
        name="rsi-threshold",
        version="1.0.0",
        parameters={
            "period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
        },
    )

    assert isinstance(strategy, RSIThresholdStrategy)
    assert strategy.oversold_threshold == Decimal("30")
    assert strategy.overbought_threshold == Decimal("70")


def test_registry_rejects_unknown_strategy_version() -> None:
    registry = build_default_strategy_registry()

    with pytest.raises(
        ValueError,
        match="unknown strategy",
    ):
        registry.create(
            name="ema-crossover",
            version="2.0.0",
            parameters={
                "fast_period": 2,
                "slow_period": 3,
            },
        )


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        (
            {
                "slow_period": 3,
            },
            "missing strategy parameter",
        ),
        (
            {
                "fast_period": 2,
                "slow_period": 3,
                "threshold": Decimal("0.5"),
            },
            "unexpected strategy parameter",
        ),
        (
            {
                "fast_period": "2",
                "slow_period": 3,
            },
            "must be an integer",
        ),
    ],
)
def test_ema_factory_validates_parameter_contract(
    parameters: dict[str, str | int | Decimal],
    message: str,
) -> None:
    registry = build_default_strategy_registry()

    with pytest.raises(
        ValueError,
        match=message,
    ):
        registry.create(
            name="ema-crossover",
            version="1.0.0",
            parameters=parameters,
        )


def test_registry_rejects_duplicate_definition() -> None:
    registry = build_default_strategy_registry()
    definition = registry.require(
        name="ema-crossover",
        version="1.0.0",
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(definition)


def test_definition_rejects_mismatched_metadata_identity() -> None:
    metadata = build_default_strategy_registry().list_metadata()[0]

    with pytest.raises(
        ValueError,
        match="metadata name",
    ):
        StrategyDefinition(
            name="different-strategy",
            version=metadata.version,
            factory=lambda _parameters: EMACrossoverStrategy(
                fast_period=2,
                slow_period=3,
            ),
            metadata=metadata,
        )


def test_definition_rejects_factory_identity_mismatch() -> None:
    registry = StrategyRegistry()

    def build_ema(
        parameters: Mapping[str, str | int | Decimal | bool],
    ) -> BaseStrategy:
        del parameters
        return EMACrossoverStrategy(
            fast_period=2,
            slow_period=3,
        )

    registry.register(
        StrategyDefinition(
            name="different-strategy",
            version="1.0.0",
            factory=build_ema,
        )
    )

    with pytest.raises(
        ValueError,
        match="unexpected strategy name",
    ):
        registry.create(
            name="different-strategy",
            version="1.0.0",
            parameters={},
        )
