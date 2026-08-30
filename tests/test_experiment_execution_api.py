from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_experiment_execution_repository,
    get_experiment_execution_task,
)
from trd_bot.main import app
from trd_bot.research import (
    InMemoryDatasetRepository,
    InMemoryExperimentExecutionRepository,
)

client = TestClient(app)


@pytest.fixture
def execution_repository() -> InMemoryExperimentExecutionRepository:
    return InMemoryExperimentExecutionRepository()


@pytest.fixture
def execution_task_calls() -> list[str]:
    return []


@pytest.fixture(autouse=True)
def override_repositories(
    execution_repository: InMemoryExperimentExecutionRepository,
    execution_task_calls: list[str],
) -> Iterator[None]:
    dataset_repository = InMemoryDatasetRepository()

    def record_execution_task(execution_id: str) -> None:
        execution_task_calls.append(execution_id)

    previous_overrides = app.dependency_overrides.copy()

    app.dependency_overrides[get_dataset_repository] = lambda: dataset_repository

    app.dependency_overrides[get_experiment_execution_repository] = lambda: execution_repository

    app.dependency_overrides[get_experiment_execution_task] = lambda: record_execution_task

    yield

    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def build_dataset_payload() -> dict[str, object]:
    start_time = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[dict[str, object]] = []

    for index in range(30):
        open_time = start_time + timedelta(hours=index)
        close_time = open_time + timedelta(hours=1) - timedelta(milliseconds=1)
        close_price = 100 + index

        candles.append(
            {
                "open_time": open_time.isoformat(),
                "close_time": close_time.isoformat(),
                "open_price": str(close_price - 1),
                "high_price": str(close_price + 1),
                "low_price": str(close_price - 2),
                "close_price": str(close_price),
                "volume": str(1000 + index),
                "is_closed": True,
            }
        )

    return {
        "name": "Execution test dataset",
        "source": "test-csv",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": "1h",
        "candles": candles,
    }


def create_dataset() -> str:
    response = client.post(
        "/api/v1/research/datasets",
        json=build_dataset_payload(),
    )

    assert response.status_code == 201

    dataset_id = response.json()["dataset_id"]

    assert isinstance(dataset_id, str)

    return dataset_id


def build_execution_payload(
    dataset_id: str,
) -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "fast_period": 9,
        "slow_period": 21,
        "horizon_candles": 1,
        "starting_balance": "10000",
        "allocation_fraction": "0.10",
        "fee_rate": "0.001",
        "slippage_rate": "0.0005",
    }


def build_rsi_execution_payload(
    dataset_id: str,
) -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "period": 14,
        "oversold_threshold": "30",
        "overbought_threshold": "70",
        "horizon_candles": 1,
        "starting_balance": "10000",
        "allocation_fraction": "0.10",
        "fee_rate": "0.001",
        "slippage_rate": "0.0005",
    }


def test_creates_queued_experiment_execution(
    execution_repository: InMemoryExperimentExecutionRepository,
    execution_task_calls: list[str],
) -> None:
    dataset_id = create_dataset()

    response = client.post(
        "/api/v1/research/experiment-executions/ema-crossover",
        json=build_execution_payload(dataset_id),
    )

    assert response.status_code == 202

    body = response.json()

    assert body["status"] == "queued"
    assert body["progress_percent"] == 0
    assert body["dataset_id"] == dataset_id
    assert body["strategy_name"] == "ema-crossover"
    assert body["experiment_id"] is None
    assert body["error_code"] is None
    assert body["error_message"] is None

    stored = execution_repository.get(body["execution_id"])

    assert stored is not None
    assert stored.status.value == "queued"
    assert execution_task_calls == [body["execution_id"]]


def test_creates_queued_rsi_experiment_execution(
    execution_repository: InMemoryExperimentExecutionRepository,
    execution_task_calls: list[str],
) -> None:
    dataset_id = create_dataset()

    response = client.post(
        "/api/v1/research/experiment-executions/rsi-threshold",
        json=build_rsi_execution_payload(dataset_id),
    )

    assert response.status_code == 202

    body = response.json()

    assert body["strategy_name"] == "rsi-threshold"
    assert body["strategy_version"] == "1.0.0"
    assert body["parameters"]["period"] == 14
    assert body["parameters"]["oversold_threshold"] == "30"
    assert body["parameters"]["overbought_threshold"] == "70"

    stored = execution_repository.get(body["execution_id"])

    assert stored is not None
    assert stored.strategy_name == "rsi-threshold"
    assert execution_task_calls == [body["execution_id"]]


def test_returns_experiment_execution() -> None:
    dataset_id = create_dataset()

    create_response = client.post(
        "/api/v1/research/experiment-executions/ema-crossover",
        json=build_execution_payload(dataset_id),
    )

    execution_id = create_response.json()["execution_id"]

    response = client.get(f"/api/v1/research/experiment-executions/{execution_id}")

    assert response.status_code == 200
    assert response.json()["execution_id"] == execution_id


def test_lists_experiment_executions() -> None:
    dataset_id = create_dataset()

    client.post(
        "/api/v1/research/experiment-executions/ema-crossover",
        json=build_execution_payload(dataset_id),
    )

    response = client.get(
        "/api/v1/research/experiment-executions",
        params={
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["count"] == 1
    assert body["limit"] == 10
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "queued"


def test_returns_not_found_for_unknown_execution() -> None:
    response = client.get("/api/v1/research/experiment-executions/execution-0000000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "experiment execution not found"}


def test_rejects_unknown_dataset(
    execution_task_calls: list[str],
) -> None:
    response = client.post(
        "/api/v1/research/experiment-executions/ema-crossover",
        json=build_execution_payload(
            "dataset-0000000000000000",
        ),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "dataset not found"}

    assert execution_task_calls == []


def test_rejects_invalid_period_relationship(
    execution_task_calls: list[str],
) -> None:
    dataset_id = create_dataset()
    payload = build_execution_payload(dataset_id)

    payload["fast_period"] = 30
    payload["slow_period"] = 20

    response = client.post(
        "/api/v1/research/experiment-executions/ema-crossover",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid EMA execution parameters"}

    assert execution_task_calls == []
