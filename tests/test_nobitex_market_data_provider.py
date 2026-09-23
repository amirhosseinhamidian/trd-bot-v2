from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data import (
    MarketDataProviderResponseError,
    NobitexPublicMarketDataProvider,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
NOW = datetime(2026, 9, 23, 12, 30, tzinfo=UTC)


def build_payload(*open_times: datetime) -> dict[str, object]:
    return {
        "s": "ok",
        "t": [int(value.timestamp()) for value in open_times],
        "o": ["100" for _ in open_times],
        "h": ["110" for _ in open_times],
        "l": ["95" for _ in open_times],
        "c": ["105" for _ in open_times],
        "v": ["12.5" for _ in open_times],
    }


def test_nobitex_provider_exposes_public_spot_capabilities() -> None:
    provider = NobitexPublicMarketDataProvider()

    assert provider.metadata.provider_id == "nobitex-public"
    assert provider.metadata.requires_credentials is False
    assert provider.metadata.supported_timeframes == tuple(Timeframe)


@pytest.mark.asyncio
async def test_nobitex_provider_normalizes_closed_candles_and_paginates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_urls: list[str] = []
    delays: list[float] = []
    responses: list[object] = [
        build_payload(
            datetime(2026, 9, 23, 10, tzinfo=UTC),
            datetime(2026, 9, 23, 11, tzinfo=UTC),
        ),
        build_payload(datetime(2026, 9, 23, 12, tzinfo=UTC)),
    ]

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        requested_urls.append(url)
        assert timeout_seconds == 4.0
        return responses.pop(0)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(NobitexPublicMarketDataProvider, "_MAX_PAGE_SIZE", 2)
    provider = NobitexPublicMarketDataProvider(
        timeout_seconds=4.0,
        fetch_json=fetch_json,
        sleep=sleep,
        clock=lambda: NOW,
        page_delay_seconds=1.0,
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=datetime(2026, 9, 23, 10, tzinfo=UTC),
        end_time=datetime(2026, 9, 23, 13, tzinfo=UTC),
    )

    assert [candle.open_time.hour for candle in candles] == [10, 11]
    assert all(candle.source == "nobitex-public" for candle in candles)
    assert candles[0].open_price == Decimal("100")
    assert candles[0].volume == Decimal("12.5")
    assert delays == [1.0]

    first_query = parse_qs(urlparse(requested_urls[0]).query)
    second_query = parse_qs(urlparse(requested_urls[1]).query)
    assert first_query == {
        "symbol": ["BTCUSDT"],
        "resolution": ["60"],
        "from": [str(int(datetime(2026, 9, 23, 10, tzinfo=UTC).timestamp()))],
        "to": [str(int(datetime(2026, 9, 23, 13, tzinfo=UTC).timestamp()))],
        "page": ["1"],
    }
    assert second_query["page"] == ["2"]


@pytest.mark.asyncio
async def test_nobitex_provider_applies_limit_after_deduplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[object] = [
        build_payload(
            datetime(2026, 9, 23, 10, tzinfo=UTC),
            datetime(2026, 9, 23, 11, tzinfo=UTC),
        ),
        build_payload(
            datetime(2026, 9, 23, 11, tzinfo=UTC),
            datetime(2026, 9, 23, 12, tzinfo=UTC),
        ),
    ]

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return responses.pop(0)

    async def sleep(delay: float) -> None:
        del delay

    monkeypatch.setattr(NobitexPublicMarketDataProvider, "_MAX_PAGE_SIZE", 2)
    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        sleep=sleep,
        clock=lambda: NOW + timedelta(hours=1),
        page_delay_seconds=1.0,
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=datetime(2026, 9, 23, 10, tzinfo=UTC),
        end_time=datetime(2026, 9, 23, 14, tzinfo=UTC),
        limit=3,
    )

    assert [candle.open_time.hour for candle in candles] == [10, 11, 12]


@pytest.mark.asyncio
async def test_nobitex_provider_returns_empty_for_documented_no_data_response() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return {"s": "no_data"}

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: NOW,
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=NOW - timedelta(days=2),
        end_time=NOW - timedelta(days=1),
    )

    assert candles == []


@pytest.mark.asyncio
async def test_nobitex_provider_rejects_misaligned_udf_columns() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        payload = build_payload(datetime(2026, 9, 23, 10, tzinfo=UTC))
        payload["v"] = []
        return payload

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: NOW,
    )

    with pytest.raises(MarketDataProviderResponseError, match="equal lengths"):
        await provider.get_candles(
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            start_time=NOW - timedelta(hours=3),
            end_time=NOW,
        )


@pytest.mark.asyncio
async def test_nobitex_health_check_requires_usable_candle_payload() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return {"s": "no_data"}

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: NOW,
    )

    with pytest.raises(MarketDataProviderResponseError, match="contains no candles"):
        await provider.test_connection()


def test_nobitex_provider_rejects_unbounded_pagination_configuration() -> None:
    with pytest.raises(ValueError, match="maximum pages"):
        NobitexPublicMarketDataProvider(max_pages=0)
