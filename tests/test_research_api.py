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


def test_research_api_runs_complete_pipeline() -> None:
    candles = [
        create_candle_payload(
            index=0,
            open_price="5",
            close_price="5",
        ),
        create_candle_payload(
            index=1,
            open_price="4",
            close_price="4",
        ),
        create_candle_payload(
            index=2,
            open_price="3",
            close_price="3",
        ),
        create_candle_payload(
            index=3,
            open_price="4",
            close_price="4",
        ),
        create_candle_payload(
            index=4,
            open_price="6",
            close_price="6",
        ),
        create_candle_payload(
            index=5,
            open_price="7",
            close_price="8",
        ),
    ]

    response = client.post(
        "/api/v1/research/ema-crossover",
        json={
            "dataset_name": "API research dataset",
            "candles": candles,
            "fast_period": 2,
            "slow_period": 3,
            "horizon_candles": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["strategy_name"] == "ema-crossover"
    assert data["generated_signals"] == 1
    assert data["summary"]["resolved_signals"] == 1
    assert data["summary"]["long_metrics"]["correct_signals"] == 1


def test_research_api_rejects_missing_candle() -> None:
    candles = [
        create_candle_payload(
            index=0,
            open_price="100",
            close_price="100",
        ),
        create_candle_payload(
            index=2,
            open_price="102",
            close_price="102",
        ),
    ]

    response = client.post(
        "/api/v1/research/ema-crossover",
        json={
            "dataset_name": "Invalid dataset",
            "candles": candles,
            "fast_period": 2,
            "slow_period": 3,
        },
    )

    assert response.status_code == 422

    issues = response.json()["detail"]["issues"]

    assert any(issue["code"] == "missing_candle" for issue in issues)


def test_research_api_rejects_invalid_periods() -> None:
    candles = [
        create_candle_payload(
            index=0,
            open_price="100",
            close_price="100",
        ),
        create_candle_payload(
            index=1,
            open_price="101",
            close_price="101",
        ),
    ]

    response = client.post(
        "/api/v1/research/ema-crossover",
        json={
            "dataset_name": "Invalid periods",
            "candles": candles,
            "fast_period": 5,
            "slow_period": 3,
        },
    )

    assert response.status_code == 422
    assert "slow EMA period must be greater" in (response.json()["detail"])
