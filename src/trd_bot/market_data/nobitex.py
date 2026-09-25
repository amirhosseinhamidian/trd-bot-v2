from collections.abc import Callable
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

_TIMEFRAME_DURATIONS: dict[Timeframe, timedelta] = {
    Timeframe.MINUTES_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.HOURS_4: timedelta(hours=4),
    Timeframe.DAY_1: timedelta(days=1),
}
_RESOLUTIONS: dict[Timeframe, str] = {
    Timeframe.MINUTES_15: "15",
    Timeframe.HOUR_1: "60",
    Timeframe.HOURS_4: "240",
    Timeframe.DAY_1: "D",
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
                timeframe=Timeframe.HOUR_1,
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
        received_at = self._now()
        candles_by_open_time: dict[datetime, OHLCVCandle] = {}

        for page in range(1, self._max_pages + 1):
            payload = await self._request_json(
                self._build_url(
                    pair=pair,
                    timeframe=timeframe,
                    start_time=normalized_start,
                    end_time=normalized_end,
                    page=page,
                )
            )
            rows = self._parse_payload(payload)

            for row in rows:
                candle = self._parse_candle(
                    row,
                    pair=pair,
                    timeframe=timeframe,
                    received_at=received_at,
                )
                if candle.is_closed and normalized_start <= candle.open_time < normalized_end:
                    candles_by_open_time[candle.open_time] = candle

            ordered = sorted(candles_by_open_time.values(), key=lambda candle: candle.open_time)
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
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        page: int,
    ) -> str:
        query = urlencode(
            {
                "symbol": f"{pair.base_asset}{pair.quote_asset}",
                "resolution": _RESOLUTIONS[timeframe],
                "from": int(start_time.timestamp()),
                "to": int(end_time.timestamp()),
                "page": page,
            }
        )
        return f"{self._HISTORY_URL}?{query}"

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
