from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    BinancePublicMarketDataProvider,
    InMemoryMarketDataProvider,
    MarketDataProviderResponseError,
)

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


def create_binance_row(open_time: datetime) -> list[object]:
    open_milliseconds = int(open_time.timestamp() * 1_000)
    close_time = open_time + timedelta(hours=1) - timedelta(milliseconds=1)
    close_milliseconds = int(close_time.timestamp() * 1_000)

    return [
        open_milliseconds,
        "100",
        "110",
        "95",
        "105",
        "1000",
        close_milliseconds,
    ]


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


def test_public_provider_exposes_historical_capabilities_without_credentials() -> None:
    provider = BinancePublicMarketDataProvider()

    assert provider.metadata.provider_id == "binance-public"
    assert provider.metadata.requires_credentials is False
    assert provider.metadata.supported_timeframes == tuple(Timeframe)


@pytest.mark.asyncio
async def test_public_provider_normalizes_and_paginates_binance_klines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_urls: list[str] = []
    responses: list[object] = [
        [
            create_binance_row(datetime(2026, 8, 21, 10, tzinfo=UTC)),
            create_binance_row(datetime(2026, 8, 21, 11, tzinfo=UTC)),
        ],
        [
            create_binance_row(datetime(2026, 8, 21, 12, tzinfo=UTC)),
        ],
    ]

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        requested_urls.append(url)
        assert timeout_seconds == 5.0
        return responses.pop(0)

    monkeypatch.setattr(
        BinancePublicMarketDataProvider,
        "_MAX_PAGE_SIZE",
        2,
    )
    provider = BinancePublicMarketDataProvider(
        timeout_seconds=5.0,
        fetch_json=fetch_json,
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=datetime(2026, 8, 21, 10, tzinfo=UTC),
        end_time=datetime(2026, 8, 21, 14, tzinfo=UTC),
    )

    assert [candle.open_time.hour for candle in candles] == [10, 11, 12]
    assert all(candle.source == "binance-public" for candle in candles)
    assert all(candle.pair == PAIR for candle in candles)
    assert candles[0].open_price == Decimal("100")
    assert candles[0].volume == Decimal("1000")
    assert len(requested_urls) == 2

    first_query = parse_qs(urlparse(requested_urls[0]).query)
    second_query = parse_qs(urlparse(requested_urls[1]).query)

    assert first_query["symbol"] == ["BTCUSDT"]
    assert first_query["interval"] == ["1h"]
    assert first_query["limit"] == ["2"]
    assert second_query["startTime"] == [
        str(int(datetime(2026, 8, 21, 12, tzinfo=UTC).timestamp() * 1_000))
    ]


@pytest.mark.asyncio
async def test_public_provider_rejects_unexpected_payload_shape() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url
        del timeout_seconds
        return {"code": -1, "message": "unexpected"}

    provider = BinancePublicMarketDataProvider(fetch_json=fetch_json)

    with pytest.raises(
        MarketDataProviderResponseError,
        match="response must be a list",
    ):
        await provider.get_candles(
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            start_time=datetime(2026, 8, 21, 10, tzinfo=UTC),
            end_time=datetime(2026, 8, 21, 11, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_public_provider_health_check_uses_public_ping_endpoint() -> None:
    requested: list[tuple[str, float]] = []

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        requested.append((url, timeout_seconds))
        return {}

    provider = BinancePublicMarketDataProvider(
        timeout_seconds=3.0,
        fetch_json=fetch_json,
    )

    await provider.test_connection()

    assert requested == [
        ("https://data-api.binance.vision/api/v3/ping", 3.0),
    ]


@pytest.mark.asyncio
async def test_public_provider_health_check_rejects_invalid_ping_payload() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url
        del timeout_seconds
        return []

    provider = BinancePublicMarketDataProvider(fetch_json=fetch_json)

    with pytest.raises(
        MarketDataProviderResponseError,
        match="health response must be an object",
    ):
        await provider.test_connection()
