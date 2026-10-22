from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data import (
    KrakenPublicMarketDataProvider,
    MarketDataProviderAccessMode,
    MarketDataProviderQueryError,
    MarketDataProviderResponseError,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USD")
NOW = datetime(2026, 9, 23, 13, 30, tzinfo=UTC)


def build_row(open_time: datetime) -> list[object]:
    return [
        int(open_time.timestamp()),
        "100",
        "110",
        "95",
        "105",
        "103",
        "12.5",
        10,
    ]


def build_payload(*open_times: datetime) -> dict[str, object]:
    return {
        "error": [],
        "result": {
            "BTC/USD": [build_row(value) for value in open_times],
            "last": int(NOW.timestamp()),
        },
    }


def test_kraken_provider_exposes_public_spot_capabilities() -> None:
    provider = KrakenPublicMarketDataProvider()

    assert provider.metadata.provider_id == "kraken-public"
    assert provider.metadata.requires_credentials is False
    assert provider.metadata.supported_timeframes == tuple(Timeframe)
    assert provider.metadata.default_pair == PAIR
    assert provider.metadata.access_mode is MarketDataProviderAccessMode.VPN_REQUIRED
    assert provider.metadata.max_closed_candles == 719


@pytest.mark.asyncio
async def test_kraken_provider_normalizes_recent_closed_candles() -> None:
    requested: list[tuple[str, float]] = []

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        requested.append((url, timeout_seconds))
        return build_payload(
            datetime(2026, 9, 23, 10, tzinfo=UTC),
            datetime(2026, 9, 23, 11, tzinfo=UTC),
            datetime(2026, 9, 23, 13, tzinfo=UTC),
        )

    provider = KrakenPublicMarketDataProvider(
        timeout_seconds=4.5,
        fetch_json=fetch_json,
        clock=lambda: NOW,
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=datetime(2026, 9, 23, 10, tzinfo=UTC),
        end_time=datetime(2026, 9, 23, 14, tzinfo=UTC),
    )

    assert [candle.open_time.hour for candle in candles] == [10, 11]
    assert all(candle.source == "kraken-public" for candle in candles)
    assert candles[0].open_price == Decimal("100")
    assert candles[0].volume == Decimal("12.5")

    url, timeout = requested[0]
    query = parse_qs(urlparse(url).query)
    assert timeout == 4.5
    assert query == {
        "pair": ["XBTUSD"],
        "interval": ["60"],
        "assetVersion": ["1"],
        "since": [str(int(datetime(2026, 9, 23, 10, tzinfo=UTC).timestamp()))],
    }


@pytest.mark.asyncio
async def test_kraken_provider_applies_limit_to_chronological_result() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return build_payload(
            datetime(2026, 9, 23, 10, tzinfo=UTC),
            datetime(2026, 9, 23, 11, tzinfo=UTC),
            datetime(2026, 9, 23, 12, tzinfo=UTC),
        )

    provider = KrakenPublicMarketDataProvider(fetch_json=fetch_json, clock=lambda: NOW)

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=datetime(2026, 9, 23, 10, tzinfo=UTC),
        end_time=datetime(2026, 9, 23, 13, tzinfo=UTC),
        limit=2,
    )

    assert [candle.open_time.hour for candle in candles] == [10, 11]


@pytest.mark.asyncio
async def test_kraken_provider_rejects_range_outside_recent_retention_before_request() -> None:
    attempts = 0

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        nonlocal attempts
        del url, timeout_seconds
        attempts += 1
        return build_payload()

    provider = KrakenPublicMarketDataProvider(fetch_json=fetch_json, clock=lambda: NOW)

    with pytest.raises(MarketDataProviderQueryError, match="recent OHLC retention window"):
        await provider.get_candles(
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            start_time=NOW - timedelta(days=31),
            end_time=NOW,
        )

    assert attempts == 0


@pytest.mark.asyncio
async def test_kraken_provider_rejects_api_error_envelope() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return {"error": ["EQuery:Unknown asset pair"], "result": {}}

    provider = KrakenPublicMarketDataProvider(fetch_json=fetch_json, clock=lambda: NOW)

    with pytest.raises(MarketDataProviderResponseError, match="contains API errors"):
        await provider.get_candles(
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            start_time=NOW - timedelta(hours=2),
            end_time=NOW,
        )


@pytest.mark.asyncio
async def test_kraken_provider_rejects_invalid_candle_shape() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return {
            "error": [],
            "result": {"BTC/USD": [[int((NOW - timedelta(hours=2)).timestamp())]], "last": 1},
        }

    provider = KrakenPublicMarketDataProvider(fetch_json=fetch_json, clock=lambda: NOW)

    with pytest.raises(MarketDataProviderResponseError, match="contain OHLCV fields"):
        await provider.get_candles(
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            start_time=NOW - timedelta(hours=3),
            end_time=NOW,
        )


@pytest.mark.asyncio
async def test_kraken_health_check_requires_usable_candle_payload() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return build_payload()

    provider = KrakenPublicMarketDataProvider(fetch_json=fetch_json, clock=lambda: NOW)

    with pytest.raises(MarketDataProviderResponseError, match="contains no candles"):
        await provider.test_connection()
