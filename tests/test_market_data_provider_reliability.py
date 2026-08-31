from collections.abc import Awaitable, Callable

import pytest

from trd_bot.market_data import (
    BinancePublicMarketDataProvider,
    MarketDataProviderError,
    MarketDataProviderHttpError,
    MarketDataRetryPolicy,
)


def build_provider(
    fetch_json: Callable[[str, float], Awaitable[object]],
    delays: list[float],
    *,
    max_attempts: int = 3,
) -> BinancePublicMarketDataProvider:
    async def sleep(delay: float) -> None:
        delays.append(delay)

    return BinancePublicMarketDataProvider(
        timeout_seconds=3.5,
        retry_policy=MarketDataRetryPolicy(
            max_attempts=max_attempts,
            initial_backoff_seconds=0.1,
            max_backoff_seconds=0.4,
            max_retry_after_seconds=2.0,
        ),
        fetch_json=fetch_json,
        sleep=sleep,
    )


@pytest.mark.asyncio
async def test_public_provider_retries_transient_request_failure_with_exponential_backoff() -> None:
    attempts = 0
    timeouts: list[float] = []
    delays: list[float] = []

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        nonlocal attempts
        del url
        attempts += 1
        timeouts.append(timeout_seconds)
        if attempts == 1:
            raise MarketDataProviderError("temporary network failure")
        return {}

    provider = build_provider(fetch_json, delays)

    await provider.test_connection()

    assert attempts == 2
    assert timeouts == [3.5, 3.5]
    assert delays == [0.1]


@pytest.mark.asyncio
async def test_public_provider_honors_bounded_retry_after_for_rate_limit() -> None:
    attempts = 0
    delays: list[float] = []

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        nonlocal attempts
        del url, timeout_seconds
        attempts += 1
        if attempts == 1:
            raise MarketDataProviderHttpError(
                "rate limited",
                status_code=429,
                retry_after_seconds=1.5,
            )
        return {}

    provider = build_provider(fetch_json, delays)

    await provider.test_connection()

    assert attempts == 2
    assert delays == [1.5]


@pytest.mark.asyncio
async def test_public_provider_does_not_retry_non_retryable_http_error() -> None:
    attempts = 0
    delays: list[float] = []

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        nonlocal attempts
        del url, timeout_seconds
        attempts += 1
        raise MarketDataProviderHttpError(
            "bad request",
            status_code=400,
        )

    provider = build_provider(fetch_json, delays)

    with pytest.raises(MarketDataProviderHttpError) as exc_info:
        await provider.test_connection()

    assert exc_info.value.status_code == 400
    assert attempts == 1
    assert delays == []


@pytest.mark.asyncio
async def test_public_provider_stops_after_bounded_retry_budget() -> None:
    attempts = 0
    delays: list[float] = []

    async def fetch_json(url: str, timeout_seconds: float) -> object:
        nonlocal attempts
        del url, timeout_seconds
        attempts += 1
        raise MarketDataProviderHttpError(
            "service unavailable",
            status_code=503,
        )

    provider = build_provider(fetch_json, delays, max_attempts=3)

    with pytest.raises(MarketDataProviderHttpError):
        await provider.test_connection()

    assert attempts == 3
    assert delays == [0.1, 0.2]


def test_retry_policy_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="max attempts"):
        MarketDataRetryPolicy(max_attempts=0)

    with pytest.raises(ValueError, match="maximum backoff"):
        MarketDataRetryPolicy(
            initial_backoff_seconds=1.0,
            max_backoff_seconds=0.5,
        )
