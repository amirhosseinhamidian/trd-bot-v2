from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_historical_dataset_committer,
    get_market_data_connection_repository,
    get_market_data_import_repository,
    get_market_data_provider_catalog,
)
from trd_bot.main import app
from trd_bot.market_data import (
    InMemoryMarketDataConnectionRepository,
    KrakenPublicMarketDataProvider,
    MarketDataProviderCatalog,
    NobitexPublicMarketDataProvider,
)
from trd_bot.market_data.import_history import InMemoryMarketDataImportRepository
from trd_bot.research import (
    InMemoryDatasetRepository,
    InMemoryHistoricalDatasetCommitter,
)

client = TestClient(app)
NOW = datetime(2026, 9, 23, 13, 30, tzinfo=UTC)
START = datetime(2026, 9, 23, 10, tzinfo=UTC)
END = datetime(2026, 9, 23, 12, tzinfo=UTC)


def build_nobitex_payload(*open_times: datetime) -> dict[str, object]:
    return {
        "s": "ok",
        "t": [int(value.timestamp()) for value in open_times],
        "o": ["100" for _ in open_times],
        "h": ["110" for _ in open_times],
        "l": ["95" for _ in open_times],
        "c": ["105" for _ in open_times],
        "v": ["12.5" for _ in open_times],
    }


def build_kraken_payload(*open_times: datetime) -> dict[str, object]:
    return {
        "error": [],
        "result": {
            "BTC/USD": [
                [
                    int(value.timestamp()),
                    "100",
                    "110",
                    "95",
                    "105",
                    "103",
                    "12.5",
                    10,
                ]
                for value in open_times
            ],
            "last": int(NOW.timestamp()),
        },
    }


@pytest.fixture
def provider_e2e_dependencies() -> Iterator[dict[str, list[str]]]:
    requests: dict[str, list[str]] = {"nobitex": [], "kraken": []}

    async def fetch_nobitex(url: str, timeout_seconds: float) -> object:
        del timeout_seconds
        requests["nobitex"].append(url)
        return build_nobitex_payload(START, START + timedelta(hours=1))

    async def fetch_kraken(url: str, timeout_seconds: float) -> object:
        del timeout_seconds
        requests["kraken"].append(url)
        return build_kraken_payload(NOW - timedelta(hours=2))

    connections = InMemoryMarketDataConnectionRepository()
    datasets = InMemoryDatasetRepository()
    history = InMemoryMarketDataImportRepository()
    committer = InMemoryHistoricalDatasetCommitter(datasets=datasets, history=history)
    providers = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: KrakenPublicMarketDataProvider(
                fetch_json=fetch_kraken,
                clock=lambda: NOW,
            ),
            "nobitex-public": lambda: NobitexPublicMarketDataProvider(
                fetch_json=fetch_nobitex,
                clock=lambda: NOW,
                page_delay_seconds=0,
            ),
        }
    )

    app.dependency_overrides[get_market_data_connection_repository] = lambda: connections
    app.dependency_overrides[get_market_data_provider_catalog] = lambda: providers
    app.dependency_overrides[get_dataset_repository] = lambda: datasets
    app.dependency_overrides[get_market_data_import_repository] = lambda: history
    app.dependency_overrides[get_historical_dataset_committer] = lambda: committer

    try:
        yield requests
    finally:
        app.dependency_overrides.pop(get_market_data_connection_repository, None)
        app.dependency_overrides.pop(get_market_data_provider_catalog, None)
        app.dependency_overrides.pop(get_dataset_repository, None)
        app.dependency_overrides.pop(get_market_data_import_repository, None)
        app.dependency_overrides.pop(get_historical_dataset_committer, None)


def test_nobitex_api_lifecycle_imports_a_dataset_with_real_adapter_logic(
    provider_e2e_dependencies: dict[str, list[str]],
) -> None:
    providers_response = client.get("/api/v1/market-data/providers")

    assert providers_response.status_code == 200
    providers = {item["provider_id"]: item for item in providers_response.json()}
    assert providers["nobitex-public"]["access_mode"] == "direct"
    assert providers["nobitex-public"]["default_pair"] == {
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "market_type": "spot",
    }
    assert providers["nobitex-public"]["max_closed_candles"] is None
    assert providers["kraken-public"]["access_mode"] == "vpn_required"
    assert providers["kraken-public"]["max_closed_candles"] == 719

    created = client.post(
        "/api/v1/market-data/connections",
        json={
            "provider_id": "nobitex-public",
            "display_name": "Nobitex direct feed",
        },
    )
    assert created.status_code == 201
    connection_id = created.json()["connection_id"]

    tested = client.post(f"/api/v1/market-data/connections/{connection_id}/test")
    assert tested.status_code == 200
    assert tested.json()["health_status"] == "healthy"

    enabled = client.post(f"/api/v1/market-data/connections/{connection_id}/enable")
    assert enabled.status_code == 200
    assert enabled.json()["state"] == "enabled"

    request = {
        "name": "Nobitex BTC acceptance dataset",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": "1h",
        "start_time": START.isoformat(),
        "end_time": END.isoformat(),
    }
    preview = client.post(
        f"/api/v1/market-data/connections/{connection_id}/datasets/preview",
        json=request,
    )
    assert preview.status_code == 200
    assert preview.json()["provider_id"] == "nobitex-public"
    assert preview.json()["candle_count"] == 2
    assert preview.json()["ready_to_import"] is True
    assert preview.json()["quality_report"]["coverage"]["coverage_percent"] == 100.0

    request["preview_checksum"] = preview.json()["preview_checksum"]
    imported = client.post(
        f"/api/v1/market-data/connections/{connection_id}/datasets",
        json=request,
    )
    assert imported.status_code == 201
    dataset_id = imported.json()["dataset_id"]
    assert imported.json()["source"] == "nobitex-public"
    assert imported.json()["candle_count"] == 2

    dataset = client.get(f"/api/v1/research/datasets/{dataset_id}/summary")
    assert dataset.status_code == 200
    assert dataset.json()["provenance"]["connection_id"] == connection_id
    assert dataset.json()["provenance"]["provider_id"] == "nobitex-public"

    history = client.get(f"/api/v1/market-data/connections/{connection_id}/imports")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["dataset_id"] == dataset_id
    assert len(provider_e2e_dependencies["nobitex"]) == 3


def test_kraken_old_range_returns_actionable_bad_request_before_fetch(
    provider_e2e_dependencies: dict[str, list[str]],
) -> None:
    created = client.post(
        "/api/v1/market-data/connections",
        json={
            "provider_id": "kraken-public",
            "display_name": "Kraken VPN feed",
        },
    )
    assert created.status_code == 201
    connection_id = created.json()["connection_id"]

    tested = client.post(f"/api/v1/market-data/connections/{connection_id}/test")
    assert tested.status_code == 200
    enabled = client.post(f"/api/v1/market-data/connections/{connection_id}/enable")
    assert enabled.status_code == 200

    response = client.post(
        f"/api/v1/market-data/connections/{connection_id}/datasets/preview",
        json={
            "name": "Unsupported old Kraken range",
            "pair": {
                "base_asset": "BTC",
                "quote_asset": "USD",
                "market_type": "spot",
            },
            "timeframe": "1h",
            "start_time": (NOW - timedelta(days=31)).isoformat(),
            "end_time": NOW.isoformat(),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "requested start time is outside Kraken's recent OHLC retention window"
    )
    assert len(provider_e2e_dependencies["kraken"]) == 1
