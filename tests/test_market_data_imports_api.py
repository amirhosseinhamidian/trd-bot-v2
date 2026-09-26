from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_background_job_repository,
    get_dataset_repository,
    get_historical_dataset_committer,
    get_market_data_connection_repository,
    get_market_data_import_repository,
    get_market_data_provider_catalog,
)
from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.jobs import BackgroundJob, BackgroundJobKind
from trd_bot.main import app
from trd_bot.market_data import (
    InMemoryMarketDataConnectionRepository,
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataProvider,
    MarketDataProviderAccessMode,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderMetadata,
)
from trd_bot.market_data.import_history import (
    InMemoryMarketDataImportRepository,
    MarketDataImportRecord,
)
from trd_bot.research import (
    DatasetSnapshot,
    HistoricalDatasetCommitResult,
    HistoricalDatasetRefreshConflictError,
    InMemoryDatasetRepository,
    InMemoryHistoricalDatasetCommitter,
    calculate_dataset_checksum,
)

client = TestClient(app)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
START = datetime(2026, 8, 20, 10, tzinfo=UTC)
CONNECTION_ID = "market-data-connection-historical-test"


@dataclass
class ProviderState:
    candles: list[OHLCVCandle]
    fail_fetch: bool = False
    failure_message: str = "synthetic historical fetch failed"


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
            default_pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
            access_mode=MarketDataProviderAccessMode.DIRECT,
            max_closed_candles=None,
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
            raise MarketDataProviderError(self._state.failure_message)

        candles = [
            candle
            for candle in self._state.candles
            if candle.pair == pair
            and candle.timeframe == timeframe
            and start_time <= candle.open_time < end_time
        ]
        return candles if limit is None else candles[:limit]


class ConflictingHistoricalDatasetCommitter:
    def commit(
        self,
        *,
        dataset: DatasetSnapshot,
        record: MarketDataImportRecord,
        expected_parent_import_id: str | None = None,
    ) -> HistoricalDatasetCommitResult:
        del dataset, record, expected_parent_import_id
        raise HistoricalDatasetRefreshConflictError(
            "dataset refresh lost a concurrency race; reload version history"
        )


class CapturingBackgroundJobRepository:
    def __init__(self) -> None:
        self.jobs_by_key: dict[tuple[BackgroundJobKind, str | None], BackgroundJob] = {}

    def enqueue(self, job: BackgroundJob) -> tuple[BackgroundJob, bool]:
        key = (job.kind, job.idempotency_key)
        existing = self.jobs_by_key.get(key)
        if existing is not None:
            return existing, False
        self.jobs_by_key[key] = job
        return job, True


@pytest.fixture
def historical_import_dependencies() -> Iterator[
    tuple[InMemoryMarketDataConnectionRepository, InMemoryDatasetRepository, ProviderState]
]:
    state = ProviderState(candles=[create_candle(0), create_candle(1)])
    connections = InMemoryMarketDataConnectionRepository()
    datasets = InMemoryDatasetRepository()
    history = InMemoryMarketDataImportRepository()
    committer = InMemoryHistoricalDatasetCommitter(datasets=datasets, history=history)
    providers = MarketDataProviderCatalog(
        {
            "synthetic-public": lambda: HistoricalSyntheticProvider(state),
        }
    )
    jobs = CapturingBackgroundJobRepository()

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
    app.dependency_overrides[get_historical_dataset_committer] = lambda: committer
    app.dependency_overrides[get_background_job_repository] = lambda: jobs

    try:
        yield connections, datasets, state
    finally:
        app.dependency_overrides.pop(get_market_data_connection_repository, None)
        app.dependency_overrides.pop(get_market_data_provider_catalog, None)
        app.dependency_overrides.pop(get_dataset_repository, None)
        app.dependency_overrides.pop(get_market_data_import_repository, None)
        app.dependency_overrides.pop(get_historical_dataset_committer, None)
        app.dependency_overrides.pop(get_background_job_repository, None)


def request_payload(*, timeframe: str = "1h", end_hours: int = 2) -> dict[str, object]:
    return {
        "name": "BTC historical import",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": timeframe,
        "start_time": START.isoformat(),
        "end_time": (START + timedelta(hours=end_hours)).isoformat(),
    }


def commit_payload(
    *,
    candles: list[OHLCVCandle] | None = None,
    timeframe: str = "1h",
    end_hours: int = 2,
) -> dict[str, object]:
    payload = request_payload(timeframe=timeframe, end_hours=end_hours)
    payload["preview_checksum"] = calculate_dataset_checksum(
        candles if candles is not None else [create_candle(0), create_candle(1)]
    )
    return payload


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
    assert payload["preview_checksum"] == calculate_dataset_checksum(
        [create_candle(0), create_candle(1)]
    )
    assert payload["quality_report"]["issues"] == []
    assert payload["quality_report"]["score"] == {
        "score_version": "quality-score-v1",
        "score_percent": 100.0,
        "coverage_percent": 100.0,
        "integrity_percent": 100.0,
    }
    assert payload["quality_report"]["acceptance"] == {
        "policy_version": "strict-quality-v1",
        "accepted": True,
        "minimum_score_percent": 100.0,
        "blocking_issue_codes": [],
    }
    assert payload["quality_report"]["coverage"] == {
        "requested_start_time": START.isoformat().replace("+00:00", "Z"),
        "requested_end_time": (START + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "expected_first_open_time": START.isoformat().replace("+00:00", "Z"),
        "expected_last_open_time": (START + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "actual_first_open_time": START.isoformat().replace("+00:00", "Z"),
        "actual_last_close_time": (START + timedelta(hours=2) - timedelta(milliseconds=1))
        .isoformat()
        .replace("+00:00", "Z"),
        "expected_candles": 2,
        "received_candles": 2,
        "missing_candles": 0,
        "coverage_percent": 100.0,
        "complete": True,
    }
    assert datasets.count() == 0


def test_import_job_enqueue_is_non_blocking_and_idempotent(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, state = historical_import_dependencies
    state.fail_fetch = True
    url = f"/api/v1/market-data/connections/{CONNECTION_ID}/dataset-jobs"

    first = client.post(url, json=commit_payload())
    duplicate = client.post(url, json=commit_payload())

    assert first.status_code == 202
    assert duplicate.status_code == 202
    assert duplicate.json()["job_id"] == first.json()["job_id"]
    assert first.json()["kind"] == "market_data_import"
    assert first.json()["status"] == "queued"
    assert first.json()["attempt_count"] == 0
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

    first = client.post(url, json=commit_payload())
    second = client.post(url, json=commit_payload())

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
    assert root_record["quality_report"]["score"]["score_percent"] == 100.0
    assert root_record["quality_report"]["acceptance"]["accepted"] is True

    import_id = history_payload["items"][0]["import_id"]
    detail = client.get(f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{import_id}")
    assert detail.status_code == 200
    assert detail.json()["import_id"] == import_id

    dataset_detail = client.get(f"/api/v1/research/datasets/{first.json()['dataset_id']}/summary")
    assert dataset_detail.status_code == 200
    dataset_payload = dataset_detail.json()
    assert dataset_payload["schema_version"] == 3
    assert dataset_payload["provenance"]["kind"] == "market_data_import"
    assert dataset_payload["provenance"]["connection_id"] == CONNECTION_ID
    assert dataset_payload["provenance"]["provider_id"] == "synthetic-public"
    assert dataset_payload["provenance"]["import_id"] == history_payload["items"][-1]["import_id"]
    assert dataset_payload["quality_report"]["candles_checked"] == 2
    assert dataset_payload["quality_report"]["issues"] == []
    assert dataset_payload["quality_report"]["coverage"]["complete"] is True
    assert dataset_payload["quality_report"]["score"]["score_percent"] == 100.0
    assert dataset_payload["quality_report"]["acceptance"]["accepted"] is True


def test_import_requires_preview_checksum(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, _ = historical_import_dependencies

    response = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=request_payload(),
    )

    assert response.status_code == 422
    assert datasets.count() == 0


def test_import_rejects_provider_content_changed_after_preview(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, state = historical_import_dependencies
    preview = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets/preview",
        json=request_payload(),
    )
    assert preview.status_code == 200

    state.candles = [
        create_candle(0),
        create_candle(1).model_copy(update={"close_price": Decimal("106")}),
    ]
    payload = request_payload()
    payload["preview_checksum"] = preview.json()["preview_checksum"]

    imported = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=payload,
    )

    assert imported.status_code == 409
    assert imported.json()["detail"] == (
        "provider data changed after preview; run preview again before importing"
    )
    assert datasets.count() == 0

    history = client.get(f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=failed")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["error_code"] == "preview_mismatch"


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
        json=commit_payload(),
    )
    assert import_response.status_code == 201

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=succeeded"
    )
    root = history_response.json()["items"][0]
    original_snapshot = datasets.get(root["dataset_id"])
    assert original_snapshot is not None

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
    assert payload["quality_report"]["score"]["score_percent"] == 100.0
    assert payload["quality_report"]["acceptance"]["accepted"] is True
    assert datasets.count() == 1
    assert datasets.get(root["dataset_id"]) == original_snapshot

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


def test_refresh_job_enqueue_is_non_blocking_and_idempotent(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, state = historical_import_dependencies
    imported = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=commit_payload(),
    )
    assert imported.status_code == 201
    history = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=succeeded"
    )
    root = history.json()["items"][0]
    state.fail_fetch = True
    url = f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{root['import_id']}/refresh-job"

    first = client.post(url)
    duplicate = client.post(url)

    assert first.status_code == 202
    assert duplicate.status_code == 202
    assert duplicate.json()["job_id"] == first.json()["job_id"]
    assert first.json()["status"] == "queued"
    assert datasets.count() == 1


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
        json=commit_payload(),
    )
    assert imported.status_code == 201

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=succeeded"
    )
    root = history_response.json()["items"][0]
    original_snapshot = datasets.get(root["dataset_id"])
    assert original_snapshot is not None

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
    assert datasets.get(root["dataset_id"]) == original_snapshot

    dataset_detail = client.get(f"/api/v1/research/datasets/{payload['dataset_id']}/summary")
    assert dataset_detail.status_code == 200
    assert dataset_detail.json()["provenance"]["import_id"] == payload["import_id"]
    assert dataset_detail.json()["quality_report"]["score"]["score_percent"] == 100.0
    assert dataset_detail.json()["quality_report"]["acceptance"]["accepted"] is True


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
        json=commit_payload(),
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


def test_refresh_commit_conflict_is_recorded_and_requires_reload(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, datasets, _ = historical_import_dependencies
    imported = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=commit_payload(),
    )
    assert imported.status_code == 201

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=succeeded"
    )
    root = history_response.json()["items"][0]
    app.dependency_overrides[get_historical_dataset_committer] = lambda: (
        ConflictingHistoricalDatasetCommitter()
    )

    conflicted = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports/{root['import_id']}/refresh"
    )

    assert conflicted.status_code == 409
    assert conflicted.json()["detail"] == (
        "dataset refresh lost a concurrency race; reload version history"
    )
    assert datasets.count() == 1

    failed = client.get(f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=failed")
    assert failed.status_code == 200
    assert failed.json()["total"] == 1
    record = failed.json()["items"][0]
    assert record["error_code"] == "refresh_conflict"
    assert record["operation"] == "refresh"
    assert record["version_number"] is None


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
        json=commit_payload(),
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
        json=request_payload(end_hours=3),
    )
    imported = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=commit_payload(candles=state.candles, end_hours=3),
    )

    assert preview.status_code == 200
    assert preview.json()["ready_to_import"] is False
    assert preview.json()["quality_report"]["issues"][0]["code"] == "missing_candle"
    assert preview.json()["quality_report"]["score"]["score_percent"] == 66.67
    assert preview.json()["quality_report"]["acceptance"]["accepted"] is False
    assert imported.status_code == 422
    assert imported.json()["detail"]["issues"][0]["code"] == "missing_candle"
    assert imported.json()["detail"]["score"]["score_percent"] == 66.67
    assert imported.json()["detail"]["acceptance"]["accepted"] is False
    assert datasets.count() == 0

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=failed"
    )
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 1
    assert history_response.json()["items"][0]["error_code"] == "quality_check_failed"
    assert history_response.json()["items"][0]["candle_count"] == 2
    assert history_response.json()["items"][0]["quality_report"]["score"]["score_percent"] == 66.67
    assert history_response.json()["items"][0]["quality_report"]["acceptance"]["accepted"] is False


def test_preview_rejects_silent_head_and_tail_truncation(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, _, state = historical_import_dependencies
    state.candles = [create_candle(1)]

    preview = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets/preview",
        json=request_payload(end_hours=3),
    )

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["ready_to_import"] is False
    assert {issue["code"] for issue in payload["quality_report"]["issues"]} == {
        "incomplete_start",
        "incomplete_end",
    }
    assert payload["quality_report"]["coverage"]["expected_candles"] == 3
    assert payload["quality_report"]["coverage"]["received_candles"] == 1
    assert payload["quality_report"]["coverage"]["missing_candles"] == 2
    assert payload["quality_report"]["coverage"]["coverage_percent"] == 33.33
    assert payload["quality_report"]["coverage"]["complete"] is False


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
        json=commit_payload(),
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


def test_import_redacts_provider_secrets_from_response_and_history(
    historical_import_dependencies: tuple[
        InMemoryMarketDataConnectionRepository,
        InMemoryDatasetRepository,
        ProviderState,
    ],
) -> None:
    _, _, state = historical_import_dependencies
    state.fail_fetch = True
    state.failure_message = "synthetic historical fetch failed; token=history-secret-value"

    response = client.post(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/datasets",
        json=commit_payload(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == ("synthetic historical fetch failed; token=[REDACTED]")
    assert "history-secret-value" not in response.text

    history_response = client.get(
        f"/api/v1/market-data/connections/{CONNECTION_ID}/imports?status=failed"
    )
    assert history_response.status_code == 200
    record = history_response.json()["items"][0]
    assert record["error_code"] == "provider_request_failed"
    assert record["error_message"] == ("synthetic historical fetch failed; token=[REDACTED]")
    assert "history-secret-value" not in history_response.text


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
        json=commit_payload(timeframe="4h"),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == ("timeframe is not supported by connection provider")


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
        json=commit_payload(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "market-data connection not found"
