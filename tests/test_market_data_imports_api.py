from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_market_data_connection_repository,
    get_market_data_import_repository,
    get_market_data_provider_catalog,
)
from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.main import app
from trd_bot.market_data import (
    InMemoryMarketDataConnectionRepository,
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataProvider,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderMetadata,
)
from trd_bot.market_data.import_history import InMemoryMarketDataImportRepository
from trd_bot.research import InMemoryDatasetRepository

client = TestClient(app)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
START = datetime(2026, 8, 20, 10, tzinfo=UTC)
CONNECTION_ID = "market-data-connection-historical-test"


@dataclass
class ProviderState:
    candles: list[OHLCVCandle]
    fail_fetch: bool = False


def create_candle(hour_offset: int) -> OHLCVCandle:
    open_time = START + timedelta(hours=hour_offset)
    return OHLCVCandle(
        source="synthetic-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=open_time,
        close_time=open_time + timedelta(hours=1) - timedelta(milliseconds=1),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1000"),
        is_closed=True,
    )


class HistoricalSyntheticProvider(MarketDataProvider):
    def __init__(self, state: ProviderState) -> None:
        self._state = state

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
        return None

    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        if self._state.fail_fetch:
            raise MarketDataProviderError("synthetic historical fetch failed")

        candles = [
            candle
            for candle in self._state.candles
            if candle.pair == pair
            and candle.timeframe == timeframe
            and start_time <= candle.open_time < end_time
        ]
        return candles if limit is None else candles[:limit]


@pytest.fixture
def historical_import_dependencies() -> Iterator[
    tuple[InMemoryMarketDataConnectionRepository, InMemoryDatasetRepository, ProviderState]
]:
    state = ProviderState(candles=[create_candle(0), create_candle(1)])
    connections = InMemoryMarketDataConnectionRepository()
    datasets = InMemoryDatasetRepository()
    history = InMemoryMarketDataImportRepository()
    providers = MarketDataProviderCatalog(
        {
            "synthetic-public": lambda: HistoricalSyntheticProvider(state),
        }
    )

    connections.save(
        MarketDataConnection(
            connection_id=CONNECTION_ID,
            provider_id="synthetic-public",
            display_name="Synthetic historical feed",
            state=MarketDataConnectionState.ENABLED,
            health_status=MarketDataConnectionHealth.HEALTHY,
            created_at=START,
            updated_at=START,
            last_tested_at=START,
        )
    )

    app.dependency_overrides[get_market_data_connection_repository] = lambda: connections
    app.dependency_overrides[get_market_data_provider_catalog] = lambda: providers
    app.dependency_overrides[get_dataset_repository] = lambda: datasets
    app.dependency_overrides[get_market_data_import_repository] = lambda: history

    try:
        yield connections, datasets, state
    finally:
        app.dependency_overrides.pop(get_market_data_connection_repository, None)
        app.dependency_overrides.pop(get_market_data_provider_catalog, None)
        app.dependency_overrides.pop(get_dataset_repository, None)
        app.dependency_overrides.pop(get_market_data_import_repository, None)


def request_payload(*, timeframe: str = "1h") -> dict[str, object]:
    return {
        "name": "BTC historical import",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": timeframe,
        "start_time": START.isoformat(),
        "end_time": (START + timedelta(hours=4)).isoformat(),
    }


def test_preview_fetches_normalized_candles_without_persisting_dataset(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, _ = historical_import_dependencies

    response = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets/preview",
        json=request_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_id"] == "synthetic-public"
    assert payload["candle_count"] == 2
    assert payload["ready_to_import"] is True
    assert payload["quality_report"]["issues"] == []
    assert datasets.count() == 0


def test_import_persists_immutable_dataset_and_is_idempotent(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, _ = historical_import_dependencies
    url = f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets"

    first = client.post(url, json=request_payload())
    second = client.post(url, json=request_payload())

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["dataset_id"] == second.json()["dataset_id"]
    assert first.json()["source"] == "synthetic-public"
    assert first.json()["candle_count"] == 2
    assert datasets.count() == 1
    assert datasets.get(first.json()["dataset_id"]) is not None

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=succeeded"
    )
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["total"] == 2
    assert history_payload["items"][0]["status"] == "succeeded"
    assert history_payload["items"][0]["dataset_id"] == first.json()["dataset_id"]
    assert history_payload["items"][0]["root_import_id"] is None
    assert history_payload["items"][0]["version_number"] is None

    root_record = history_payload["items"][-1]
    assert root_record["root_import_id"] == root_record["import_id"]
    assert root_record["version_number"] == 1
    assert root_record["operation"] == "import"

    import_id = history_payload["items"][0]["import_id"]
    detail = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{import_id}"
    )
    assert detail.status_code == 200
    assert detail.json()["import_id"] == import_id

    dataset_detail = client.get(
        f"/api/v1/research/datasets/{first.json()['dataset_id']}/summary"
    )
    assert dataset_detail.status_code == 200
    dataset_payload = dataset_detail.json()
    assert dataset_payload["schema_version"] == 2
    assert dataset_payload["provenance"]["kind"] == "market_data_import"
    assert dataset_payload["provenance"]["connection_id"] == CONNECTION_ID
    assert dataset_payload["provenance"]["provider_id"] == "synthetic-public"
    assert dataset_payload["provenance"]["import_id"] == history_payload["items"][-1]["import_id"]
    assert dataset_payload["quality_report"]["candles_checked"] == 2
    assert dataset_payload["quality_report"]["issues"] == []


def test_refresh_without_content_change_records_new_version_without_new_snapshot(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, _ = historical_import_dependencies
    import_response = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=request_payload(),
    )
    assert import_response.status_code == 201

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=succeeded"
    )
    root = history_response.json()["items"][0]

    refreshed = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{root['import_id']}/refresh"
    )

    assert refreshed.status_code == 201
    payload = refreshed.json()
    assert payload["operation"] == "refresh"
    assert payload["root_import_id"] == root["import_id"]
    assert payload["parent_import_id"] == root["import_id"]
    assert payload["version_number"] == 2
    assert payload["source_dataset_id"] == root["dataset_id"]
    assert payload["dataset_id"] == root["dataset_id"]
    assert payload["content_changed"] is False
    assert datasets.count() == 1

    versions = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{payload['import_id']}/versions"
    )
    assert versions.status_code == 200
    assert versions.json()["total"] == 2
    assert versions.json()["items"][0]["version_number"] == 2
    assert versions.json()["items"][1]["version_number"] == 1

    stale = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{root['import_id']}/refresh"
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "only the latest successful dataset version can be refreshed"


def test_refresh_with_changed_content_creates_new_immutable_snapshot(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, state = historical_import_dependencies
    imported = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=request_payload(),
    )
    assert imported.status_code == 201

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=succeeded"
    )
    root = history_response.json()["items"][0]

    state.candles = [
        create_candle(0),
        create_candle(1).model_copy(update={"close_price": Decimal("106")}),
    ]

    refreshed = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{root['import_id']}/refresh"
    )

    assert refreshed.status_code == 201
    payload = refreshed.json()
    assert payload["content_changed"] is True
    assert payload["version_number"] == 2
    assert payload["dataset_id"] != root["dataset_id"]
    assert datasets.count() == 2

    dataset_detail = client.get(
        f"/api/v1/research/datasets/{payload['dataset_id']}/summary"
    )
    assert dataset_detail.status_code == 200
    assert dataset_detail.json()["provenance"]["import_id"] == payload["import_id"]


def test_failed_refresh_is_recorded_without_consuming_a_version_number(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, _, state = historical_import_dependencies
    imported = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=request_payload(),
    )
    assert imported.status_code == 201

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=succeeded"
    )
    root = history_response.json()["items"][0]
    state.fail_fetch = True

    failed = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{root['import_id']}/refresh"
    )

    assert failed.status_code == 502

    versions = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{root['import_id']}/versions"
    )
    assert versions.status_code == 200
    assert versions.json()["total"] == 2
    failed_record = versions.json()["items"][0]
    assert failed_record["operation"] == "refresh"
    assert failed_record["status"] == "failed"
    assert failed_record["root_import_id"] == root["import_id"]
    assert failed_record["parent_import_id"] == root["import_id"]
    assert failed_record["source_dataset_id"] == root["dataset_id"]
    assert failed_record["version_number"] is None
    assert failed_record["content_changed"] is None

    state.fail_fetch = False
    retried = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{root['import_id']}/refresh"
    )
    assert retried.status_code == 201
    assert retried.json()["version_number"] == 2


def test_import_requires_enabled_connection(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    connections, _, _ = historical_import_dependencies
    existing = connections.get(CONNECTION_ID)
    assert existing is not None
    connections.save(
        existing.model_copy(
            update={
                "state": MarketDataConnectionState.DISABLED,
            }
        )
    )

    response = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=request_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "market-data connection must be enabled before historical import"
    )


def test_preview_exposes_quality_failure_and_import_rejects_it(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, state = historical_import_dependencies
    state.candles = [create_candle(0), create_candle(2)]

    preview = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets/preview",
        json=request_payload(),
    )
    imported = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=request_payload(),
    )

    assert preview.status_code == 200
    assert preview.json()["ready_to_import"] is False
    assert preview.json()["quality_report"]["issues"][0]["code"] == "missing_candle"
    assert imported.status_code == 422
    assert imported.json()["detail"]["issues"][0]["code"] == "missing_candle"
    assert datasets.count() == 0


    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=failed"
    )
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 1
    assert history_response.json()["items"][0]["error_code"] == "quality_check_failed"
    assert history_response.json()["items"][0]["candle_count"] == 2


def test_import_maps_provider_failure_to_bad_gateway(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, _, state = historical_import_dependencies
    state.fail_fetch = True

    response = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=request_payload(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "synthetic historical fetch failed"


    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=failed"
    )
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 1
    assert history_response.json()["items"][0]["error_code"] == "provider_request_failed"
    assert history_response.json()["items"][0]["dataset_id"] is None


def test_import_rejects_unsupported_timeframe_before_fetch(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    del historical_import_dependencies

    response = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=request_payload(timeframe="4h"),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "timeframe is not supported by connection provider"
    )


def test_import_returns_not_found_for_unknown_connection(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    del historical_import_dependencies

    response = client.post(
        "/api/v1/market-data/connections/missing/datasets",
        json=request_payload(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "market-data connection not found"
