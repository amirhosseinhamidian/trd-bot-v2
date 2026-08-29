from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from trd_bot.strategies.base import BaseStrategy
from trd_bot.strategies.ema_crossover import EMACrossoverStrategy
from trd_bot.strategies.rsi_threshold import RSIThresholdStrategy

StrategyParameterValue = str | int | Decimal | bool
StrategyFactory = Callable[[Mapping[str, StrategyParameterValue]], BaseStrategy]


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    """One versioned strategy factory registered for research execution."""

    name: str
    version: str
    factory: StrategyFactory

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("strategy definition name cannot be empty")

        if not self.version.strip():
            raise ValueError("strategy definition version cannot be empty")

    def create(
        self,
        parameters: Mapping[str, StrategyParameterValue],
    ) -> BaseStrategy:
        strategy = self.factory(parameters)

        if strategy.name != self.name:
            raise ValueError("strategy factory returned an unexpected strategy name")

        if strategy.version != self.version:
            raise ValueError("strategy factory returned an unexpected strategy version")

        return strategy


class StrategyRegistry:
    """Resolve versioned research strategies without runner-specific branching."""

    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str], StrategyDefinition] = {}

    def register(
        self,
        definition: StrategyDefinition,
    ) -> None:
        key = (definition.name, definition.version)

        if key in self._definitions:
            raise ValueError(
                f"strategy {definition.name!r} version {definition.version!r} is already registered"
            )

        self._definitions[key] = definition

    def get(
        self,
        *,
        name: str,
        version: str,
    ) -> StrategyDefinition | None:
        return self._definitions.get((name, version))

    def require(
        self,
        *,
        name: str,
        version: str,
    ) -> StrategyDefinition:
        definition = self.get(
            name=name,
            version=version,
        )

        if definition is None:
            raise ValueError(f"unknown strategy {name!r} version {version!r}")

        return definition

    def create(
        self,
        *,
        name: str,
        version: str,
        parameters: Mapping[str, StrategyParameterValue],
    ) -> BaseStrategy:
        definition = self.require(
            name=name,
            version=version,
        )

        return definition.create(parameters)

    def list_definitions(self) -> tuple[StrategyDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))


def _require_exact_parameters(
    parameters: Mapping[str, StrategyParameterValue],
    *,
    expected: frozenset[str],
) -> None:
    received = frozenset(parameters)

    missing = sorted(expected - received)
    if missing:
        raise ValueError(f"missing strategy parameter: {missing[0]}")

    unexpected = sorted(received - expected)
    if unexpected:
        raise ValueError(f"unexpected strategy parameter: {unexpected[0]}")


def _require_int_parameter(
    parameters: Mapping[str, StrategyParameterValue],
    name: str,
) -> int:
    value = parameters[name]

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"strategy parameter {name!r} must be an integer")

    return value


def _require_decimal_parameter(
    parameters: Mapping[str, StrategyParameterValue],
    name: str,
) -> Decimal:
    value = parameters[name]

    if isinstance(value, bool):
        raise ValueError(f"strategy parameter {name!r} must be a decimal")

    if isinstance(value, Decimal):
        return value

    if isinstance(value, int):
        return Decimal(value)

    raise ValueError(f"strategy parameter {name!r} must be a decimal")


def _build_ema_crossover(
    parameters: Mapping[str, StrategyParameterValue],
) -> BaseStrategy:
    _require_exact_parameters(
        parameters,
        expected=frozenset(
            {
                "fast_period",
                "slow_period",
            }
        ),
    )

    return EMACrossoverStrategy(
        fast_period=_require_int_parameter(parameters, "fast_period"),
        slow_period=_require_int_parameter(parameters, "slow_period"),
    )


def _build_rsi_threshold(
    parameters: Mapping[str, StrategyParameterValue],
) -> BaseStrategy:
    _require_exact_parameters(
        parameters,
        expected=frozenset(
            {
                "period",
                "oversold_threshold",
                "overbought_threshold",
            }
        ),
    )

    return RSIThresholdStrategy(
        period=_require_int_parameter(parameters, "period"),
        oversold_threshold=_require_decimal_parameter(
            parameters,
            "oversold_threshold",
        ),
        overbought_threshold=_require_decimal_parameter(
            parameters,
            "overbought_threshold",
        ),
    )


def build_default_strategy_registry() -> StrategyRegistry:
    """Build the registry used by historical research execution runners."""

    registry = StrategyRegistry()

    registry.register(
        StrategyDefinition(
            name="ema-crossover",
            version="1.0.0",
            factory=_build_ema_crossover,
        )
    )
    registry.register(
        StrategyDefinition(
            name="rsi-threshold",
            version="1.0.0",
            factory=_build_rsi_threshold,
        )
    )

    return registry
