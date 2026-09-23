from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast
from urllib.parse import urlencode

from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data.providers import (
    JsonFetcher,
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
_INTERVAL_MINUTES: dict[Timeframe, int] = {
    Timeframe.MINUTES_15: 15,
    Timeframe.HOUR_1: 60,
    Timeframe.HOURS_4: 240,
    Timeframe.DAY_1: 1_440,
}
_ASSET_ALIASES = {
    "BTC": "XBT",
    "DOGE": "XDG",
}


class KrakenPublicMarketDataProvider(RetryingPublicJsonMarketDataProvider):
    """Kraken recent-window OHLC adapter for public spot market data."""

    _OHLC_URL = "https://api.kraken.com/0/public/OHLC"
    _MAX_RETURNED_ENTRIES = 720
    _METADATA = MarketDataProviderMetadata(
        provider_id="kraken-public",
        display_name="Kraken Public Market Data",
        requires_credentials=False,
        supported_market_types=(MarketType.SPOT,),
        supported_timeframes=tuple(Timeframe),
    )

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        retry_policy: MarketDataRetryPolicy | None = None,
        fetch_json: JsonFetcher | None = None,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        super().__init__(
            timeout_seconds=timeout_seconds,
            retry_policy=retry_policy,
            fetch_json=fetch_json,
            sleep=sleep,
        )
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return self._METADATA

    async def test_connection(self) -> None:
        """Probe Kraken's public OHLC endpoint and validate its envelope."""

        payload = await self._request_json(
            self._build_url(
                pair=TradingPair(base_asset="BTC", quote_asset="USD"),
                timeframe=Timeframe.HOUR_1,
                start_time=None,
            )
        )
        if not self._parse_payload(payload):
            raise MarketDataProviderResponseError(
                "kraken public market-data health response contains no candles"
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
        duration = _TIMEFRAME_DURATIONS[timeframe]
        closed_entry_budget = self._MAX_RETURNED_ENTRIES - 1
        earliest_available = received_at - (duration * closed_entry_budget)
        if normalized_start < earliest_available:
            raise ValueError(
                "requested start time is outside Kraken's recent OHLC retention window"
            )

        payload = await self._request_json(
            self._build_url(
                pair=pair,
                timeframe=timeframe,
                start_time=normalized_start,
            )
        )
        rows = self._parse_payload(payload)
        candles_by_open_time: dict[datetime, OHLCVCandle] = {}

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
        if limit is not None:
            return ordered[:limit]
        return ordered

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
        start_time: datetime | None,
    ) -> str:
        base_asset = _ASSET_ALIASES.get(pair.base_asset, pair.base_asset)
        quote_asset = _ASSET_ALIASES.get(pair.quote_asset, pair.quote_asset)
        query: dict[str, str | int] = {
            "pair": f"{base_asset}{quote_asset}",
            "interval": _INTERVAL_MINUTES[timeframe],
            "assetVersion": 1,
        }
        if start_time is not None:
            query["since"] = int(start_time.timestamp())
        return f"{self._OHLC_URL}?{urlencode(query)}"

    @staticmethod
    def _parse_payload(payload: object) -> list[object]:
        if not isinstance(payload, dict):
            raise MarketDataProviderResponseError(
                "kraken public market-data response must be an object"
            )
        root = cast(dict[str, object], payload)
        errors = root.get("error")
        if not isinstance(errors, list):
            raise MarketDataProviderResponseError("kraken public market-data errors must be a list")
        if errors:
            raise MarketDataProviderResponseError(
                "kraken public market-data response contains API errors"
            )

        result_value = root.get("result")
        if not isinstance(result_value, dict):
            raise MarketDataProviderResponseError(
                "kraken public market-data result must be an object"
            )
        result = cast(dict[str, object], result_value)
        series = [value for key, value in result.items() if key != "last"]
        if len(series) != 1 or not isinstance(series[0], list):
            raise MarketDataProviderResponseError(
                "kraken public market-data result must contain one candle series"
            )
        return cast(list[object], series[0])

    def _parse_candle(
        self,
        row: object,
        *,
        pair: TradingPair,
        timeframe: Timeframe,
        received_at: datetime,
    ) -> OHLCVCandle:
        if not isinstance(row, list) or len(row) < 8:
            raise MarketDataProviderResponseError(
                "kraken public market-data candle must contain OHLCV fields"
            )

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
                volume=Decimal(str(row[6])),
                is_closed=close_time <= received_at,
            )
        except (InvalidOperation, OSError, OverflowError, TypeError, ValueError) as exc:
            raise MarketDataProviderResponseError(
                "kraken public market-data candle contains invalid values"
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
