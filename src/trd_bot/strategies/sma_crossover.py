from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from trd_bot.indicators import simple_moving_average
from trd_bot.strategies.base import BaseStrategy
from trd_bot.strategies.signals import (
    SignalDirection,
    StrategyFeature,
    StrategySignal,
    build_signal_id,
)

if TYPE_CHECKING:
    from trd_bot.research.datasets import DatasetSnapshot


class SMACrossoverStrategy(BaseStrategy):
    """Generate research signals when fast and slow SMAs cross."""

    def __init__(
        self,
        fast_period: int = 9,
        slow_period: int = 21,
    ) -> None:
        if fast_period < 2:
            raise ValueError("fast SMA period must be at least 2")

        if slow_period <= fast_period:
            raise ValueError("slow SMA period must be greater than fast SMA period")

        self.fast_period = fast_period
        self.slow_period = slow_period

    @property
    def name(self) -> str:
        return "sma-crossover"

    @property
    def version(self) -> str:
        return "1.0.0"

    def generate(
        self,
        dataset: DatasetSnapshot,
    ) -> tuple[StrategySignal, ...]:
        close_prices = [candle.close_price for candle in dataset.candles]

        fast_sma_values = simple_moving_average(
            close_prices,
            self.fast_period,
        )

        slow_sma_values = simple_moving_average(
            close_prices,
            self.slow_period,
        )

        signals: list[StrategySignal] = []

        for index in range(1, len(dataset.candles)):
            previous_fast = fast_sma_values[index - 1]
            previous_slow = slow_sma_values[index - 1]
            current_fast = fast_sma_values[index]
            current_slow = slow_sma_values[index]

            if (
                previous_fast is None
                or previous_slow is None
                or current_fast is None
                or current_slow is None
            ):
                continue

            direction: SignalDirection | None = None

            if previous_fast <= previous_slow and current_fast > current_slow:
                direction = SignalDirection.LONG

            elif previous_fast >= previous_slow and current_fast < current_slow:
                direction = SignalDirection.SHORT

            if direction is None:
                continue

            candle = dataset.candles[index]

            score = (current_fast - current_slow) / candle.close_price

            score = max(
                Decimal("-1"),
                min(Decimal("1"), score),
            )

            reason = (
                "Fast SMA crossed above slow SMA."
                if direction == SignalDirection.LONG
                else "Fast SMA crossed below slow SMA."
            )

            signal_id = build_signal_id(
                strategy_name=self.name,
                strategy_version=self.version,
                dataset_id=dataset.dataset_id,
                candle_close_time=candle.close_time,
                direction=direction,
            )

            signals.append(
                StrategySignal(
                    signal_id=signal_id,
                    strategy_name=self.name,
                    strategy_version=self.version,
                    dataset_id=dataset.dataset_id,
                    pair=dataset.pair,
                    timeframe=dataset.timeframe,
                    candle_open_time=candle.open_time,
                    candle_close_time=candle.close_time,
                    generated_at=candle.close_time,
                    direction=direction,
                    score=score,
                    reason=reason,
                    features=(
                        StrategyFeature(
                            name="fast_sma",
                            value=current_fast,
                        ),
                        StrategyFeature(
                            name="slow_sma",
                            value=current_slow,
                        ),
                        StrategyFeature(
                            name="close_price",
                            value=candle.close_price,
                        ),
                    ),
                )
            )

        return tuple(signals)
