from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trd_bot.backtesting.models import (
    BacktestConfig,
    BacktestEvent,
    BacktestEventType,
    ExitReason,
    PositionSide,
    build_backtest_event_id,
)
from trd_bot.domain.market_data import TradingPair
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.strategies.signals import SignalDirection, StrategySignal


@dataclass(frozen=True, slots=True)
class _OpenPosition:
    side: PositionSide
    quantity: Decimal


class BacktestEngine:
    """Execute research signals against historical candles."""

    def run(
        self,
        *,
        run_id: str,
        dataset: DatasetSnapshot,
        signals: Sequence[StrategySignal],
        config: BacktestConfig,
    ) -> tuple[BacktestEvent, ...]:
        if not run_id.strip():
            raise ValueError("run ID cannot be empty")

        self._validate_signals(
            dataset=dataset,
            signals=signals,
        )

        scheduled_signals = self._schedule_signals(
            dataset=dataset,
            signals=signals,
        )

        events: list[BacktestEvent] = []
        current_position: _OpenPosition | None = None
        sequence_number = 1

        allocation = config.starting_balance * config.allocation_fraction

        for candle in dataset.candles:
            signal = scheduled_signals.get(candle.open_time)

            if signal is None:
                continue

            target_side = self._direction_to_side(signal.direction)

            if current_position is not None and current_position.side == target_side:
                continue

            if current_position is not None:
                exit_price = self._apply_slippage(
                    market_price=candle.open_price,
                    side=current_position.side,
                    opening=False,
                    slippage_rate=config.slippage_rate,
                )

                events.append(
                    self._create_event(
                        run_id=run_id,
                        sequence_number=sequence_number,
                        event_type=(BacktestEventType.POSITION_CLOSED),
                        timestamp=candle.open_time,
                        pair=dataset.pair,
                        side=current_position.side,
                        price=exit_price,
                        quantity=current_position.quantity,
                        signal_id=signal.signal_id,
                        exit_reason=ExitReason.OPPOSITE_SIGNAL,
                    )
                )

                sequence_number += 1
                current_position = None

            entry_price = self._apply_slippage(
                market_price=candle.open_price,
                side=target_side,
                opening=True,
                slippage_rate=config.slippage_rate,
            )

            quantity = allocation / entry_price

            events.append(
                self._create_event(
                    run_id=run_id,
                    sequence_number=sequence_number,
                    event_type=(BacktestEventType.POSITION_OPENED),
                    timestamp=candle.open_time,
                    pair=dataset.pair,
                    side=target_side,
                    price=entry_price,
                    quantity=quantity,
                    signal_id=signal.signal_id,
                    exit_reason=None,
                )
            )

            sequence_number += 1

            current_position = _OpenPosition(
                side=target_side,
                quantity=quantity,
            )

        if current_position is not None:
            final_candle = dataset.candles[-1]

            final_exit_price = self._apply_slippage(
                market_price=final_candle.close_price,
                side=current_position.side,
                opening=False,
                slippage_rate=config.slippage_rate,
            )

            events.append(
                self._create_event(
                    run_id=run_id,
                    sequence_number=sequence_number,
                    event_type=(BacktestEventType.POSITION_CLOSED),
                    timestamp=final_candle.close_time,
                    pair=dataset.pair,
                    side=current_position.side,
                    price=final_exit_price,
                    quantity=current_position.quantity,
                    signal_id=None,
                    exit_reason=ExitReason.END_OF_DATA,
                )
            )

        return tuple(events)

    @staticmethod
    def _validate_signals(
        *,
        dataset: DatasetSnapshot,
        signals: Sequence[StrategySignal],
    ) -> None:
        candle_windows = {
            (
                candle.open_time,
                candle.close_time,
            )
            for candle in dataset.candles
        }

        for signal in signals:
            if signal.dataset_id != dataset.dataset_id:
                raise ValueError("signal does not belong to the dataset")

            if signal.pair != dataset.pair:
                raise ValueError("signal pair does not match the dataset")

            if signal.timeframe != dataset.timeframe:
                raise ValueError("signal timeframe does not match the dataset")

            signal_window = (
                signal.candle_open_time,
                signal.candle_close_time,
            )

            if signal_window not in candle_windows:
                raise ValueError("signal candle does not exist in the dataset")

    @staticmethod
    def _schedule_signals(
        *,
        dataset: DatasetSnapshot,
        signals: Sequence[StrategySignal],
    ) -> dict[datetime, StrategySignal]:
        candle_open_times = {candle.open_time for candle in dataset.candles}

        scheduled: dict[datetime, StrategySignal] = {}

        for signal in sorted(
            signals,
            key=lambda item: item.candle_close_time,
        ):
            if signal.direction == SignalDirection.NEUTRAL:
                continue

            execution_time = signal.candle_close_time

            if execution_time not in candle_open_times:
                continue

            if execution_time in scheduled:
                raise ValueError("multiple signals cannot execute at the same time")

            scheduled[execution_time] = signal

        return scheduled

    @staticmethod
    def _direction_to_side(
        direction: SignalDirection,
    ) -> PositionSide:
        if direction == SignalDirection.LONG:
            return PositionSide.LONG

        if direction == SignalDirection.SHORT:
            return PositionSide.SHORT

        raise ValueError("neutral signal cannot open a position")

    @staticmethod
    def _apply_slippage(
        *,
        market_price: Decimal,
        side: PositionSide,
        opening: bool,
        slippage_rate: Decimal,
    ) -> Decimal:
        is_buy = (opening and side == PositionSide.LONG) or (
            not opening and side == PositionSide.SHORT
        )

        if is_buy:
            return market_price * (Decimal("1") + slippage_rate)

        return market_price * (Decimal("1") - slippage_rate)

    @staticmethod
    def _create_event(
        *,
        run_id: str,
        sequence_number: int,
        event_type: BacktestEventType,
        timestamp: datetime,
        pair: TradingPair,
        side: PositionSide,
        price: Decimal,
        quantity: Decimal,
        signal_id: str | None,
        exit_reason: ExitReason | None,
    ) -> BacktestEvent:
        event_id = build_backtest_event_id(
            run_id=run_id,
            sequence_number=sequence_number,
            event_type=event_type,
            timestamp=timestamp,
        )

        return BacktestEvent(
            event_id=event_id,
            sequence_number=sequence_number,
            event_type=event_type,
            timestamp=timestamp,
            pair=pair,
            side=side,
            price=price,
            quantity=quantity,
            signal_id=signal_id,
            exit_reason=exit_reason,
        )
