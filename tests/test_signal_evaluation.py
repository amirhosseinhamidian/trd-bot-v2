from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import (
    OHLCVCandle,
    Timeframe,
    TradingPair,
)
from trd_bot.research import (
    DatasetBuilder,
    DatasetSnapshot,
    SignalEvaluator,
    SignalOutcome,
)
from trd_bot.strategies import (
    SignalDirection,
    StrategySignal,
    build_signal_id,
)

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)


def create_dataset(
    prices: list[tuple[str, str]],
) -> DatasetSnapshot:
    candles = []

    for index, (open_text, close_text) in enumerate(prices):
        open_price = Decimal(open_text)
        close_price = Decimal(close_text)
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
                open_price=open_price,
                high_price=(max(open_price, close_price) + Decimal("1")),
                low_price=(min(open_price, close_price) - Decimal("1")),
                close_price=close_price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(
        name="Signal evaluation dataset",
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
        reason="Signal evaluation test.",
    )


def test_long_signal_is_evaluated_as_correct() -> None:
    dataset = create_dataset(
        [
            ("100", "100"),
            ("100", "110"),
            ("110", "112"),
        ]
    )

    signal = create_signal(
        dataset=dataset,
        candle_index=0,
        direction=SignalDirection.LONG,
    )

    report = SignalEvaluator().evaluate(
        dataset=dataset,
        signals=[signal],
        horizon_candles=1,
    )

    assert report.correct_signals == 1
    assert report.hit_rate == Decimal("1")
    assert report.evaluations[0].directional_return == Decimal("0.1")
    assert report.evaluations[0].outcome == SignalOutcome.CORRECT


def test_short_signal_is_evaluated_as_correct() -> None:
    dataset = create_dataset(
        [
            ("100", "100"),
            ("100", "90"),
            ("90", "88"),
        ]
    )

    signal = create_signal(
        dataset=dataset,
        candle_index=0,
        direction=SignalDirection.SHORT,
    )

    report = SignalEvaluator().evaluate(
        dataset=dataset,
        signals=[signal],
    )

    assert report.correct_signals == 1
    assert report.evaluations[0].directional_return == Decimal("0.1")


def test_incorrect_signal_is_detected() -> None:
    dataset = create_dataset(
        [
            ("100", "100"),
            ("100", "90"),
            ("90", "88"),
        ]
    )

    signal = create_signal(
        dataset=dataset,
        candle_index=0,
        direction=SignalDirection.LONG,
    )

    report = SignalEvaluator().evaluate(
        dataset=dataset,
        signals=[signal],
    )

    assert report.incorrect_signals == 1
    assert report.hit_rate == Decimal("0")


def test_final_signal_is_unresolved() -> None:
    dataset = create_dataset(
        [
            ("100", "100"),
            ("100", "110"),
        ]
    )

    signal = create_signal(
        dataset=dataset,
        candle_index=1,
        direction=SignalDirection.LONG,
    )

    report = SignalEvaluator().evaluate(
        dataset=dataset,
        signals=[signal],
    )

    assert report.resolved_signals == 0
    assert report.unresolved_signals == 1
    assert report.hit_rate is None


def test_invalid_horizon_is_rejected() -> None:
    dataset = create_dataset(
        [
            ("100", "100"),
            ("100", "110"),
        ]
    )

    with pytest.raises(
        ValueError,
        match="horizon must be at least 1",
    ):
        SignalEvaluator().evaluate(
            dataset=dataset,
            signals=[],
            horizon_candles=0,
        )
