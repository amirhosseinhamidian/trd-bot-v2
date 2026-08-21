from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import DatasetBuilder, DatasetSnapshot
from trd_bot.strategies import EMACrossoverStrategy, SignalDirection

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
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
        name="EMA crossover test dataset",
        candles=candles,
    )


def test_strategy_generates_long_signal() -> None:
    dataset = create_dataset(["5", "4", "3", "4", "6"])

    signals = EMACrossoverStrategy(
        fast_period=2,
        slow_period=3,
    ).generate(dataset)

    assert len(signals) == 1
    assert signals[0].direction == SignalDirection.LONG
    assert signals[0].score > 0


def test_strategy_generates_short_signal() -> None:
    dataset = create_dataset(["3", "4", "5", "4", "2"])

    signals = EMACrossoverStrategy(
        fast_period=2,
        slow_period=3,
    ).generate(dataset)

    assert len(signals) == 1
    assert signals[0].direction == SignalDirection.SHORT
    assert signals[0].score < 0


def test_strategy_returns_no_signal_during_warmup() -> None:
    dataset = create_dataset(["3", "4"])

    signals = EMACrossoverStrategy(
        fast_period=2,
        slow_period=3,
    ).generate(dataset)

    assert signals == ()


def test_strategy_rejects_invalid_periods() -> None:
    with pytest.raises(
        ValueError,
        match="slow EMA period must be greater",
    ):
        EMACrossoverStrategy(
            fast_period=5,
            slow_period=3,
        )
