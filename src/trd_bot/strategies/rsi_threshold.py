from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from trd_bot.indicators import relative_strength_index
from trd_bot.strategies.base import BaseStrategy
from trd_bot.strategies.signals import (
    SignalDirection,
    StrategyFeature,
    StrategySignal,
    build_signal_id,
)

if TYPE_CHECKING:
    from trd_bot.research.datasets import DatasetSnapshot


class RSIThresholdStrategy(BaseStrategy):
    """Generate mean-reversion signals when RSI enters an extreme region."""

    def __init__(
        self,
        period: int = 14,
        oversold_threshold: Decimal = Decimal("30"),
        overbought_threshold: Decimal = Decimal("70"),
    ) -> None:
        if period < 2:
            raise ValueError("RSI period must be at least 2")

        if not Decimal("0") < oversold_threshold < Decimal("50"):
            raise ValueError("oversold RSI threshold must be between 0 and 50")

        if not Decimal("50") < overbought_threshold < Decimal("100"):
            raise ValueError("overbought RSI threshold must be between 50 and 100")

        self.period = period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold

    @property
    def name(self) -> str:
        return "rsi-threshold"

    @property
    def version(self) -> str:
        return "1.0.0"

    def generate(
        self,
        dataset: DatasetSnapshot,
    ) -> tuple[StrategySignal, ...]:
        close_prices = [candle.close_price for candle in dataset.candles]

        rsi_values = relative_strength_index(
            close_prices,
            self.period,
        )

        signals: list[StrategySignal] = []

        for index in range(1, len(dataset.candles)):
            previous_rsi = rsi_values[index - 1]
            current_rsi = rsi_values[index]

            if previous_rsi is None or current_rsi is None:
                continue

            direction: SignalDirection | None = None
            threshold: Decimal | None = None

            if previous_rsi > self.oversold_threshold and current_rsi <= self.oversold_threshold:
                direction = SignalDirection.LONG
                threshold = self.oversold_threshold

            elif (
                previous_rsi < self.overbought_threshold
                and current_rsi >= self.overbought_threshold
            ):
                direction = SignalDirection.SHORT
                threshold = self.overbought_threshold

            if direction is None or threshold is None:
                continue

            candle = dataset.candles[index]

            if direction is SignalDirection.LONG:
                score = (Decimal("50") - current_rsi) / Decimal("50")
                reason = "RSI crossed into the oversold region."
            else:
                score = -((current_rsi - Decimal("50")) / Decimal("50"))
                reason = "RSI crossed into the overbought region."

            score = max(
                Decimal("-1"),
                min(Decimal("1"), score),
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
                            name="previous_rsi",
                            value=previous_rsi,
                        ),
                        StrategyFeature(
                            name="rsi",
                            value=current_rsi,
                        ),
                        StrategyFeature(
                            name="threshold",
                            value=threshold,
                        ),
                        StrategyFeature(
                            name="close_price",
                            value=candle.close_price,
                        ),
                    ),
                )
            )

        return tuple(signals)
