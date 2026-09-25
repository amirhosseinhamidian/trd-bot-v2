import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from trd_bot.domain.market_data import (
    MarketType,
    OHLCVCandle,
    Timeframe,
    TradingPair,
)


class MarketDataProviderErrorCode(StrEnum):
    """Stable public categories for external provider failures."""

    REQUEST_FAILED = "provider_request_failed"
    TIMEOUT = "provider_timeout"
    RATE_LIMITED = "provider_rate_limited"
    HTTP_ERROR = "provider_http_error"
    RESPONSE_INVALID = "provider_response_invalid"
    UNAVAILABLE = "provider_unavailable"


class MarketDataProviderAccessMode(StrEnum):
    """Operational network route selected for this research deployment."""

    DIRECT = "direct"
    VPN_REQUIRED = "vpn_required"


@dataclass(frozen=True, slots=True)
class MarketDataProviderMetadata:
    """Stable provider capabilities exposed to connector orchestration."""

    provider_id: str
    display_name: str
    requires_credentials: bool
    supported_market_types: tuple[MarketType, ...]
    supported_timeframes: tuple[Timeframe, ...]
    default_pair: TradingPair
    access_mode: MarketDataProviderAccessMode
    max_closed_candles: int | None


class MarketDataProviderError(RuntimeError):
    """Base error raised when an external market-data provider fails."""

    def __init__(
        self,
        message: str,
        *,
        code: MarketDataProviderErrorCode = MarketDataProviderErrorCode.REQUEST_FAILED,
    ) -> None:
        super().__init__(message)
        self.code = code


class MarketDataProviderResponseError(MarketDataProviderError):
    """Raised when a provider returns an unexpected or invalid payload."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code=MarketDataProviderErrorCode.RESPONSE_INVALID,
        )


class MarketDataProviderQueryError(MarketDataProviderError):
    """Raised when a valid provider cannot serve the requested historical query."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code=MarketDataProviderErrorCode.UNAVAILABLE,
        )


class MarketDataProviderTimeoutError(MarketDataProviderError):
    """Raised when a bounded provider request exceeds its timeout."""

    def __init__(self, message: str = "public market-data request timed out") -> None:
        super().__init__(
            message,
            code=MarketDataProviderErrorCode.TIMEOUT,
        )


class MarketDataProviderHttpError(MarketDataProviderError):
    """HTTP failure with enough metadata for deterministic retry decisions."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        retry_after_seconds: float | None = None,
    ) -> None:
        if status_code == 429:
            code = MarketDataProviderErrorCode.RATE_LIMITED
        elif status_code in {408, 504}:
            code = MarketDataProviderErrorCode.TIMEOUT
        else:
            code = MarketDataProviderErrorCode.HTTP_ERROR

        super().__init__(message, code=code)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class MarketDataRetryPolicy:
    """Bounded retry/backoff policy for public read-only market-data requests."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0
    max_retry_after_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max attempts must be greater than zero")
        if self.initial_backoff_seconds < 0:
            raise ValueError("initial backoff cannot be negative")
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError("maximum backoff cannot be lower than initial backoff")
        if self.max_retry_after_seconds < 0:
            raise ValueError("maximum retry-after cannot be negative")


JsonFetcher = Callable[[str, float], Awaitable[object]]
Sleep = Callable[[float], Awaitable[None]]

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_TIMEFRAME_DURATIONS: dict[Timeframe, timedelta] = {
    Timeframe.MINUTES_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.HOURS_4: timedelta(hours=4),
    Timeframe.DAY_1: timedelta(days=1),
}


async def _fetch_json(url: str, timeout_seconds: float) -> object:
    """Fetch one public JSON document without introducing a runtime HTTP dependency."""

    def load() -> object:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "trd-bot-v2-research/0.1",
            },
        )

        with urlopen(request, timeout=timeout_seconds) as response:
            payload: object = json.loads(response.read().decode("utf-8"))

        return payload

    try:
        return await asyncio.to_thread(load)
    except HTTPError as exc:
        retry_after_header = exc.headers.get("Retry-After") if exc.headers is not None else None
        retry_after_seconds = _parse_retry_after_seconds(retry_after_header)
        raise MarketDataProviderHttpError(
            "public market-data request failed",
            status_code=exc.code,
            retry_after_seconds=retry_after_seconds,
        ) from exc
    except TimeoutError as exc:
        raise MarketDataProviderTimeoutError() from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketDataProviderError("public market-data request failed") from exc


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None

    try:
        parsed = float(value.strip())
    except ValueError:
        return None

    if parsed < 0:
        return None
    return parsed


def _to_epoch_milliseconds(value: datetime) -> int:
    normalized = value.astimezone(UTC)
    delta = normalized - _EPOCH

    return ((delta.days * 86_400) + delta.seconds) * 1_000 + (delta.microseconds // 1_000)


def _from_epoch_milliseconds(value: int) -> datetime:
    return _EPOCH + timedelta(milliseconds=value)


class MarketDataProvider(ABC):
    """Interface for retrieving historical market candles."""

    @property
    @abstractmethod
    def metadata(self) -> MarketDataProviderMetadata:
        """Return stable capabilities for this provider implementation."""

        raise NotImplementedError

    @abstractmethod
    async def test_connection(self) -> None:
        """Validate that the read-only provider endpoint is reachable and usable."""

        raise NotImplementedError

    @abstractmethod
    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        """Return closed candles in chronological order."""

        raise NotImplementedError

    @staticmethod
    def _validate_query(
        start_time: datetime,
        end_time: datetime,
        limit: int | None,
    ) -> None:
        if start_time.tzinfo is None or start_time.utcoffset() is None:
            raise ValueError("start time must include timezone information")

        if end_time.tzinfo is None or end_time.utcoffset() is None:
            raise ValueError("end time must include timezone information")

        if end_time <= start_time:
            raise ValueError("end time must be after start time")

        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than zero")


class RetryingPublicJsonMarketDataProvider(MarketDataProvider):
    """Shared bounded HTTP/retry behavior for public read-only JSON providers."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        retry_policy: MarketDataRetryPolicy | None = None,
        fetch_json: JsonFetcher | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout must be greater than zero")

        self._timeout_seconds = timeout_seconds
        self._retry_policy = retry_policy or MarketDataRetryPolicy()
        self._fetch_json = fetch_json or _fetch_json
        self._sleep = sleep or asyncio.sleep

    async def _request_json(self, url: str) -> object:
        """Execute one bounded public request with retry/backoff and rate-limit handling."""

        policy = self._retry_policy

        for attempt in range(1, policy.max_attempts + 1):
            try:
                return await self._fetch_json(url, self._timeout_seconds)
            except MarketDataProviderHttpError as exc:
                if not self._is_retryable_status(exc.status_code) or attempt >= policy.max_attempts:
                    raise
                delay = self._retry_delay(
                    attempt=attempt,
                    retry_after_seconds=exc.retry_after_seconds,
                )
            except MarketDataProviderError:
                if attempt >= policy.max_attempts:
                    raise
                delay = self._retry_delay(attempt=attempt)
            except TimeoutError as exc:
                timeout_error = MarketDataProviderTimeoutError()
                if attempt >= policy.max_attempts:
                    raise timeout_error from exc
                delay = self._retry_delay(attempt=attempt)

            await self._sleep(delay)

        raise RuntimeError("market-data retry policy exhausted without a result")

    def _retry_delay(
        self,
        *,
        attempt: int,
        retry_after_seconds: float | None = None,
    ) -> float:
        policy = self._retry_policy
        exponential = min(
            policy.initial_backoff_seconds * float(2 ** (attempt - 1)),
            policy.max_backoff_seconds,
        )

        if retry_after_seconds is None:
            return exponential

        bounded_retry_after = min(
            retry_after_seconds,
            policy.max_retry_after_seconds,
        )
        return max(exponential, bounded_retry_after)

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code in {408, 425, 429, 500, 502, 503, 504}

    def _validate_capabilities(
        self,
        *,
        pair: TradingPair,
        timeframe: Timeframe,
    ) -> None:
        if pair.market_type not in self.metadata.supported_market_types:
            raise ValueError("market type is not supported by provider")

        if timeframe not in self.metadata.supported_timeframes:
            raise ValueError("timeframe is not supported by provider")


class InMemoryMarketDataProvider(MarketDataProvider):
    """Market-data provider backed by an in-memory candle collection."""

    _METADATA = MarketDataProviderMetadata(
        provider_id="in-memory",
        display_name="In-memory",
        requires_credentials=False,
        supported_market_types=(MarketType.SPOT,),
        supported_timeframes=tuple(Timeframe),
        default_pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
        access_mode=MarketDataProviderAccessMode.DIRECT,
        max_closed_candles=None,
    )

    def __init__(self, candles: Iterable[OHLCVCandle]) -> None:
        self._candles = tuple(
            sorted(
                candles,
                key=lambda candle: candle.open_time,
            )
        )

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return self._METADATA

    async def test_connection(self) -> None:
        """In-memory provider is always available to isolated tests."""

    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        self._validate_query(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        result = [
            candle
            for candle in self._candles
            if candle.pair == pair
            and candle.timeframe == timeframe
            and candle.is_closed
            and start_time <= candle.open_time < end_time
        ]

        if limit is not None:
            return result[:limit]

        return result


class BinancePublicMarketDataProvider(RetryingPublicJsonMarketDataProvider):
    """Historical spot-candle provider using Binance public market-data endpoints only."""

    _API_BASE_URL = "https://data-api.binance.vision/api/v3"
    _KLINES_URL = f"{_API_BASE_URL}/klines"
    _PING_URL = f"{_API_BASE_URL}/ping"
    _MAX_PAGE_SIZE = 1_000
    _METADATA = MarketDataProviderMetadata(
        provider_id="binance-public",
        display_name="Binance Public Market Data",
        requires_credentials=False,
        supported_market_types=(MarketType.SPOT,),
        supported_timeframes=tuple(Timeframe),
        default_pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
        access_mode=MarketDataProviderAccessMode.VPN_REQUIRED,
        max_closed_candles=None,
    )

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return self._METADATA

    async def test_connection(self) -> None:
        """Probe Binance's public market-data API without account credentials."""

        payload = await self._request_json(self._PING_URL)

        if not isinstance(payload, dict):
            raise MarketDataProviderResponseError(
                "binance public market-data health response must be an object"
            )

    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        self._validate_query(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        self._validate_capabilities(
            pair=pair,
            timeframe=timeframe,
        )

        normalized_start = start_time.astimezone(UTC)
        normalized_end = end_time.astimezone(UTC)
        start_milliseconds = _to_epoch_milliseconds(normalized_start)
        end_milliseconds = _to_epoch_milliseconds(normalized_end)

        if end_milliseconds <= start_milliseconds:
            return []

        cursor = normalized_start
        candles: list[OHLCVCandle] = []

        while cursor < normalized_end:
            if limit is not None and len(candles) >= limit:
                break

            remaining = None if limit is None else limit - len(candles)
            page_size = (
                self._MAX_PAGE_SIZE if remaining is None else min(self._MAX_PAGE_SIZE, remaining)
            )

            payload = await self._request_json(
                self._build_url(
                    pair=pair,
                    timeframe=timeframe,
                    start_time=cursor,
                    end_time=normalized_end,
                    page_size=page_size,
                )
            )
            rows = self._validate_payload(payload)

            if not rows:
                break

            last_open_time: datetime | None = None

            for row in rows:
                candle = self._parse_candle(
                    row,
                    pair=pair,
                    timeframe=timeframe,
                )
                last_open_time = candle.open_time

                if candle.is_closed and normalized_start <= candle.open_time < normalized_end:
                    candles.append(candle)

                    if limit is not None and len(candles) >= limit:
                        break

            if limit is not None and len(candles) >= limit:
                break

            if last_open_time is None or len(rows) < page_size:
                break

            next_cursor = last_open_time + _TIMEFRAME_DURATIONS[timeframe]

            if next_cursor <= cursor:
                raise MarketDataProviderResponseError(
                    "binance public market-data pagination did not advance"
                )

            cursor = next_cursor

        return sorted(
            candles,
            key=lambda candle: candle.open_time,
        )

    def _build_url(
        self,
        *,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        page_size: int,
    ) -> str:
        query = urlencode(
            {
                "symbol": f"{pair.base_asset}{pair.quote_asset}",
                "interval": timeframe.value,
                "startTime": _to_epoch_milliseconds(start_time),
                "endTime": _to_epoch_milliseconds(end_time) - 1,
                "limit": page_size,
            }
        )

        return f"{self._KLINES_URL}?{query}"

    @staticmethod
    def _validate_payload(payload: object) -> list[object]:
        if not isinstance(payload, list):
            raise MarketDataProviderResponseError(
                "binance public market-data response must be a list"
            )

        return payload

    def _parse_candle(
        self,
        row: object,
        *,
        pair: TradingPair,
        timeframe: Timeframe,
    ) -> OHLCVCandle:
        if not isinstance(row, list) or len(row) < 7:
            raise MarketDataProviderResponseError(
                "binance public market-data candle must contain OHLCV fields"
            )

        try:
            open_time = _from_epoch_milliseconds(self._parse_integer(row[0]))
            close_time = _from_epoch_milliseconds(self._parse_integer(row[6]))
            received_at = datetime.now(UTC)

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
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise MarketDataProviderResponseError(
                "binance public market-data candle contains invalid values"
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
