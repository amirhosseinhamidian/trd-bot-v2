from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_acceptance_policy_preset_catalog,
    get_dataset_repository,
    get_experiment_registry,
    get_walk_forward_run_registry,
)
from trd_bot.main import app
from trd_bot.research import (
    AcceptancePolicyPresetCatalog,
    InMemoryDatasetRepository,
    InMemoryExperimentRegistry,
    InMemoryWalkForwardRunRegistry,
)

RepositorySet = tuple[
    InMemoryDatasetRepository,
    InMemoryExperimentRegistry,
    InMemoryWalkForwardRunRegistry,
    AcceptancePolicyPresetCatalog,
]

client = TestClient(app)


@pytest.fixture
def repositories() -> Iterator[RepositorySet]:
    datasets = InMemoryDatasetRepository()
    experiments = InMemoryExperimentRegistry()

    walk_forward_runs = InMemoryWalkForwardRunRegistry()

    policy_presets = AcceptancePolicyPresetCatalog()

    app.dependency_overrides[get_dataset_repository] = lambda: datasets

    app.dependency_overrides[get_experiment_registry] = lambda: experiments

    app.dependency_overrides[get_walk_forward_run_registry] = lambda: walk_forward_runs

    app.dependency_overrides[get_acceptance_policy_preset_catalog] = lambda: policy_presets

    try:
        yield (
            datasets,
            experiments,
            walk_forward_runs,
            policy_presets,
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
        app.dependency_overrides.pop(
            get_acceptance_policy_preset_catalog,
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
        "acceptance_policy_preset_count": 3,
        "research_stage": "empty",
        "acceptance_policy_presets": [
            {
                "preset_id": "baseline-v1",
                "name": "baseline",
                "version": 1,
                "description": ("Example baseline thresholds for historical research."),
                "policy": {
                    "minimum_total_trades": 20,
                    "minimum_excess_return": "0",
                    "maximum_drawdown_fraction": ("0.20"),
                },
                "interpretation": ("historical_research_only"),
            },
            {
                "preset_id": ("drawdown-focused-v1"),
                "name": "drawdown-focused",
                "version": 1,
                "description": ("Example policy using a tighter historical drawdown threshold."),
                "policy": {
                    "minimum_total_trades": 20,
                    "minimum_excess_return": "0",
                    "maximum_drawdown_fraction": ("0.10"),
                },
                "interpretation": ("historical_research_only"),
            },
            {
                "preset_id": "larger-sample-v1",
                "name": "larger-sample",
                "version": 1,
                "description": ("Example policy requiring a larger historical trade sample."),
                "policy": {
                    "minimum_total_trades": 50,
                    "minimum_excess_return": "0",
                    "maximum_drawdown_fraction": ("0.20"),
                },
                "interpretation": ("historical_research_only"),
            },
        ],
        "latest_dataset": None,
        "latest_experiment": None,
        "latest_walk_forward_run": None,
    }


def test_api_returns_compact_persisted_research_overview(
    repositories: RepositorySet,
) -> None:
    payload = create_research_payload()

    experiment_response = client.post(
        ("/api/v1/research/experiments/ema-crossover"),
        json=payload,
    )

    walk_forward_response = client.post(
        ("/api/v1/research/walk-forward/runs/ema-crossover"),
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

    assert data["acceptance_policy_preset_count"] == 3

    assert data["research_stage"] == "walk_forward_available"

    assert [preset["preset_id"] for preset in data["acceptance_policy_presets"]] == [
        "baseline-v1",
        "drawdown-focused-v1",
        "larger-sample-v1",
    ]

    assert data["latest_experiment"]["experiment_id"] == experiment_response.json()["experiment_id"]

    assert (
        data["latest_walk_forward_run"]["execution_id"]
        == walk_forward_response.json()["execution_id"]
    )

    assert "candles" not in data["latest_dataset"]

    assert "result" not in data["latest_experiment"]

    assert "result" not in data["latest_walk_forward_run"]


def test_api_reports_experiment_stage_before_walk_forward(
    repositories: RepositorySet,
) -> None:
    response = client.post(
        ("/api/v1/research/experiments/ema-crossover"),
        json=create_research_payload(),
    )

    assert response.status_code == 200

    overview_response = client.get("/api/v1/research/overview")

    assert overview_response.status_code == 200

    data = overview_response.json()

    assert data["dataset_count"] == 1
    assert data["experiment_count"] == 1
    assert data["walk_forward_run_count"] == 0

    assert data["research_stage"] == "experiments_available"


def test_api_returns_empty_research_activity_feed(
    repositories: RepositorySet,
) -> None:
    response = client.get("/api/v1/research/overview/activity")

    assert response.status_code == 200

    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
        "count": 0,
        "has_next": False,
        "has_previous": False,
    }


def test_api_returns_newest_first_research_activity(
    repositories: RepositorySet,
) -> None:
    payload = create_research_payload()

    experiment_response = client.post(
        ("/api/v1/research/experiments/ema-crossover"),
        json=payload,
    )

    run_response = client.post(
        ("/api/v1/research/walk-forward/runs/ema-crossover"),
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
    assert run_response.status_code == 200

    response = client.get("/api/v1/research/overview/activity")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["count"] == 3

    assert [item["activity_type"] for item in data["items"]] == [
        "walk_forward_run",
        "experiment",
        "dataset",
    ]

    assert "result" not in data["items"][0]
    assert "candles" not in data["items"][2]


def test_api_paginates_research_activity(
    repositories: RepositorySet,
) -> None:
    payload = create_research_payload()

    experiment_response = client.post(
        ("/api/v1/research/experiments/ema-crossover"),
        json=payload,
    )

    run_response = client.post(
        ("/api/v1/research/walk-forward/runs/ema-crossover"),
        json={
            **payload,
            "train_candles": 4,
            "test_candles": 2,
            "step_candles": 2,
        },
    )

    assert experiment_response.status_code == 200
    assert run_response.status_code == 200

    response = client.get(
        "/api/v1/research/overview/activity",
        params={
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["count"] == 1

    assert data["items"][0]["activity_type"] == "experiment"

    assert data["has_next"] is True
    assert data["has_previous"] is True


@pytest.mark.parametrize(
    (
        "activity_type",
        "expected_resource_type",
    ),
    [
        (
            "dataset",
            "dataset",
        ),
        (
            "experiment",
            "experiment",
        ),
        (
            "walk_forward_run",
            "walk_forward_run",
        ),
    ],
)
def test_api_filters_research_activity_by_type(
    repositories: RepositorySet,
    activity_type: str,
    expected_resource_type: str,
) -> None:
    payload = create_research_payload()

    experiment_response = client.post(
        ("/api/v1/research/experiments/ema-crossover"),
        json=payload,
    )

    run_response = client.post(
        ("/api/v1/research/walk-forward/runs/ema-crossover"),
        json={
            **payload,
            "train_candles": 4,
            "test_candles": 2,
            "step_candles": 2,
        },
    )

    assert experiment_response.status_code == 200
    assert run_response.status_code == 200

    response = client.get(
        ("/api/v1/research/overview/activity"),
        params={
            "activity_type": activity_type,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["count"] == 1

    assert data["items"][0]["activity_type"] == expected_resource_type


def test_api_rejects_unknown_research_activity_type(
    repositories: RepositorySet,
) -> None:
    response = client.get(
        ("/api/v1/research/overview/activity"),
        params={
            "activity_type": "unknown",
        },
    )

    assert response.status_code == 422


def test_api_filters_research_activity_by_time_range(
    repositories: RepositorySet,
) -> None:
    from_time = datetime.now(UTC) - timedelta(seconds=1)
    payload = create_research_payload()

    experiment_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=payload,
    )
    run_response = client.post(
        "/api/v1/research/walk-forward/runs/ema-crossover",
        json={
            **payload,
            "train_candles": 4,
            "test_candles": 2,
            "step_candles": 2,
        },
    )
    to_time = datetime.now(UTC) + timedelta(seconds=1)

    assert experiment_response.status_code == 200
    assert run_response.status_code == 200

    response = client.get(
        "/api/v1/research/overview/activity",
        params={
            "from_time": from_time.isoformat(),
            "to_time": to_time.isoformat(),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert [item["activity_type"] for item in data["items"]] == [
        "walk_forward_run",
        "experiment",
        "dataset",
    ]


def test_api_returns_empty_activity_for_future_time_range(
    repositories: RepositorySet,
) -> None:
    response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_research_payload(),
    )
    assert response.status_code == 200

    future = datetime.now(UTC) + timedelta(days=1)

    activity_response = client.get(
        "/api/v1/research/overview/activity",
        params={"from_time": future.isoformat()},
    )

    assert activity_response.status_code == 200
    assert activity_response.json()["total"] == 0
    assert activity_response.json()["items"] == []


def test_api_combines_activity_type_and_time_filters(
    repositories: RepositorySet,
) -> None:
    from_time = datetime.now(UTC) - timedelta(seconds=1)

    response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_research_payload(),
    )
    assert response.status_code == 200

    activity_response = client.get(
        "/api/v1/research/overview/activity",
        params={
            "activity_type": "experiment",
            "from_time": from_time.isoformat(),
        },
    )

    assert activity_response.status_code == 200
    data = activity_response.json()
    assert data["total"] == 1
    assert data["items"][0]["activity_type"] == "experiment"


def test_api_rejects_reversed_activity_time_range(
    repositories: RepositorySet,
) -> None:
    response = client.get(
        "/api/v1/research/overview/activity",
        params={
            "from_time": "2026-08-23T10:00:00Z",
            "to_time": "2026-08-22T10:00:00Z",
        },
    )

    assert response.status_code == 422
