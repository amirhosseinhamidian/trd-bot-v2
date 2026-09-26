import csv
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_acceptance_policy_preset_catalog,
    get_dataset_repository,
    get_experiment_registry,
)
from trd_bot.main import app
from trd_bot.research import (
    AcceptancePolicyPresetCatalog,
    ExperimentPerformanceSeriesBuilder,
    InMemoryDatasetRepository,
    InMemoryExperimentRegistry,
)

client = TestClient(app)


@pytest.fixture
def registry() -> Iterator[InMemoryExperimentRegistry]:
    dataset_repository = InMemoryDatasetRepository()
    experiment_registry = InMemoryExperimentRegistry()
    policy_catalog = AcceptancePolicyPresetCatalog()

    def override_registry() -> InMemoryExperimentRegistry:
        return experiment_registry

    def override_datasets() -> InMemoryDatasetRepository:
        return dataset_repository

    def override_policy_catalog() -> AcceptancePolicyPresetCatalog:
        return policy_catalog

    app.dependency_overrides[get_experiment_registry] = override_registry

    app.dependency_overrides[get_dataset_repository] = override_datasets

    app.dependency_overrides[get_acceptance_policy_preset_catalog] = override_policy_catalog

    try:
        yield experiment_registry
    finally:
        app.dependency_overrides.pop(
            get_experiment_registry,
            None,
        )
        app.dependency_overrides.pop(
            get_dataset_repository,
            None,
        )
        app.dependency_overrides.pop(
            get_acceptance_policy_preset_catalog,
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
    assert data["strategy_fingerprint"].startswith("sha256:")
    assert data["result"]["generated_signals"] == 1
    assert data["result"]["benchmark_result"]["benchmark_type"] == "buy_and_hold"
    assert "benchmark_comparison" in data["result"]
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


def test_api_returns_stored_experiment_summary(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    assert create_response.status_code == 200

    experiment_id = create_response.json()["experiment_id"]

    response = client.get(f"/api/v1/research/experiments/{experiment_id}/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["experiment_id"] == experiment_id
    assert data["strategy_name"] == "ema-crossover"
    assert data["strategy_version"] == "1.0.0"
    assert data["strategy_fingerprint"].startswith("sha256:")
    assert data["horizon_candles"] == 1
    assert data["generated_signals"] == 1
    assert data["total_trades"] == 1
    assert data["benchmark_type"] == "buy_and_hold"
    assert data["comparison_outcome"] in {
        "strategy",
        "benchmark",
        "tie",
    }

    # Summary must remain lightweight.
    assert "result" not in data


def test_api_verifies_an_experiment_replay_without_replacing_it(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )
    experiment_id = create_response.json()["experiment_id"]

    response = client.post(
        f"/api/v1/research/experiments/{experiment_id}/replay-verification",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "verified"
    assert response.json()["code"] == "verified"
    assert (
        response.json()["recorded_result_checksum"] == (response.json()["replayed_result_checksum"])
    )
    assert registry.count() == 1


def test_api_returns_404_when_replay_target_is_unknown(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.post(
        "/api/v1/research/experiments/experiment-0000000000000000/replay-verification",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "experiment not found"}


def test_api_returns_404_for_unknown_experiment_summary(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.get("/api/v1/research/experiments/experiment-0000000000000000/summary")

    assert response.status_code == 404
    assert response.json()["detail"] == "experiment not found"


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
    assert summary["total_trades"] == 1
    assert "net_pnl" in summary
    assert "total_return" in summary
    assert "win_rate" in summary
    assert "max_drawdown_fraction" in summary
    assert "profit_factor" in summary
    assert summary["benchmark_type"] == "buy_and_hold"
    assert "benchmark_return" in summary
    assert "excess_return" in summary
    assert "benchmark_max_drawdown_fraction" in summary
    assert "max_drawdown_fraction_delta" in summary
    assert "strategy_has_lower_drawdown" in summary
    assert "comparison_outcome" in summary
    assert "result" not in summary


def test_api_treats_different_backtest_costs_as_different_experiments(
    registry: InMemoryExperimentRegistry,
) -> None:
    first_payload = create_request_payload()
    first_payload["fee_rate"] = "0.001"

    second_payload = create_request_payload()
    second_payload["fee_rate"] = "0.002"

    first_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=first_payload,
    )
    second_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=second_payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["experiment_id"] != second_response.json()["experiment_id"]
    assert registry.count() == 2


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


def test_api_filters_experiment_catalog(
    registry: InMemoryExperimentRegistry,
) -> None:
    for horizon_candles in (1, 2, 3):
        payload = create_request_payload()
        payload["horizon_candles"] = horizon_candles

        response = client.post(
            "/api/v1/research/experiments/ema-crossover",
            json=payload,
        )

        assert response.status_code == 200

    response = client.get(
        "/api/v1/research/experiments",
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


def test_api_sorts_experiment_catalog_by_horizon_descending(
    registry: InMemoryExperimentRegistry,
) -> None:
    for horizon_candles in (1, 2, 3):
        payload = create_request_payload()
        payload["horizon_candles"] = horizon_candles

        response = client.post(
            "/api/v1/research/experiments/ema-crossover",
            json=payload,
        )

        assert response.status_code == 200

    response = client.get(
        "/api/v1/research/experiments",
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


@pytest.mark.parametrize(
    "params",
    [
        {"horizon_candles": 0},
        {"sort_by": "unsupported"},
        {"sort_direction": "sideways"},
        {"strategy_name": " "},
    ],
)
def test_api_rejects_invalid_experiment_catalog_query(
    registry: InMemoryExperimentRegistry,
    params: dict[str, int | str],
) -> None:
    response = client.get(
        "/api/v1/research/experiments",
        params=params,
    )

    assert response.status_code == 422


def test_api_compares_stored_experiments_by_excess_return(
    registry: InMemoryExperimentRegistry,
) -> None:
    experiment_ids = []

    for fee_rate in ("0", "0.01"):
        payload = create_request_payload()
        payload["fee_rate"] = fee_rate

        response = client.post(
            "/api/v1/research/experiments/ema-crossover",
            json=payload,
        )

        assert response.status_code == 200
        experiment_ids.append(response.json()["experiment_id"])

    response = client.post(
        "/api/v1/research/experiments/compare",
        json={
            "experiment_ids": experiment_ids,
            "metric": "excess_return",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["metric"] == "excess_return"
    assert data["ranking_direction"] == "higher_is_better"
    assert data["compared_experiments"] == 2
    assert data["best_experiment_id"] == data["entries"][0]["experiment"]["experiment_id"]
    assert Decimal(data["entries"][0]["metric_value"]) >= Decimal(
        data["entries"][1]["metric_value"]
    )
    assert data["interpretation"] == "historical_research_only"


def test_api_returns_missing_experiment_ids_from_comparison(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    stored_id = create_response.json()["experiment_id"]
    missing_id = "experiment-0000000000000000"

    response = client.post(
        "/api/v1/research/experiments/compare",
        json={
            "experiment_ids": [
                stored_id,
                missing_id,
            ],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "message": "experiments not found",
        "experiment_ids": [missing_id],
    }


def test_api_rejects_comparison_with_different_horizons(
    registry: InMemoryExperimentRegistry,
) -> None:
    experiment_ids = []

    for horizon_candles in (1, 2):
        payload = create_request_payload()
        payload["horizon_candles"] = horizon_candles

        response = client.post(
            "/api/v1/research/experiments/ema-crossover",
            json=payload,
        )

        assert response.status_code == 200
        experiment_ids.append(response.json()["experiment_id"])

    response = client.post(
        "/api/v1/research/experiments/compare",
        json={
            "experiment_ids": experiment_ids,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == ("experiments must use the same evaluation horizon")


@pytest.mark.parametrize(
    "payload",
    [
        {
            "experiment_ids": [
                "experiment-0000000000000001",
            ],
        },
        {
            "experiment_ids": [
                "experiment-0000000000000001",
                "experiment-0000000000000001",
            ],
        },
        {
            "experiment_ids": [
                "experiment-0000000000000001",
                "experiment-0000000000000002",
            ],
            "metric": "unsupported",
        },
    ],
)
def test_api_rejects_invalid_experiment_comparison_request(
    registry: InMemoryExperimentRegistry,
    payload: dict[str, object],
) -> None:
    response = client.post(
        "/api/v1/research/experiments/compare",
        json=payload,
    )

    assert response.status_code == 422


def test_api_assesses_stored_experiment_acceptance(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.post(
        (f"/api/v1/research/experiments/{experiment_id}/acceptance"),
        json={
            "minimum_total_trades": 1,
            "minimum_excess_return": "-1",
            "maximum_drawdown_fraction": "1",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["experiment_id"] == experiment_id
    assert data["outcome"] == "accepted"
    assert len(data["checks"]) == 3
    assert data["interpretation"] == "historical_research_only"


def test_api_marks_experiment_with_few_trades_as_insufficient_data(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.post(
        (f"/api/v1/research/experiments/{experiment_id}/acceptance"),
        json={
            "minimum_total_trades": 20,
        },
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "insufficient_data"


def test_api_returns_404_when_assessed_experiment_does_not_exist(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.post(
        ("/api/v1/research/experiments/experiment-0000000000000000/acceptance"),
        json={},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "experiment not found"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "minimum_total_trades": 0,
        },
        {
            "maximum_drawdown_fraction": "-0.01",
        },
        {
            "maximum_drawdown_fraction": "1.01",
        },
        {
            "unknown_threshold": "1",
        },
    ],
)
def test_api_rejects_invalid_experiment_acceptance_policy(
    registry: InMemoryExperimentRegistry,
    payload: dict[str, object],
) -> None:
    response = client.post(
        ("/api/v1/research/experiments/experiment-0000000000000000/acceptance"),
        json=payload,
    )

    assert response.status_code == 422


def test_api_builds_dashboard_ready_experiment_report(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.post(
        (f"/api/v1/research/experiments/{experiment_id}/report"),
        json={
            "minimum_total_trades": 1,
            "minimum_excess_return": "-1",
            "maximum_drawdown_fraction": "1",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["experiment"]["experiment_id"] == experiment_id
    assert data["acceptance"]["outcome"] == "accepted"
    assert data["benchmark_context"]["benchmark_type"] == "buy_and_hold"

    assert "strategy_total_return" in data["benchmark_context"]
    assert "benchmark_return" in data["benchmark_context"]

    assert data["passed_checks"] == 3
    assert data["failed_checks"] == 0

    assert data["interpretation"] == "historical_research_only"


def test_api_report_preserves_insufficient_data_outcome(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.post(
        (f"/api/v1/research/experiments/{experiment_id}/report"),
        json={
            "minimum_total_trades": 20,
        },
    )

    assert response.status_code == 200

    assert response.json()["acceptance"]["outcome"] == "insufficient_data"


def test_api_returns_404_for_unknown_experiment_report(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.post(
        ("/api/v1/research/experiments/experiment-0000000000000000/report"),
        json={},
    )

    assert response.status_code == 404

    assert response.json()["detail"] == "experiment not found"


def test_api_rejects_invalid_experiment_report_policy(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.post(
        ("/api/v1/research/experiments/experiment-0000000000000000/report"),
        json={
            "maximum_drawdown_fraction": "1.01",
        },
    )

    assert response.status_code == 422


def test_api_lists_versioned_acceptance_policy_presets(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.get("/api/v1/research/acceptance-policies")

    assert response.status_code == 200

    assert [preset["preset_id"] for preset in response.json()] == [
        "baseline-v1",
        "drawdown-focused-v1",
        "larger-sample-v1",
    ]


def test_api_returns_one_acceptance_policy_preset(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.get("/api/v1/research/acceptance-policies/larger-sample-v1")

    assert response.status_code == 200

    data = response.json()

    assert data["preset_id"] == ("larger-sample-v1")
    assert data["version"] == 1

    assert data["policy"]["minimum_total_trades"] == 50

    assert data["interpretation"] == "historical_research_only"


def test_api_returns_404_for_unknown_acceptance_policy_preset(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.get("/api/v1/research/acceptance-policies/unknown-v1")

    assert response.status_code == 404

    assert response.json()["detail"] == ("acceptance policy preset not found")


def test_api_builds_experiment_report_from_versioned_preset(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        ("/api/v1/research/experiments/ema-crossover"),
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.post(
        f"/api/v1/research/experiments/{experiment_id}/report/presets/baseline-v1"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["preset"]["preset_id"] == "baseline-v1"

    assert data["report"]["experiment"]["experiment_id"] == experiment_id

    assert data["report"]["acceptance"]["policy"] == data["preset"]["policy"]

    assert data["interpretation"] == "historical_research_only"


def test_api_returns_404_when_report_preset_does_not_exist(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        ("/api/v1/research/experiments/ema-crossover"),
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.post(
        f"/api/v1/research/experiments/{experiment_id}/report/presets/unknown-v1"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == ("acceptance policy preset not found")


def test_api_exports_versioned_experiment_report_as_csv(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.get(
        f"/api/v1/research/experiments/{experiment_id}/report/presets/baseline-v1/export.csv"
    )

    assert response.status_code == 200

    assert response.headers["content-type"].startswith("text/csv")

    assert response.headers["content-disposition"] == (
        f'attachment; filename="{experiment_id}-baseline-v1.csv"'
    )

    rows = list(csv.reader(StringIO(response.text)))

    assert rows[0] == [
        "section",
        "metric",
        "value",
    ]

    assert [
        "metadata",
        "experiment_id",
        experiment_id,
    ] in rows

    assert [
        "policy_preset",
        "preset_id",
        "baseline-v1",
    ] in rows

    assert [
        "metadata",
        "interpretation",
        "historical_research_only",
    ] in rows


def test_api_returns_404_for_unknown_experiment_csv_export(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.get(
        "/api/v1/research/experiments/"
        "experiment-0000000000000000/"
        "report/presets/baseline-v1/export.csv"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == ("experiment not found")


def test_api_returns_404_for_unknown_csv_export_preset(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    experiment_id = create_response.json()["experiment_id"]

    response = client.get(
        f"/api/v1/research/experiments/{experiment_id}/report/presets/unknown-v1/export.csv"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == ("acceptance policy preset not found")


def test_api_lists_historical_signals_for_stored_experiment(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    assert create_response.status_code == 200

    created_experiment = create_response.json()
    experiment_id = created_experiment["experiment_id"]
    expected_signal = created_experiment["result"]["signals"][0]

    response = client.get(f"/api/v1/research/experiments/{experiment_id}/signals")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["count"] == 1
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert data["has_next"] is False
    assert data["has_previous"] is False

    signal = data["items"][0]

    assert signal["signal_id"] == expected_signal["signal_id"]
    assert signal["dataset_id"] == created_experiment["dataset_id"]
    assert signal["strategy_name"] == created_experiment["strategy_name"]
    assert signal["strategy_version"] == created_experiment["strategy_version"]
    assert signal["direction"] in {
        "long",
        "short",
        "neutral",
    }


def test_api_filters_historical_signals_by_direction(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    assert create_response.status_code == 200

    created_experiment = create_response.json()
    experiment_id = created_experiment["experiment_id"]
    signal_direction = created_experiment["result"]["signals"][0]["direction"]

    matching_response = client.get(
        f"/api/v1/research/experiments/{experiment_id}/signals",
        params={
            "direction": signal_direction,
        },
    )

    assert matching_response.status_code == 200
    assert matching_response.json()["total"] == 1

    non_matching_direction = "short" if signal_direction != "short" else "long"

    non_matching_response = client.get(
        f"/api/v1/research/experiments/{experiment_id}/signals",
        params={
            "direction": non_matching_direction,
        },
    )

    assert non_matching_response.status_code == 200
    assert non_matching_response.json()["total"] == 0
    assert non_matching_response.json()["items"] == []


@pytest.mark.parametrize(
    "params",
    [
        {
            "limit": 0,
        },
        {
            "limit": 101,
        },
        {
            "offset": -1,
        },
        {
            "direction": "unsupported",
        },
        {
            "sort_direction": "sideways",
        },
    ],
)
def test_api_rejects_invalid_experiment_signal_query(
    registry: InMemoryExperimentRegistry,
    params: dict[str, int | str],
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    assert create_response.status_code == 200

    experiment_id = create_response.json()["experiment_id"]

    response = client.get(
        f"/api/v1/research/experiments/{experiment_id}/signals",
        params=params,
    )

    assert response.status_code == 422


def test_api_rejects_invalid_experiment_signal_time_range(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    assert create_response.status_code == 200

    experiment_id = create_response.json()["experiment_id"]

    response = client.get(
        f"/api/v1/research/experiments/{experiment_id}/signals",
        params={
            "candle_close_time_from": "2026-08-22T00:00:00Z",
            "candle_close_time_to": "2026-08-21T00:00:00Z",
        },
    )

    assert response.status_code == 422


def test_api_returns_404_for_unknown_experiment_signals(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.get("/api/v1/research/experiments/experiment-0000000000000000/signals")

    assert response.status_code == 404
    assert response.json()["detail"] == "experiment not found"


def test_performance_series_builder_preserves_stored_reports(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    assert create_response.status_code == 200

    created_experiment = create_response.json()
    experiment_id = created_experiment["experiment_id"]

    experiment = registry.get(experiment_id)

    assert experiment is not None

    series = ExperimentPerformanceSeriesBuilder().build(experiment)

    strategy_report = experiment.result.performance_report
    benchmark_report = experiment.result.benchmark_result.performance_report

    assert series.experiment_id == experiment_id
    assert series.dataset_id == experiment.dataset_id
    assert series.strategy.starting_balance == str(strategy_report.starting_balance)
    assert series.strategy.ending_balance == str(strategy_report.ending_balance)
    assert series.strategy.points == strategy_report.equity_curve
    assert series.benchmark.points == benchmark_report.equity_curve
    assert series.interpretation == "historical_research_only"


def test_api_returns_historical_experiment_performance_series(
    registry: InMemoryExperimentRegistry,
) -> None:
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_request_payload(),
    )

    assert create_response.status_code == 200

    created_experiment = create_response.json()
    experiment_id = created_experiment["experiment_id"]

    response = client.get(f"/api/v1/research/experiments/{experiment_id}/performance-series")

    assert response.status_code == 200

    data = response.json()

    assert data["experiment_id"] == experiment_id
    assert data["dataset_id"] == created_experiment["dataset_id"]
    assert data["benchmark_type"] == "buy_and_hold"
    assert data["interpretation"] == "historical_research_only"

    strategy_report = created_experiment["result"]["performance_report"]
    benchmark_report = created_experiment["result"]["benchmark_result"]["performance_report"]

    assert Decimal(data["strategy"]["starting_balance"]) == Decimal(
        strategy_report["starting_balance"]
    )

    assert Decimal(data["strategy"]["ending_balance"]) == Decimal(strategy_report["ending_balance"])

    assert Decimal(data["strategy"]["total_return"]) == Decimal(strategy_report["total_return"])

    assert Decimal(data["benchmark"]["starting_balance"]) == Decimal(
        benchmark_report["starting_balance"]
    )

    assert Decimal(data["benchmark"]["ending_balance"]) == Decimal(
        benchmark_report["ending_balance"]
    )
    assert data["strategy"]["ending_balance"] == str(strategy_report["ending_balance"])
    assert data["strategy"]["total_return"] == str(strategy_report["total_return"])
    assert data["strategy"]["points"] == strategy_report["equity_curve"]

    assert data["benchmark"]["starting_balance"] == str(benchmark_report["starting_balance"])
    assert data["benchmark"]["ending_balance"] == str(benchmark_report["ending_balance"])
    assert data["benchmark"]["points"] == benchmark_report["equity_curve"]


def test_api_returns_404_for_unknown_experiment_performance_series(
    registry: InMemoryExperimentRegistry,
) -> None:
    response = client.get(
        "/api/v1/research/experiments/experiment-0000000000000000/performance-series"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "experiment not found"
