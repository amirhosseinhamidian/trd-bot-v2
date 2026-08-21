from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair


def create_valid_candle(**overrides: object) -> OHLCVCandle:
    data: dict[str, object] = {
        "source": "test-exchange",
        "pair": TradingPair(
            base_asset="BTC",
            quote_asset="USDT",
        ),
        "timeframe": Timeframe.HOUR_1,
        "open_time": datetime(2026, 8, 21, 12, tzinfo=UTC),
        "close_time": datetime(2026, 8, 21, 13, tzinfo=UTC),
        "open_price": Decimal("100"),
        "high_price": Decimal("110"),
        "low_price": Decimal("95"),
        "close_price": Decimal("105"),
        "volume": Decimal("1250.50"),
        "is_closed": True,
    }

    data.update(overrides)

    return OHLCVCandle.model_validate(data)


def test_trading_pair_is_normalized() -> None:
    pair = TradingPair(
        base_asset=" btc ",
        quote_asset="usdt",
    )

    assert pair.base_asset == "BTC"
    assert pair.quote_asset == "USDT"
    assert pair.symbol == "BTC/USDT"


def test_trading_pair_rejects_identical_assets() -> None:
    with pytest.raises(ValidationError):
        TradingPair(
            base_asset="BTC",
            quote_asset="BTC",
        )


def test_valid_candle_is_created() -> None:
    candle = create_valid_candle()

    assert candle.pair.symbol == "BTC/USDT"
    assert candle.timeframe == Timeframe.HOUR_1
    assert candle.is_closed is True
    assert candle.open_time.tzinfo is UTC


def test_candle_rejects_invalid_high_price() -> None:
    with pytest.raises(ValidationError):
        create_valid_candle(
            high_price=Decimal("99"),
        )


def test_candle_rejects_invalid_low_price() -> None:
    with pytest.raises(ValidationError):
        create_valid_candle(
            low_price=Decimal("101"),
        )


def test_candle_rejects_negative_volume() -> None:
    with pytest.raises(ValidationError):
        create_valid_candle(
            volume=Decimal("-1"),
        )


def test_candle_rejects_timestamp_without_timezone() -> None:
    with pytest.raises(ValidationError):
        create_valid_candle(
            open_time=datetime(2026, 8, 21, 12),
        )
