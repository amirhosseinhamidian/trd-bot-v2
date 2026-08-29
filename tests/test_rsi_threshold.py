from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import DatasetBuilder, DatasetSnapshot
from trd_bot.strategies import RSIThresholdStrategy, SignalDirection

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
        name="RSI threshold test dataset",
        candles=candles,
    )


def test_strategy_generates_long_signal_when_rsi_enters_oversold_region() -> None:
    dataset = create_dataset(["10", "11", "12", "6"])

    signals = RSIThresholdStrategy(
        period=2,
        oversold_threshold=Decimal("30"),
        overbought_threshold=Decimal("70"),
    ).generate(dataset)

    assert len(signals) == 1
    assert signals[0].direction is SignalDirection.LONG
    assert signals[0].score > 0
    assert signals[0].features[1].name == "rsi"
    assert signals[0].features[1].value <= Decimal("30")


def test_strategy_generates_short_signal_when_rsi_enters_overbought_region() -> None:
    dataset = create_dataset(["10", "9", "8", "14"])

    signals = RSIThresholdStrategy(
        period=2,
        oversold_threshold=Decimal("30"),
        overbought_threshold=Decimal("70"),
    ).generate(dataset)

    assert len(signals) == 1
    assert signals[0].direction is SignalDirection.SHORT
    assert signals[0].score < 0
    assert signals[0].features[1].value >= Decimal("70")


def test_strategy_does_not_repeat_signal_while_rsi_stays_extreme() -> None:
    dataset = create_dataset(["10", "11", "12", "6", "5"])

    signals = RSIThresholdStrategy(
        period=2,
        oversold_threshold=Decimal("30"),
        overbought_threshold=Decimal("70"),
    ).generate(dataset)

    assert len(signals) == 1
    assert signals[0].direction is SignalDirection.LONG


def test_strategy_returns_no_signal_during_warmup() -> None:
    dataset = create_dataset(["10", "11"])

    signals = RSIThresholdStrategy(
        period=2,
    ).generate(dataset)

    assert signals == ()


def test_strategy_rejects_invalid_period() -> None:
    with pytest.raises(
        ValueError,
        match="RSI period must be at least 2",
    ):
        RSIThresholdStrategy(period=1)


def test_strategy_rejects_invalid_oversold_threshold() -> None:
    with pytest.raises(
        ValueError,
        match="oversold RSI threshold",
    ):
        RSIThresholdStrategy(oversold_threshold=Decimal("50"))


def test_strategy_rejects_invalid_overbought_threshold() -> None:
    with pytest.raises(
        ValueError,
        match="overbought RSI threshold",
    ):
        RSIThresholdStrategy(overbought_threshold=Decimal("50"))
