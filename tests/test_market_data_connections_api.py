from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_market_data_connection_repository,
    get_market_data_provider_catalog,
)
from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.main import app
from trd_bot.market_data import (
    InMemoryMarketDataConnectionRepository,
    MarketDataProvider,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderMetadata,
)

client = TestClient(app)


class ApiSyntheticProvider(MarketDataProvider):
    def __init__(self, health_state: dict[str, bool]) -> None:
        self._health_state = health_state

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
        if self._health_state["should_fail"]:
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


@pytest.fixture
def connection_dependencies() -> Iterator[
    tuple[InMemoryMarketDataConnectionRepository, dict[str, bool]]
]:
    repository = InMemoryMarketDataConnectionRepository()
    health_state = {"should_fail": False}
    providers = MarketDataProviderCatalog(
        {
            "synthetic-public": lambda: ApiSyntheticProvider(health_state),
        }
    )

    app.dependency_overrides[get_market_data_connection_repository] = lambda: repository
    app.dependency_overrides[get_market_data_provider_catalog] = lambda: providers

    try:
        yield repository, health_state
    finally:
        app.dependency_overrides.pop(get_market_data_connection_repository, None)
        app.dependency_overrides.pop(get_market_data_provider_catalog, None)


def test_api_lists_allowlisted_provider_capabilities(
    connection_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        dict[str, bool],
    ],
) -> None:
    del connection_dependencies

    response = client.get("/api/v1/market-data/providers")

    assert response.status_code == 200
    assert response.json() == [
        {
            "provider_id": "synthetic-public",
            "display_name": "Synthetic Public",
            "requires_credentials": False,
            "supported_market_types": ["spot"],
            "supported_timeframes": ["1h"],
        }
    ]


def test_api_connection_lifecycle_requires_successful_health_check(
    connection_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        dict[str, bool],
    ],
) -> None:
    del connection_dependencies

    create_response = client.post(
        "/api/v1/market-data/connections",
        json={
            "provider_id": "synthetic-public",
            "display_name": "Synthetic historical feed",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    connection_id = created["connection_id"]
    assert created["state"] == "disabled"
    assert created["health_status"] == "untested"

    enable_before_test = client.post(f"/api/v1/market-data/connections/{connection_id}/enable")
    assert enable_before_test.status_code == 409

    test_response = client.post(f"/api/v1/market-data/connections/{connection_id}/test")
    assert test_response.status_code == 200
    assert test_response.json()["health_status"] == "healthy"
    assert test_response.json()["last_tested_at"] is not None

    enable_response = client.post(f"/api/v1/market-data/connections/{connection_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["state"] == "enabled"

    list_response = client.get("/api/v1/market-data/connections")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["connection_id"] == connection_id

    get_response = client.get(f"/api/v1/market-data/connections/{connection_id}")
    assert get_response.status_code == 200
    assert get_response.json()["state"] == "enabled"

    disable_response = client.post(f"/api/v1/market-data/connections/{connection_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["state"] == "disabled"
    assert disable_response.json()["health_status"] == "healthy"


def test_api_failed_health_check_returns_persisted_unhealthy_state(
    connection_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        dict[str, bool],
    ],
) -> None:
    _, health_state = connection_dependencies

    create_response = client.post(
        "/api/v1/market-data/connections",
        json={
            "provider_id": "synthetic-public",
            "display_name": "Synthetic historical feed",
        },
    )
    connection_id = create_response.json()["connection_id"]
    health_state["should_fail"] = True

    response = client.post(f"/api/v1/market-data/connections/{connection_id}/test")

    assert response.status_code == 200
    assert response.json()["state"] == "disabled"
    assert response.json()["health_status"] == "unhealthy"
    assert response.json()["last_error"] == "synthetic provider unavailable"


def test_api_rejects_unknown_provider(
    connection_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        dict[str, bool],
    ],
) -> None:
    del connection_dependencies

    response = client.post(
        "/api/v1/market-data/connections",
        json={
            "provider_id": "unknown-provider",
            "display_name": "Unknown",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "market-data provider is not available"


def test_api_returns_404_for_missing_connection(
    connection_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        dict[str, bool],
    ],
) -> None:
    del connection_dependencies

    response = client.get("/api/v1/market-data/connections/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "market-data connection not found"
