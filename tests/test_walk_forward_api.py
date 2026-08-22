from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from trd_bot.main import app

client = TestClient(app)


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
        "open_time": datetime(2026, 8, 21, hour, tzinfo=UTC).isoformat(),
        "close_time": datetime(2026, 8, 21, hour + 1, tzinfo=UTC).isoformat(),
        "received_at": datetime(2026, 8, 22, 10, tzinfo=UTC).isoformat(),
        "open_price": str(open_decimal),
        "high_price": str(max(open_decimal, close_decimal) + Decimal("1")),
        "low_price": str(min(open_decimal, close_decimal) - Decimal("1")),
        "close_price": str(close_decimal),
        "volume": "1000",
        "is_closed": True,
    }


def create_request_payload(candle_count: int = 10) -> dict[str, object]:
    candles = [
        create_candle_payload(
            index=index,
            open_price=str(100 + index),
            close_price=str(100 + index),
        )
        for index in range(candle_count)
    ]
    return {
        "dataset_name": "API walk-forward dataset",
        "candles": candles,
        "fast_period": 2,
        "slow_period": 3,
        "horizon_candles": 1,
        "train_candles": 4,
        "test_candles": 2,
        "step_candles": 2,
        "gap_candles": 0,
        "mode": "rolling",
    }


def test_walk_forward_api_runs_all_out_of_sample_folds() -> None:
    response = client.post(
        "/api/v1/research/walk-forward/ema-crossover",
        json=create_request_payload(),
    )

    assert response.status_code == 200
    data = response.json()

    assert data["execution_id"].startswith("walk-forward-execution-")
    assert data["plan_id"].startswith("walk-forward-")
    assert data["strategy_name"] == "ema-crossover"
    assert data["strategy_version"] == "1.0.0"
    assert data["summary"]["total_folds"] == 3
    assert len(data["fold_results"]) == 3
    assert data["backtest_config"]["starting_balance"] == "10000"

    for fold_result in data["fold_results"]:
        assert fold_result["result"]["dataset_id"] == fold_result["test_dataset_id"]
        assert (
            fold_result["result"]["benchmark_result"]["dataset_id"]
            == (fold_result["test_dataset_id"])
        )


def test_walk_forward_api_is_deterministic() -> None:
    payload = create_request_payload()

    first = client.post(
        "/api/v1/research/walk-forward/ema-crossover",
        json=payload,
    )
    second = client.post(
        "/api/v1/research/walk-forward/ema-crossover",
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["execution_id"] == second.json()["execution_id"]
    assert first.json()["summary"] == second.json()["summary"]


def test_walk_forward_api_rejects_dataset_without_complete_fold() -> None:
    response = client.post(
        "/api/v1/research/walk-forward/ema-crossover",
        json=create_request_payload(candle_count=5),
    )

    assert response.status_code == 422
    assert "requires at least 6 candles" in response.json()["detail"]


def test_walk_forward_api_rejects_overlapping_test_windows() -> None:
    payload = create_request_payload()
    payload["test_candles"] = 3
    payload["step_candles"] = 2

    response = client.post(
        "/api/v1/research/walk-forward/ema-crossover",
        json=payload,
    )

    assert response.status_code == 422
    assert "step candles must be at least test candles" in response.json()["detail"]


def test_walk_forward_api_reports_market_data_quality_issues() -> None:
    payload = create_request_payload(candle_count=2)
    candles = payload["candles"]
    assert isinstance(candles, list)
    candles[1] = create_candle_payload(
        index=2,
        open_price="102",
        close_price="102",
    )

    response = client.post(
        "/api/v1/research/walk-forward/ema-crossover",
        json=payload,
    )

    assert response.status_code == 422
    issues = response.json()["detail"]["issues"]
    assert any(issue["code"] == "missing_candle" for issue in issues)
