from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data import (
    DataIssueCode,
    MarketDataProviderAccessMode,
    MarketDataProviderResponseError,
    MarketDataQualityChecker,
    NobitexPublicMarketDataProvider,
)
from trd_bot.research import calculate_dataset_checksum

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
NOW = datetime(2026, 9, 23, 12, 30, tzinfo=UTC)
REGRESSION_START = datetime(2026, 9, 27, tzinfo=UTC)
REGRESSION_END = datetime(2026, 9, 28, tzinfo=UTC)


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


def quarter_hours(start_time: datetime, count: int) -> tuple[datetime, ...]:
    return tuple(start_time + timedelta(minutes=15 * index) for index in range(count))


def test_nobitex_provider_exposes_public_spot_capabilities() -> None:
    provider = NobitexPublicMarketDataProvider()

    assert provider.metadata.provider_id == "nobitex-public"
    assert provider.metadata.requires_credentials is False
    assert provider.metadata.supported_timeframes == tuple(Timeframe)
    assert provider.metadata.default_pair == PAIR
    assert provider.metadata.access_mode is MarketDataProviderAccessMode.DIRECT
    assert provider.metadata.max_closed_candles is None
    assert provider.metadata.normalization_version == "nobitex-utc-grid-v1"


@pytest.mark.asyncio
async def test_nobitex_provider_normalizes_closed_candles_and_paginates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_urls: list[str] = []
    delays: list[float] = []
    responses: list[object] = [
        build_payload(
            datetime(2026, 9, 23, 10, tzinfo=UTC),
            datetime(2026, 9, 23, 10, 15, tzinfo=UTC),
        ),
        build_payload(datetime(2026, 9, 23, 10, 30, tzinfo=UTC)),
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
        timeframe=Timeframe.MINUTES_15,
        start_time=datetime(2026, 9, 23, 10, tzinfo=UTC),
        end_time=datetime(2026, 9, 23, 10, 45, tzinfo=UTC),
    )

    assert [candle.open_time for candle in candles] == list(
        quarter_hours(datetime(2026, 9, 23, 10, tzinfo=UTC), 3)
    )
    assert all(candle.source == "nobitex-public" for candle in candles)
    assert candles[0].open_price == Decimal("100")
    assert candles[0].volume == Decimal("12.5")
    assert delays == [1.0]

    first_query = parse_qs(urlparse(requested_urls[0]).query)
    second_query = parse_qs(urlparse(requested_urls[1]).query)
    assert first_query == {
        "symbol": ["BTCUSDT"],
        "resolution": ["15"],
        "from": [str(int(datetime(2026, 9, 23, 10, tzinfo=UTC).timestamp()))],
        "to": [str(int(datetime(2026, 9, 23, 10, 45, tzinfo=UTC).timestamp()))],
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
            datetime(2026, 9, 23, 10, 15, tzinfo=UTC),
        ),
        build_payload(
            datetime(2026, 9, 23, 10, 15, tzinfo=UTC),
            datetime(2026, 9, 23, 10, 30, tzinfo=UTC),
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
        timeframe=Timeframe.MINUTES_15,
        start_time=datetime(2026, 9, 23, 10, tzinfo=UTC),
        end_time=datetime(2026, 9, 23, 11, tzinfo=UTC),
        limit=3,
    )

    assert [candle.open_time for candle in candles] == list(
        quarter_hours(datetime(2026, 9, 23, 10, tzinfo=UTC), 3)
    )


def test_nobitex_native_hourly_timestamp_is_preserved_as_provider_open_time() -> None:
    provider = NobitexPublicMarketDataProvider(clock=lambda: REGRESSION_END + timedelta(hours=1))

    candle = provider._parse_candle(
        (1790469000, "100", "110", "95", "105", "12.5"),
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        received_at=REGRESSION_END + timedelta(hours=1),
    )

    assert candle.open_time == datetime(2026, 9, 27, 0, 30, tzinfo=UTC)
    assert candle.close_time == datetime(2026, 9, 27, 1, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_nobitex_hourly_range_is_reaggregated_from_canonical_quarters() -> None:
    requested_urls: list[str] = []
    payload = build_payload(*quarter_hours(REGRESSION_START, 96))

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del timeout_seconds
        requested_urls.append(url)
        return payload

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: REGRESSION_END + timedelta(hours=1),
        page_delay_seconds=0,
    )

    first = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=REGRESSION_START,
        end_time=REGRESSION_END,
    )
    second = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=REGRESSION_START,
        end_time=REGRESSION_END,
    )

    assert len(first) == 24
    assert [candle.open_time for candle in first] == [
        REGRESSION_START + timedelta(hours=index) for index in range(24)
    ]
    assert len({candle.open_time for candle in first}) == 24
    assert all(candle.close_time == candle.open_time + timedelta(hours=1) for candle in first)
    assert all(candle.is_closed for candle in first)
    assert all(parse_qs(urlparse(url).query)["resolution"] == ["15"] for url in requested_urls)
    assert calculate_dataset_checksum(first) == calculate_dataset_checksum(second)

    report = MarketDataQualityChecker().check(
        first,
        requested_start_time=REGRESSION_START,
        requested_end_time=REGRESSION_END,
        requested_timeframe=Timeframe.HOUR_1,
    )
    issue_codes = {issue.code for issue in report.issues}
    assert report.issues == ()
    assert report.coverage is not None
    assert report.coverage.expected_candles == 24
    assert report.coverage.received_candles == 24
    assert report.coverage.missing_candles == 0
    assert report.coverage.coverage_percent == 100.0
    assert report.score is not None
    assert report.score.integrity_percent == 100.0
    assert report.score.score_percent == 100.0
    assert report.acceptance is not None
    assert report.acceptance.accepted is True
    assert DataIssueCode.UNALIGNED_CANDLE not in issue_codes


@pytest.mark.asyncio
async def test_nobitex_aggregation_preserves_ohlcv_interval_semantics() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return {
            "s": "ok",
            "t": [int(timestamp.timestamp()) for timestamp in quarter_hours(REGRESSION_START, 4)],
            "o": ["100", "104", "103", "108"],
            "h": ["106", "109", "107", "112"],
            "l": ["98", "101", "99", "105"],
            "c": ["104", "103", "106", "110"],
            "v": ["1.25", "2.5", "3.75", "4"],
        }

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: REGRESSION_START + timedelta(hours=2),
        page_delay_seconds=0,
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=REGRESSION_START,
        end_time=REGRESSION_START + timedelta(hours=1),
    )

    assert len(candles) == 1
    assert candles[0].open_price == Decimal("100")
    assert candles[0].high_price == Decimal("112")
    assert candles[0].low_price == Decimal("98")
    assert candles[0].close_price == Decimal("110")
    assert candles[0].volume == Decimal("11.50")


@pytest.mark.parametrize(
    ("timeframe", "source_count", "duration"),
    [
        (Timeframe.HOURS_4, 16, timedelta(hours=4)),
        (Timeframe.DAY_1, 96, timedelta(days=1)),
    ],
)
@pytest.mark.asyncio
async def test_nobitex_larger_timeframes_use_complete_utc_quarter_groups(
    timeframe: Timeframe,
    source_count: int,
    duration: timedelta,
) -> None:
    requested_urls: list[str] = []

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del timeout_seconds
        requested_urls.append(url)
        return build_payload(*quarter_hours(REGRESSION_START, source_count))

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: REGRESSION_START + duration + timedelta(hours=1),
        page_delay_seconds=0,
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=timeframe,
        start_time=REGRESSION_START,
        end_time=REGRESSION_START + duration,
    )

    assert len(candles) == 1
    assert candles[0].open_time == REGRESSION_START
    assert candles[0].close_time == REGRESSION_START + duration
    assert parse_qs(urlparse(requested_urls[0]).query)["resolution"] == ["15"]

    report = MarketDataQualityChecker().check(
        candles,
        requested_start_time=REGRESSION_START,
        requested_end_time=REGRESSION_START + duration,
        requested_timeframe=timeframe,
    )
    assert report.issues == ()
    assert report.is_valid is True


@pytest.mark.asyncio
async def test_nobitex_aggregation_does_not_emit_partially_closed_hour() -> None:
    start_time = datetime(2026, 9, 27, tzinfo=UTC)
    end_time = start_time + timedelta(hours=2)

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return build_payload(*quarter_hours(start_time, 8))

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: end_time - timedelta(minutes=15),
        page_delay_seconds=0,
    )

    candles = await provider.get_candles(
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        start_time=start_time,
        end_time=end_time,
    )

    assert [candle.open_time for candle in candles] == [start_time]


@pytest.mark.asyncio
async def test_nobitex_provider_rejects_conflicting_source_timestamp_collision() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        timestamp = int(REGRESSION_START.timestamp())
        return {
            "s": "ok",
            "t": [timestamp, timestamp],
            "o": ["100", "101"],
            "h": ["110", "110"],
            "l": ["95", "95"],
            "c": ["105", "105"],
            "v": ["12.5", "12.5"],
        }

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: REGRESSION_END,
        page_delay_seconds=0,
    )

    with pytest.raises(MarketDataProviderResponseError, match="conflicting duplicate"):
        await provider.get_candles(
            pair=PAIR,
            timeframe=Timeframe.MINUTES_15,
            start_time=REGRESSION_START,
            end_time=REGRESSION_START + timedelta(minutes=15),
        )


@pytest.mark.asyncio
async def test_nobitex_provider_rejects_unaligned_source_quarter() -> None:
    async def fetch_json(url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        return build_payload(REGRESSION_START + timedelta(minutes=1))

    provider = NobitexPublicMarketDataProvider(
        fetch_json=fetch_json,
        clock=lambda: REGRESSION_END,
        page_delay_seconds=0,
    )

    with pytest.raises(MarketDataProviderResponseError, match="not aligned"):
        await provider.get_candles(
            pair=PAIR,
            timeframe=Timeframe.MINUTES_15,
            start_time=REGRESSION_START,
            end_time=REGRESSION_START + timedelta(minutes=15),
        )


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
