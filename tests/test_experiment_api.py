from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import get_experiment_registry
from trd_bot.main import app
from trd_bot.research import InMemoryExperimentRegistry

client = TestClient(app)


@pytest.fixture
def registry() -> Iterator[InMemoryExperimentRegistry]:
    experiment_registry = InMemoryExperimentRegistry()

    def override_registry() -> InMemoryExperimentRegistry:
        return experiment_registry

    app.dependency_overrides[get_experiment_registry] = override_registry

    try:
        yield experiment_registry
    finally:
        app.dependency_overrides.pop(
            get_experiment_registry,
            None,
        )


def create_candle_payload(
    *,
    index: int,
    open_price: str,
    close_price: str,
) -> dict[str, object]:
    open_decimal = Decimal(open_price)
    close_decimal = Decimal(close_price)
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
            21,
            20,
            tzinfo=UTC,
        ).isoformat(),
        "open_price": str(open_decimal),
        "high_price": str(max(open_decimal, close_decimal) + Decimal("1")),
        "low_price": str(min(open_decimal, close_decimal) - Decimal("1")),
        "close_price": str(close_decimal),
        "volume": "1000",
        "is_closed": True,
    }


def create_request_payload() -> dict[str, object]:
    prices = [
        ("5", "5"),
        ("4", "4"),
        ("3", "3"),
        ("4", "4"),
        ("6", "6"),
        ("7", "8"),
    ]

    candles = [
        create_candle_payload(
            index=index,
            open_price=open_price,
            close_price=close_price,
        )
        for index, (
            open_price,
            close_price,
        ) in enumerate(prices)
    ]

    return {
        "dataset_name": "Stored API experiment",
        "candles": candles,
        "fast_period": 2,
        "slow_period": 3,
        "horizon_candles": 1,
    }


def test_api_creates_and_stores_experiment(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    assert response.status_code == 200

    data = response.json()
    experiment_id = data["experiment_id"]

    assert experiment_id.startswith("experiment-")
    assert data["result"]["generated_signals"] == 1
    assert registry.get(experiment_id) is not None


def test_api_returns_stored_experiment(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.get(f"/api/v1/research/experiments/{experiment_id}")

    assert response.status_code == 200
    assert response.json()["experiment_id"] == experiment_id


def test_api_returns_404_for_unknown_experiment(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.get("/api/v1/research/experiments/experiment-0000000000000000")

    assert response.status_code == 404
    assert response.json()["detail"] == "experiment not found"


def test_api_lists_experiments_idempotently(
    registry: InMemoryExperimentRegistry,
) -> None:
    payload = create_request_payload()

    first_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=payload,
    )

    second_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    experiment_id = first_response.json()["experiment_id"]

    response = client.get("/api/v1/research/experiments")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert data["count"] == 1
    assert data["has_next"] is False
    assert data["has_previous"] is False

    summary = data["items"][0]

    assert summary["experiment_id"] == experiment_id
    assert summary["generated_signals"] == 1
    assert "result" not in summary


def test_api_paginates_experiment_summaries(
    registry: InMemoryExperimentRegistry,
) -> None:
    for horizon_candles in (1, 2, 3):
        payload = create_request_payload()
        payload["horizon_candles"] = horizon_candles

        create_response = client.post(
            "/api/v1/research/experiments/ema-crossover",
            json=payload,
        )

        assert create_response.status_code == 200

    response = client.get(
        "/api/v1/research/experiments",
        params={
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert data["count"] == 2
    assert data["has_next"] is False
    assert data["has_previous"] is True
    assert len(data["items"]) == 2
    assert all("result" not in item for item in data["items"])


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ],
)
def test_api_rejects_invalid_experiment_pagination(
    registry: InMemoryExperimentRegistry,
    params: dict[str, int],
) -> None:
    response = client.get(
        "/api/v1/research/experiments",
        params=params,
    )

    assert response.status_code == 422
