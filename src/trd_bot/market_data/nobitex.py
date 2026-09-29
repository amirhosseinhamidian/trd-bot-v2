from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast
from urllib.parse import urlencode

from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data.providers import (
    JsonFetcher,
    MarketDataProviderAccessMode,
    MarketDataProviderMetadata,
    MarketDataProviderResponseError,
    MarketDataRetryPolicy,
    RetryingPublicJsonMarketDataProvider,
    Sleep,
)

Clock = Callable[[], datetime]

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_SOURCE_TIMEFRAME = Timeframe.MINUTES_15
_NORMALIZATION_VERSION = "nobitex-utc-grid-v1"
_TIMEFRAME_DURATIONS: dict[Timeframe, timedelta] = {
    Timeframe.MINUTES_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.HOURS_4: timedelta(hours=4),
    Timeframe.DAY_1: timedelta(days=1),
}


class NobitexPublicMarketDataProvider(RetryingPublicJsonMarketDataProvider):
    """Nobitex public TradingView-UDF OHLC adapter with bounded pagination."""

    _HISTORY_URL = "https://apiv2.nobitex.ir/market/udf/history"
    _MAX_PAGE_SIZE = 500
    _DEFAULT_MAX_PAGES = 100
    _METADATA = MarketDataProviderMetadata(
        provider_id="nobitex-public",
        display_name="Nobitex Public Market Data",
        requires_credentials=False,
        supported_market_types=(MarketType.SPOT,),
        supported_timeframes=tuple(Timeframe),
        default_pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
        access_mode=MarketDataProviderAccessMode.DIRECT,
        max_closed_candles=None,
        normalization_version=_NORMALIZATION_VERSION,
    )

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        retry_policy: MarketDataRetryPolicy | None = None,
        fetch_json: JsonFetcher | None = None,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
        page_delay_seconds: float = 1.0,
        max_pages: int = _DEFAULT_MAX_PAGES,
    ) -> None:
        super().__init__(
            timeout_seconds=timeout_seconds,
            retry_policy=retry_policy,
            fetch_json=fetch_json,
            sleep=sleep,
        )
        if page_delay_seconds < 0:
            raise ValueError("page delay cannot be negative")
        if max_pages <= 0:
            raise ValueError("maximum pages must be greater than zero")

        self._clock = clock or (lambda: datetime.now(UTC))
        self._page_delay_seconds = page_delay_seconds
        self._max_pages = max_pages

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return self._METADATA

    async def test_connection(self) -> None:
        """Probe a public BTC/USDT window and validate the UDF response contract."""

        observed_at = self._now()
        payload = await self._request_json(
            self._build_url(
                pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
                start_time=observed_at - timedelta(hours=3),
                end_time=observed_at,
                page=1,
            )
        )
        if not self._parse_payload(payload):
            raise MarketDataProviderResponseError(
                "nobitex public market-data health response contains no candles"
            )

    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        self._validate_query(start_time=start_time, end_time=end_time, limit=limit)
        self._validate_capabilities(pair=pair, timeframe=timeframe)

        normalized_start = start_time.astimezone(UTC)
        normalized_end = end_time.astimezone(UTC)
        source_start = self._ceil_to_boundary(normalized_start, timeframe)
        source_end = self._ceil_to_boundary(normalized_end, timeframe)
        if source_end <= source_start:
            return []

        received_at = self._now()
        source_candles_by_open_time: dict[datetime, OHLCVCandle] = {}

        for page in range(1, self._max_pages + 1):
            payload = await self._request_json(
                self._build_url(
                    pair=pair,
                    start_time=source_start,
                    end_time=source_end,
                    page=page,
                )
            )
            rows = self._parse_payload(payload)

            for row in rows:
                candle = self._parse_candle(
                    row,
                    pair=pair,
                    timeframe=_SOURCE_TIMEFRAME,
                    received_at=received_at,
                )
                self._validate_source_alignment(candle)
                if candle.is_closed and source_start <= candle.open_time < source_end:
                    existing = source_candles_by_open_time.get(candle.open_time)
                    if existing is not None and existing != candle:
                        raise MarketDataProviderResponseError(
                            "nobitex public market-data response contains conflicting "
                            "duplicate timestamps"
                        )
                    source_candles_by_open_time[candle.open_time] = candle

            ordered = self._normalize_to_utc_grid(
                tuple(source_candles_by_open_time.values()),
                pair=pair,
                timeframe=timeframe,
                start_time=normalized_start,
                end_time=normalized_end,
                received_at=received_at,
            )
            if limit is not None and len(ordered) >= limit:
                return ordered[:limit]

            if len(rows) < self._MAX_PAGE_SIZE:
                return ordered

            if page == self._max_pages:
                raise MarketDataProviderResponseError(
                    "nobitex public market-data pagination exceeded the configured page budget"
                )

            if self._page_delay_seconds:
                await self._sleep(self._page_delay_seconds)

        raise RuntimeError("nobitex pagination ended without a result")

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider clock must include timezone information")
        return value.astimezone(UTC)

    def _build_url(
        self,
        *,
        pair: TradingPair,
        start_time: datetime,
        end_time: datetime,
        page: int,
    ) -> str:
        query = urlencode(
            {
                "symbol": f"{pair.base_asset}{pair.quote_asset}",
                "resolution": "15",
                "from": int(start_time.timestamp()),
                "to": int(end_time.timestamp()),
                "page": page,
            }
        )
        return f"{self._HISTORY_URL}?{query}"

    @staticmethod
    def _epoch_microseconds(value: datetime) -> int:
        delta = value.astimezone(UTC) - _EPOCH
        return ((delta.days * 86_400) + delta.seconds) * 1_000_000 + delta.microseconds

    @classmethod
    def _ceil_to_boundary(cls, value: datetime, timeframe: Timeframe) -> datetime:
        interval_microseconds = int(_TIMEFRAME_DURATIONS[timeframe].total_seconds() * 1_000_000)
        value_microseconds = cls._epoch_microseconds(value)
        boundary_index = -(-value_microseconds // interval_microseconds)
        return _EPOCH + timedelta(microseconds=boundary_index * interval_microseconds)

    @classmethod
    def _floor_to_boundary(cls, value: datetime, timeframe: Timeframe) -> datetime:
        interval_microseconds = int(_TIMEFRAME_DURATIONS[timeframe].total_seconds() * 1_000_000)
        value_microseconds = cls._epoch_microseconds(value)
        boundary_index = value_microseconds // interval_microseconds
        return _EPOCH + timedelta(microseconds=boundary_index * interval_microseconds)

    @classmethod
    def _validate_source_alignment(cls, candle: OHLCVCandle) -> None:
        interval_microseconds = int(
            _TIMEFRAME_DURATIONS[_SOURCE_TIMEFRAME].total_seconds() * 1_000_000
        )
        if cls._epoch_microseconds(candle.open_time) % interval_microseconds != 0:
            raise MarketDataProviderResponseError(
                "nobitex 15-minute source candle is not aligned to the UTC grid"
            )

    def _normalize_to_utc_grid(
        self,
        source_candles: Sequence[OHLCVCandle],
        *,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        received_at: datetime,
    ) -> list[OHLCVCandle]:
        ordered_source = sorted(source_candles, key=lambda candle: candle.open_time)
        if timeframe is _SOURCE_TIMEFRAME:
            return [
                candle for candle in ordered_source if start_time <= candle.open_time < end_time
            ]

        target_duration = _TIMEFRAME_DURATIONS[timeframe]
        source_duration = _TIMEFRAME_DURATIONS[_SOURCE_TIMEFRAME]
        expected_source_count = int(target_duration / source_duration)
        grouped: dict[datetime, list[OHLCVCandle]] = defaultdict(list)

        for candle in ordered_source:
            grouped[self._floor_to_boundary(candle.open_time, timeframe)].append(candle)

        normalized: list[OHLCVCandle] = []
        for open_time, group in sorted(grouped.items()):
            if not start_time <= open_time < end_time:
                continue

            ordered_group = sorted(group, key=lambda candle: candle.open_time)
            expected_open_times = tuple(
                open_time + (source_duration * index) for index in range(expected_source_count)
            )
            actual_open_times = tuple(candle.open_time for candle in ordered_group)
            if actual_open_times != expected_open_times:
                continue

            close_time = open_time + target_duration
            if close_time > received_at or not all(candle.is_closed for candle in ordered_group):
                continue

            normalized.append(
                OHLCVCandle(
                    source=self.metadata.provider_id,
                    pair=pair,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=close_time,
                    received_at=received_at,
                    open_price=ordered_group[0].open_price,
                    high_price=max(candle.high_price for candle in ordered_group),
                    low_price=min(candle.low_price for candle in ordered_group),
                    close_price=ordered_group[-1].close_price,
                    volume=sum(
                        (candle.volume for candle in ordered_group),
                        start=Decimal("0"),
                    ),
                    is_closed=True,
                )
            )

        return normalized

    @staticmethod
    def _parse_payload(payload: object) -> list[tuple[object, ...]]:
        if not isinstance(payload, dict):
            raise MarketDataProviderResponseError(
                "nobitex public market-data response must be an object"
            )
        root = cast(dict[str, object], payload)
        status = root.get("s")
        if status == "no_data":
            return []
        if status != "ok":
            raise MarketDataProviderResponseError(
                "nobitex public market-data response status is not ok"
            )

        columns: list[list[object]] = []
        for name in ("t", "o", "h", "l", "c", "v"):
            value = root.get(name)
            if not isinstance(value, list):
                raise MarketDataProviderResponseError(
                    f"nobitex public market-data column {name} must be a list"
                )
            columns.append(cast(list[object], value))

        lengths = {len(column) for column in columns}
        if len(lengths) != 1:
            raise MarketDataProviderResponseError(
                "nobitex public market-data columns must have equal lengths"
            )

        return list(zip(*columns, strict=True))

    def _parse_candle(
        self,
        row: tuple[object, ...],
        *,
        pair: TradingPair,
        timeframe: Timeframe,
        received_at: datetime,
    ) -> OHLCVCandle:
        try:
            open_time = datetime.fromtimestamp(self._parse_integer(row[0]), tz=UTC)
            close_time = open_time + _TIMEFRAME_DURATIONS[timeframe]
            return OHLCVCandle(
                source=self.metadata.provider_id,
                pair=pair,
                timeframe=timeframe,
                open_time=open_time,
                close_time=close_time,
                received_at=received_at,
                open_price=Decimal(str(row[1])),
                high_price=Decimal(str(row[2])),
                low_price=Decimal(str(row[3])),
                close_price=Decimal(str(row[4])),
                volume=Decimal(str(row[5])),
                is_closed=close_time <= received_at,
            )
        except (
            InvalidOperation,
            IndexError,
            OSError,
            OverflowError,
            TypeError,
            ValueError,
        ) as exc:
            raise MarketDataProviderResponseError(
                "nobitex public market-data candle contains invalid values"
            ) from exc

    @staticmethod
    def _parse_integer(value: object) -> int:
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid integer")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            return int(value)
        raise TypeError("value must be an integer")
