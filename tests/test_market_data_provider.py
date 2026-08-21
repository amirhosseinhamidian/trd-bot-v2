from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import InMemoryMarketDataProvider

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)


def create_candle(
    hour: int,
    *,
    is_closed: bool = True,
) -> OHLCVCandle:
    return OHLCVCandle(
        source="test-exchange",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 8, 21, hour, tzinfo=UTC),
        close_time=datetime(2026, 8, 21, hour + 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1000"),
        is_closed=is_closed,
    )


@pytest.mark.asyncio
async def test_provider_returns_closed_candles_in_order() -> None:
    provider = InMemoryMarketDataProvider(
        candles=[
            create_candle(12, is_closed=False),
            create_candle(11),
            create_candle(10),
        ]
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=datetime(2026, 8, 21, 9, tzinfo=UTC),
        end_time=datetime(2026, 8, 21, 13, tzinfo=UTC),
    )

    assert len(candles) == 2
    assert candles[0].open_time.hour == 10
    assert candles[1].open_time.hour == 11


@pytest.mark.asyncio
async def test_provider_applies_limit() -> None:
    provider = InMemoryMarketDataProvider(
        candles=[
            create_candle(10),
            create_candle(11),
        ]
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=datetime(2026, 8, 21, 9, tzinfo=UTC),
        end_time=datetime(2026, 8, 21, 13, tzinfo=UTC),
        limit=1,
    )

    assert len(candles) == 1
    assert candles[0].open_time.hour == 10


@pytest.mark.asyncio
async def test_provider_rejects_invalid_time_range() -> None:
    provider = InMemoryMarketDataProvider(candles=[])

    with pytest.raises(
        ValueError,
        match="end time must be after start time",
    ):
        await provider.get_candles(
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            start_time=datetime(2026, 8, 21, 13, tzinfo=UTC),
            end_time=datetime(2026, 8, 21, 12, tzinfo=UTC),
        )
