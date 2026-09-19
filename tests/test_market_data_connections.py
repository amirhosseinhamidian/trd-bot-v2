from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    InMemoryMarketDataConnectionRepository,
    MarketDataConnectionHealth,
    MarketDataConnectionManager,
    MarketDataConnectionState,
    MarketDataConnectionStateError,
    MarketDataProvider,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderErrorCode,
    MarketDataProviderMetadata,
)

BASE_TIME = datetime(2026, 8, 31, 12, tzinfo=UTC)


class SyntheticProvider(MarketDataProvider):
    def __init__(self, *, should_fail: bool = False) -> None:
        self._should_fail = should_fail

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return MarketDataProviderMetadata(
            provider_id="synthetic-public",
            display_name="Synthetic Public",
            requires_credentials=False,
            supported_market_types=(MarketType.SPOT,),
            supported_timeframes=(Timeframe.HOUR_1,),
        )

    async def test_connection(self) -> None:
        if self._should_fail:
            raise MarketDataProviderError("synthetic provider unavailable")

    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        del pair
        del timeframe
        del start_time
        del end_time
        del limit
        return []


class CredentialedSyntheticProvider(SyntheticProvider):
    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return MarketDataProviderMetadata(
            provider_id="credentialed-synthetic",
            display_name="Credentialed Synthetic",
            requires_credentials=True,
            supported_market_types=(MarketType.SPOT,),
            supported_timeframes=(Timeframe.HOUR_1,),
        )


def clock(*values: datetime) -> Iterator[datetime]:
    yield from values


def test_default_provider_catalog_exposes_binance_public_only() -> None:
    catalog = MarketDataProviderCatalog()

    metadata = catalog.list_metadata()

    assert len(metadata) == 1
    assert metadata[0].provider_id == "binance-public"
    assert metadata[0].requires_credentials is False


@pytest.mark.asyncio
async def test_connection_must_pass_health_check_before_enable() -> None:
    repository = InMemoryMarketDataConnectionRepository()
    catalog = MarketDataProviderCatalog(
        {
            "synthetic-public": SyntheticProvider,
        }
    )
    times = clock(
        BASE_TIME,
        BASE_TIME + timedelta(minutes=1),
        BASE_TIME + timedelta(minutes=2),
        BASE_TIME + timedelta(minutes=3),
    )
    manager = MarketDataConnectionManager(
        repository=repository,
        providers=catalog,
        clock=lambda: next(times),
    )

    connection = manager.create(
        provider_id="synthetic-public",
        display_name="Synthetic research feed",
    )

    assert connection.state is MarketDataConnectionState.DISABLED
    assert connection.health_status is MarketDataConnectionHealth.UNTESTED
    assert connection.last_tested_at is None

    with pytest.raises(
        MarketDataConnectionStateError,
        match="must pass a health check",
    ):
        manager.enable(connection.connection_id)

    healthy = await manager.test_connection(connection.connection_id)
    assert healthy.state is MarketDataConnectionState.DISABLED
    assert healthy.health_status is MarketDataConnectionHealth.HEALTHY
    assert healthy.last_tested_at == BASE_TIME + timedelta(minutes=1)
    assert healthy.last_error is None

    enabled = manager.enable(connection.connection_id)
    assert enabled.state is MarketDataConnectionState.ENABLED
    assert enabled.updated_at == BASE_TIME + timedelta(minutes=2)

    disabled = manager.disable(connection.connection_id)
    assert disabled.state is MarketDataConnectionState.DISABLED
    assert disabled.health_status is MarketDataConnectionHealth.HEALTHY
    assert disabled.updated_at == BASE_TIME + timedelta(minutes=3)


@pytest.mark.asyncio
async def test_failed_health_check_disables_connection_and_records_safe_error() -> None:
    repository = InMemoryMarketDataConnectionRepository()
    catalog = MarketDataProviderCatalog(
        {
            "synthetic-public": lambda: SyntheticProvider(should_fail=True),
        }
    )
    times = clock(
        BASE_TIME,
        BASE_TIME + timedelta(minutes=1),
    )
    manager = MarketDataConnectionManager(
        repository=repository,
        providers=catalog,
        clock=lambda: next(times),
    )
    connection = manager.create(
        provider_id="synthetic-public",
        display_name="Synthetic research feed",
    )

    failed = await manager.test_connection(connection.connection_id)

    assert failed.state is MarketDataConnectionState.DISABLED
    assert failed.health_status is MarketDataConnectionHealth.UNHEALTHY
    assert failed.last_tested_at == BASE_TIME + timedelta(minutes=1)
    assert failed.last_error_code is MarketDataProviderErrorCode.REQUEST_FAILED
    assert failed.last_error == "synthetic provider unavailable"


def test_connection_manager_rejects_credentialed_provider_for_now() -> None:
    repository = InMemoryMarketDataConnectionRepository()
    catalog = MarketDataProviderCatalog(
        {
            "credentialed-synthetic": CredentialedSyntheticProvider,
        }
    )
    manager = MarketDataConnectionManager(
        repository=repository,
        providers=catalog,
        clock=lambda: BASE_TIME,
    )

    with pytest.raises(
        ValueError,
        match="credentialed market-data providers are not supported yet",
    ):
        manager.create(
            provider_id="credentialed-synthetic",
            display_name="Not allowed yet",
        )
