from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_walk_forward_run_registry,
)
from trd_bot.main import app
from trd_bot.research import InMemoryDatasetRepository, InMemoryWalkForwardRunRegistry

client = TestClient(app)


@pytest.fixture
def registry() -> Iterator[InMemoryWalkForwardRunRegistry]:
    dataset_repository = InMemoryDatasetRepository()
    run_registry = InMemoryWalkForwardRunRegistry()

    def override_registry() -> InMemoryWalkForwardRunRegistry:
        return run_registry

    def override_datasets() -> InMemoryDatasetRepository:
        return dataset_repository

    app.dependency_overrides[get_walk_forward_run_registry] = override_registry
    app.dependency_overrides[get_dataset_repository] = override_datasets
    try:
        yield run_registry
    finally:
        app.dependency_overrides.pop(get_walk_forward_run_registry, None)
        app.dependency_overrides.pop(get_dataset_repository, None)


def create_candle_payload(index: int) -> dict[str, object]:
    prices = ("5", "4", "3", "4", "6", "5", "3", "4", "6", "8")
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
        "open_time": datetime(2026, 8, 21, hour, tzinfo=UTC).isoformat(),
        "close_time": datetime(2026, 8, 21, hour + 1, tzinfo=UTC).isoformat(),
        "received_at": datetime(2026, 8, 22, 10, tzinfo=UTC).isoformat(),
        "open_price": str(price),
        "high_price": str(price + Decimal("1")),
        "low_price": str(price - Decimal("1")),
        "close_price": str(price),
        "volume": "1000",
        "is_closed": True,
    }


def create_request_payload(
    *,
    fast_period: int = 2,
    slow_period: int = 3,
) -> dict[str, object]:
    return {
        "dataset_name": "Stored API walk-forward run",
        "candles": [create_candle_payload(index) for index in range(10)],
        "fast_period": fast_period,
        "slow_period": slow_period,
        "horizon_candles": 1,
        "train_candles": 4,
        "test_candles": 2,
        "step_candles": 2,
        "gap_candles": 0,
        "mode": "rolling",
    }


def create_run(payload: dict[str, object]) -> dict[str, object]:
    response = client.post(
        "/api/v1/research/walk-forward/runs/ema-crossover",
        json=payload,
    )
    assert response.status_code == 200
    data: dict[str, object] = response.json()
    return data


def test_api_creates_and_stores_walk_forward_run(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    data = create_run(create_request_payload())
    execution_id = data["execution_id"]

    assert isinstance(execution_id, str)
    assert execution_id.startswith("walk-forward-execution-")
    assert data["walk_forward_config"] == {
        "train_candles": 4,
        "test_candles": 2,
        "step_candles": 2,
        "gap_candles": 0,
        "mode": "rolling",
    }
    result = data["result"]
    assert isinstance(result, dict)
    assert result["strategy_parameters"] == [
        {"name": "fast_period", "value": "2"},
        {"name": "slow_period", "value": "3"},
    ]
    assert registry.get(execution_id) is not None


def test_api_saves_identical_run_idempotently(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    payload = create_request_payload()
    first = create_run(payload)
    second = create_run(payload)

    assert first["execution_id"] == second["execution_id"]
    assert registry.count() == 1


def test_api_distinguishes_different_ema_parameters(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    first = create_run(create_request_payload(fast_period=2, slow_period=3))
    second = create_run(create_request_payload(fast_period=3, slow_period=4))

    assert first["execution_id"] != second["execution_id"]
    assert registry.count() == 2


def test_api_returns_stored_walk_forward_run(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    created = create_run(create_request_payload())

    response = client.get(f"/api/v1/research/walk-forward/runs/{created['execution_id']}")

    assert response.status_code == 200
    assert response.json()["execution_id"] == created["execution_id"]


def test_api_returns_404_for_unknown_walk_forward_run(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    response = client.get(
        "/api/v1/research/walk-forward/runs/walk-forward-execution-0000000000000000"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "walk-forward run not found"


def test_api_returns_walk_forward_stability_report(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    created = create_run(create_request_payload())

    execution_id = created["execution_id"]

    assert isinstance(execution_id, str)

    response = client.get(f"/api/v1/research/walk-forward/runs/{execution_id}/stability")

    assert response.status_code == 200

    data = response.json()

    assert data["execution_id"] == execution_id
    assert data["total_folds"] == 3
    assert len(data["folds"]) == 3

    assert "strategy_return_mean_absolute_deviation" in data

    assert data["interpretation"] == "historical_research_only"


def test_api_returns_404_for_unknown_walk_forward_stability_report(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    response = client.get(
        "/api/v1/research/walk-forward/runs/walk-forward-execution-0000000000000000/stability"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == ("walk-forward run not found")


def test_api_lists_paginated_walk_forward_summaries(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    create_run(create_request_payload(fast_period=2, slow_period=3))
    create_run(create_request_payload(fast_period=3, slow_period=4))
    create_run(create_request_payload(fast_period=4, slow_period=5))

    response = client.get(
        "/api/v1/research/walk-forward/runs",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["count"] == 2
    assert data["has_previous"] is True
    assert data["has_next"] is False
    assert all("result" not in item for item in data["items"])
    assert all("fold_results" not in item for item in data["items"])
    assert all("average_excess_return" in item for item in data["items"])


def test_api_filters_walk_forward_run_catalog(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    for horizon_candles in (1, 2, 3):
        payload = create_request_payload()
        payload["horizon_candles"] = horizon_candles

        create_run(payload)

    response = client.get(
        "/api/v1/research/walk-forward/runs",
        params={
            "strategy_name": "ema-crossover",
            "strategy_version": "1.0.0",
            "horizon_candles": 2,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["count"] == 1
    assert data["items"][0]["horizon_candles"] == 2


def test_api_sorts_walk_forward_run_catalog_by_horizon_descending(
    registry: InMemoryWalkForwardRunRegistry,
) -> None:
    for horizon_candles in (1, 2, 3):
        payload = create_request_payload()
        payload["horizon_candles"] = horizon_candles

        create_run(payload)

    response = client.get(
        "/api/v1/research/walk-forward/runs",
        params={
            "sort_by": "horizon_candles",
            "sort_direction": "desc",
        },
    )

    assert response.status_code == 200

    assert [item["horizon_candles"] for item in response.json()["items"]] == [
        3,
        2,
        1,
    ]


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}],
)
def test_api_rejects_invalid_walk_forward_pagination(
    registry: InMemoryWalkForwardRunRegistry,
    params: dict[str, int],
) -> None:
    response = client.get(
        "/api/v1/research/walk-forward/runs",
        params=params,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"horizon_candles": 0},
        {"sort_by": "unsupported"},
        {"sort_direction": "sideways"},
        {"plan_id": " "},
    ],
)
def test_api_rejects_invalid_walk_forward_catalog_query(
    registry: InMemoryWalkForwardRunRegistry,
    params: dict[str, int | str],
) -> None:
    response = client.get(
        "/api/v1/research/walk-forward/runs",
        params=params,
    )

    assert response.status_code == 422
