from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.backtesting import (
    BacktestConfig,
    BacktestEngine,
    BacktestEventType,
    ExitReason,
    PositionSide,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import DatasetBuilder, DatasetSnapshot
from trd_bot.strategies import (
    SignalDirection,
    StrategySignal,
    build_signal_id,
)

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)

DEFAULT_CONFIG = BacktestConfig(
    starting_balance=Decimal("10000"),
    allocation_fraction=Decimal("0.10"),
    fee_rate=Decimal("0"),
    slippage_rate=Decimal("0"),
)


def create_dataset(
    prices: list[str],
) -> DatasetSnapshot:
    candles = []

    for index, price_text in enumerate(prices):
        price = Decimal(price_text)
        hour = 10 + index

        candles.append(
            OHLCVCandle(
                source="test-exchange",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=datetime(
                    2026,
                    8,
                    21,
                    hour,
                    tzinfo=UTC,
                ),
                close_time=datetime(
                    2026,
                    8,
                    21,
                    hour + 1,
                    tzinfo=UTC,
                ),
                received_at=datetime(
                    2026,
                    8,
                    21,
                    20,
                    tzinfo=UTC,
                ),
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(
        name="Backtest engine dataset",
        candles=candles,
    )


def create_signal(
    *,
    dataset: DatasetSnapshot,
    candle_index: int,
    direction: SignalDirection,
) -> StrategySignal:
    candle = dataset.candles[candle_index]

    signal_id = build_signal_id(
        strategy_name="test-strategy",
        strategy_version="1.0.0",
        dataset_id=dataset.dataset_id,
        candle_close_time=candle.close_time,
        direction=direction,
    )

    score = Decimal("0.5") if direction == SignalDirection.LONG else Decimal("-0.5")

    return StrategySignal(
        signal_id=signal_id,
        strategy_name="test-strategy",
        strategy_version="1.0.0",
        dataset_id=dataset.dataset_id,
        pair=dataset.pair,
        timeframe=dataset.timeframe,
        candle_open_time=candle.open_time,
        candle_close_time=candle.close_time,
        generated_at=candle.close_time,
        direction=direction,
        score=score,
        reason="Backtest engine test signal.",
    )


def test_signal_executes_on_next_candle_open() -> None:
    dataset = create_dataset(["100", "110", "90", "95"])

    signal = create_signal(
        dataset=dataset,
        candle_index=0,
        direction=SignalDirection.LONG,
    )

    events = BacktestEngine().run(
        run_id="backtest-next-candle",
        dataset=dataset,
        signals=[signal],
        config=DEFAULT_CONFIG,
    )

    assert len(events) == 2

    opened_event = events[0]

    assert opened_event.event_type == BacktestEventType.POSITION_OPENED
    assert opened_event.timestamp == dataset.candles[1].open_time
    assert opened_event.price == Decimal("110")
    assert opened_event.side == PositionSide.LONG

    assert events[1].exit_reason == ExitReason.END_OF_DATA


def test_opposite_signal_reverses_position() -> None:
    dataset = create_dataset(["100", "110", "90", "95"])

    long_signal = create_signal(
        dataset=dataset,
        candle_index=0,
        direction=SignalDirection.LONG,
    )

    short_signal = create_signal(
        dataset=dataset,
        candle_index=1,
        direction=SignalDirection.SHORT,
    )

    events = BacktestEngine().run(
        run_id="backtest-reversal",
        dataset=dataset,
        signals=[
            long_signal,
            short_signal,
        ],
        config=DEFAULT_CONFIG,
    )

    assert len(events) == 4

    assert events[0].event_type == BacktestEventType.POSITION_OPENED
    assert events[0].side == PositionSide.LONG

    assert events[1].event_type == BacktestEventType.POSITION_CLOSED
    assert events[1].side == PositionSide.LONG
    assert events[1].exit_reason == ExitReason.OPPOSITE_SIGNAL

    assert events[2].event_type == BacktestEventType.POSITION_OPENED
    assert events[2].side == PositionSide.SHORT

    assert events[3].event_type == BacktestEventType.POSITION_CLOSED
    assert events[3].exit_reason == ExitReason.END_OF_DATA


def test_signal_on_final_candle_is_not_executed() -> None:
    dataset = create_dataset(["100", "110", "90", "95"])

    final_signal = create_signal(
        dataset=dataset,
        candle_index=3,
        direction=SignalDirection.LONG,
    )

    events = BacktestEngine().run(
        run_id="backtest-final-signal",
        dataset=dataset,
        signals=[final_signal],
        config=DEFAULT_CONFIG,
    )

    assert events == ()


def test_unfavorable_slippage_is_applied() -> None:
    dataset = create_dataset(["100", "110", "90", "95"])

    signal = create_signal(
        dataset=dataset,
        candle_index=0,
        direction=SignalDirection.LONG,
    )

    config = BacktestConfig(
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0.01"),
    )

    events = BacktestEngine().run(
        run_id="backtest-slippage",
        dataset=dataset,
        signals=[signal],
        config=config,
    )

    assert events[0].price == Decimal("111.10")
    assert events[1].price == Decimal("94.05")


def test_signal_from_another_dataset_is_rejected() -> None:
    dataset = create_dataset(["100", "110", "90", "95"])

    signal = create_signal(
        dataset=dataset,
        candle_index=0,
        direction=SignalDirection.LONG,
    )

    invalid_signal = signal.model_copy(
        update={"dataset_id": "dataset-other"},
    )

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        BacktestEngine().run(
            run_id="backtest-invalid-signal",
            dataset=dataset,
            signals=[invalid_signal],
            config=DEFAULT_CONFIG,
        )
