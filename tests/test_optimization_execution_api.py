from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_optimization_execution_enqueuer,
    get_optimization_execution_repository,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.main import app
from trd_bot.research.datasets import DatasetBuilder, InMemoryDatasetRepository
from trd_bot.research.optimization_executions import (
    InMemoryOptimizationExecutionRepository,
)
from trd_bot.research.optimization_jobs import InMemoryOptimizationExecutionEnqueuer

client = TestClient(app)


@pytest.fixture
def dataset_repository() -> InMemoryDatasetRepository:
    repository = InMemoryDatasetRepository()
    start = datetime(2026, 9, 1, tzinfo=UTC)
    candles = tuple(
        OHLCVCandle(
            source="test-exchange",
            pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
            timeframe=Timeframe.HOUR_1,
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
            received_at=start,
            open_price=Decimal(100 + index),
            high_price=Decimal(102 + index),
            low_price=Decimal(99 + index),
            close_price=Decimal(101 + index),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index in range(4)
    )
    repository.save(DatasetBuilder().build(name="Optimization API dataset", candles=candles))
    return repository


@pytest.fixture
def execution_repository() -> InMemoryOptimizationExecutionRepository:
    return InMemoryOptimizationExecutionRepository()


@pytest.fixture(autouse=True)
def override_repositories(
    dataset_repository: InMemoryDatasetRepository,
    execution_repository: InMemoryOptimizationExecutionRepository,
) -> Iterator[None]:
    previous_overrides = app.dependency_overrides.copy()
    enqueuer = InMemoryOptimizationExecutionEnqueuer(execution_repository)
    app.dependency_overrides[get_dataset_repository] = lambda: dataset_repository
    app.dependency_overrides[get_optimization_execution_enqueuer] = lambda: enqueuer
    app.dependency_overrides[get_optimization_execution_repository] = lambda: execution_repository

    yield

    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def build_request(dataset_id: str) -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "strategy_name": "ema-crossover",
        "strategy_version": "1.0.0",
        "objective": "excess_return",
        "parameter_grid": [
            {"name": "fast_period", "values": ["9", "21"]},
            {"name": "slow_period", "values": ["10", "20"]},
        ],
        "horizon_candles": 1,
        "backtest_config": {
            "starting_balance": "10000",
            "allocation_fraction": "0.10",
            "fee_rate": "0.001",
            "slippage_rate": "0.0005",
        },
    }


def stored_dataset_id(repository: InMemoryDatasetRepository) -> str:
    return repository.list_page(limit=1, offset=0)[0].dataset_id


def test_creates_a_server_built_bounded_optimization_execution(
    dataset_repository: InMemoryDatasetRepository,
    execution_repository: InMemoryOptimizationExecutionRepository,
) -> None:
    dataset_id = stored_dataset_id(dataset_repository)

    response = client.post(
        "/api/v1/research/optimization-executions",
        json=build_request(dataset_id),
    )

    assert response.status_code == 202
    body = response.json()
    execution = body["execution"]
    assert body["created"] is True
    assert body["job"]["kind"] == "optimization_execution"
    assert body["job"]["status"] == "queued"
    assert execution["status"] == "queued"
    assert execution["dataset_id"] == dataset_id
    assert execution["strategy_name"] == "ema-crossover"
    assert execution["objective"] == "excess_return"
    assert execution["plan"]["requested_combinations"] == 4
    assert execution["plan"]["skipped_combinations"] == 2
    assert execution["plan"]["total_trials"] == 2
    assert execution["completed_trials"] == 0
    assert execution["experiment_ids"] == []

    stored = execution_repository.get(execution["execution_id"])
    assert stored is not None
    assert stored.plan.total_trials == 2


def test_lists_and_returns_persisted_optimization_executions(
    dataset_repository: InMemoryDatasetRepository,
) -> None:
    dataset_id = stored_dataset_id(dataset_repository)
    submission = client.post(
        "/api/v1/research/optimization-executions",
        json=build_request(dataset_id),
    ).json()
    created = submission["execution"]

    page_response = client.get(
        "/api/v1/research/optimization-executions",
        params={"limit": 1, "offset": 0},
    )
    detail_response = client.get(
        f"/api/v1/research/optimization-executions/{created['execution_id']}",
    )

    assert page_response.status_code == 200
    assert page_response.json()["total"] == 1
    assert page_response.json()["items"] == [created]
    assert detail_response.status_code == 200
    assert detail_response.json() == created


def test_duplicate_submission_returns_the_existing_execution_and_job(
    dataset_repository: InMemoryDatasetRepository,
    execution_repository: InMemoryOptimizationExecutionRepository,
) -> None:
    request = build_request(stored_dataset_id(dataset_repository))

    first = client.post(
        "/api/v1/research/optimization-executions",
        json=request,
    ).json()
    duplicate = client.post(
        "/api/v1/research/optimization-executions",
        json=request,
    ).json()

    assert first["created"] is True
    assert duplicate["created"] is False
    assert duplicate["execution"]["execution_id"] == first["execution"]["execution_id"]
    assert duplicate["job"]["job_id"] == first["job"]["job_id"]
    assert execution_repository.count() == 1


def test_rejects_an_unknown_dataset_without_persisting_execution(
    execution_repository: InMemoryOptimizationExecutionRepository,
) -> None:
    response = client.post(
        "/api/v1/research/optimization-executions",
        json=build_request("dataset-0000000000000000"),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "dataset_not_found",
        "message": "dataset not found",
    }
    assert execution_repository.count() == 0


def test_rejects_an_oversized_grid_with_a_stable_error_code(
    dataset_repository: InMemoryDatasetRepository,
    execution_repository: InMemoryOptimizationExecutionRepository,
) -> None:
    request = build_request(stored_dataset_id(dataset_repository))
    request["parameter_grid"] = [
        {"name": "fast_period", "values": [str(value) for value in range(2, 22)]},
        {"name": "slow_period", "values": [str(value) for value in range(22, 42)]},
    ]

    response = client.post(
        "/api/v1/research/optimization-executions",
        json=request,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_optimization_plan"
    assert "maximum of 100 trials" in response.json()["detail"]["message"]
    assert execution_repository.count() == 0


def test_client_cannot_supply_optimization_lifecycle_state(
    dataset_repository: InMemoryDatasetRepository,
) -> None:
    request = build_request(stored_dataset_id(dataset_repository))
    request["status"] = "succeeded"
    request["best_experiment_id"] = "experiment-0000000000000001"

    response = client.post(
        "/api/v1/research/optimization-executions",
        json=request,
    )

    assert response.status_code == 422


def test_returns_404_for_an_unknown_optimization_execution() -> None:
    response = client.get(
        "/api/v1/research/optimization-executions/optimization-0000000000000000",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "optimization_execution_not_found",
        "message": "optimization execution not found",
    }
