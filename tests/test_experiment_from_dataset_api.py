from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_experiment_registry,
)
from trd_bot.main import app
from trd_bot.research import (
    InMemoryDatasetRepository,
)
from trd_bot.research.experiments import InMemoryExperimentRegistry

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_repositories() -> Iterator[None]:
    dataset_repository = InMemoryDatasetRepository()
    experiment_registry = InMemoryExperimentRegistry()

    previous_overrides = app.dependency_overrides.copy()

    app.dependency_overrides[get_dataset_repository] = lambda: dataset_repository
    app.dependency_overrides[get_experiment_registry] = lambda: experiment_registry

    yield

    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def build_dataset_payload() -> dict[str, object]:
    start_time = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[dict[str, object]] = []

    for index in range(60):
        candle_open_time = start_time + timedelta(hours=index)
        candle_close_time = candle_open_time + timedelta(hours=1) - timedelta(milliseconds=1)

        close_price = 200 - index if index < 30 else 170 + (index - 30) * 2

        open_price = close_price - 0.5
        high_price = max(open_price, close_price) + 1
        low_price = min(open_price, close_price) - 1

        candles.append(
            {
                "open_time": candle_open_time.isoformat(),
                "close_time": candle_close_time.isoformat(),
                "open_price": str(open_price),
                "high_price": str(high_price),
                "low_price": str(low_price),
                "close_price": str(close_price),
                "volume": str(1000 + index),
                "is_closed": True,
            }
        )

    return {
        "name": "Stored BTC historical dataset",
        "source": "test-csv",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": "1h",
        "candles": candles,
    }


def create_stored_dataset() -> str:
    response = client.post(
        "/api/v1/research/datasets",
        json=build_dataset_payload(),
    )

    assert response.status_code == 201

    dataset_id = response.json()["dataset_id"]

    assert isinstance(dataset_id, str)

    return dataset_id


def build_experiment_payload(dataset_id: str) -> dict[str, object]:
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


def test_creates_experiment_from_stored_dataset() -> None:
    dataset_id = create_stored_dataset()

    response = client.post(
        "/api/v1/research/experiments/ema-crossover/from-dataset",
        json=build_experiment_payload(dataset_id),
    )

    assert response.status_code == 200

    body = response.json()

    assert isinstance(body["experiment_id"], str)

    list_response = client.get(
        "/api/v1/research/experiments",
        params={
            "dataset_id": dataset_id,
            "limit": 10,
            "offset": 0,
        },
    )

    assert list_response.status_code == 200

    page = list_response.json()

    assert page["total"] == 1
    assert page["count"] == 1
    assert page["items"][0]["experiment_id"] == body["experiment_id"]
    assert page["items"][0]["dataset_id"] == dataset_id
    assert page["items"][0]["strategy_name"] == "ema-crossover"


def test_returns_not_found_for_unknown_dataset() -> None:
    response = client.post(
        "/api/v1/research/experiments/ema-crossover/from-dataset",
        json=build_experiment_payload("dataset-does-not-exist"),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "dataset not found",
    }


def test_rejects_invalid_ema_period_relationship() -> None:
    dataset_id = create_stored_dataset()
    payload = build_experiment_payload(dataset_id)

    payload["fast_period"] = 21
    payload["slow_period"] = 21

    response = client.post(
        "/api/v1/research/experiments/ema-crossover/from-dataset",
        json=payload,
    )

    assert response.status_code == 422
