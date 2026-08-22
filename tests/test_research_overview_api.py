from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_experiment_registry,
    get_walk_forward_run_registry,
)
from trd_bot.main import app
from trd_bot.research import (
    InMemoryDatasetRepository,
    InMemoryExperimentRegistry,
    InMemoryWalkForwardRunRegistry,
)

RepositorySet = tuple[
    InMemoryDatasetRepository,
    InMemoryExperimentRegistry,
    InMemoryWalkForwardRunRegistry,
]

client = TestClient(app)


@pytest.fixture
def repositories() -> Iterator[RepositorySet]:
    datasets = InMemoryDatasetRepository()
    experiments = InMemoryExperimentRegistry()
    walk_forward_runs = InMemoryWalkForwardRunRegistry()

    app.dependency_overrides[get_dataset_repository] = lambda: datasets

    app.dependency_overrides[get_experiment_registry] = lambda: experiments

    app.dependency_overrides[get_walk_forward_run_registry] = lambda: walk_forward_runs

    try:
        yield (
            datasets,
            experiments,
            walk_forward_runs,
        )
    finally:
        app.dependency_overrides.pop(
            get_dataset_repository,
            None,
        )

        app.dependency_overrides.pop(
            get_experiment_registry,
            None,
        )

        app.dependency_overrides.pop(
            get_walk_forward_run_registry,
            None,
        )


def create_candle_payload(
    index: int,
) -> dict[str, object]:
    prices = (
        "5",
        "4",
        "3",
        "4",
        "6",
        "5",
        "3",
        "4",
        "6",
        "8",
    )

    price = Decimal(prices[index])
    hour = 10 + index

    return {
        "source": "test-exchange",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": "1h",
        "open_time": datetime(
            2026,
            8,
            21,
            hour,
            tzinfo=UTC,
        ).isoformat(),
        "close_time": datetime(
            2026,
            8,
            21,
            hour + 1,
            tzinfo=UTC,
        ).isoformat(),
        "received_at": datetime(
            2026,
            8,
            22,
            10,
            tzinfo=UTC,
        ).isoformat(),
        "open_price": str(price),
        "high_price": str(price + Decimal("1")),
        "low_price": str(price - Decimal("1")),
        "close_price": str(price),
        "volume": "1000",
        "is_closed": True,
    }


def create_research_payload() -> dict[str, object]:
    return {
        "dataset_name": "Overview dataset",
        "candles": [create_candle_payload(index) for index in range(10)],
        "fast_period": 2,
        "slow_period": 3,
        "horizon_candles": 1,
    }


def test_api_returns_empty_research_overview(
    repositories: RepositorySet,
) -> None:
    response = client.get("/api/v1/research/overview")

    assert response.status_code == 200

    assert response.json() == {
        "dataset_count": 0,
        "experiment_count": 0,
        "walk_forward_run_count": 0,
        "latest_dataset": None,
        "latest_experiment": None,
        "latest_walk_forward_run": None,
    }


def test_api_returns_compact_persisted_research_overview(
    repositories: RepositorySet,
) -> None:
    payload = create_research_payload()

    experiment_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=payload,
    )

    walk_forward_response = client.post(
        "/api/v1/research/walk-forward/runs/ema-crossover",
        json={
            **payload,
            "train_candles": 4,
            "test_candles": 2,
            "step_candles": 2,
            "gap_candles": 0,
            "mode": "rolling",
        },
    )

    assert experiment_response.status_code == 200
    assert walk_forward_response.status_code == 200

    response = client.get("/api/v1/research/overview")

    assert response.status_code == 200

    data = response.json()

    assert data["dataset_count"] == 1
    assert data["experiment_count"] == 1
    assert data["walk_forward_run_count"] == 1

    assert data["latest_experiment"]["experiment_id"] == experiment_response.json()["experiment_id"]

    assert (
        data["latest_walk_forward_run"]["execution_id"]
        == walk_forward_response.json()["execution_id"]
    )

    assert "candles" not in data["latest_dataset"]
    assert "result" not in data["latest_experiment"]
    assert "result" not in data["latest_walk_forward_run"]
