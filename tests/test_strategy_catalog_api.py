from fastapi.testclient import TestClient

from trd_bot.main import app

client = TestClient(app)


def test_lists_versioned_research_strategy_metadata() -> None:
    response = client.get("/api/v1/research/strategies")

    assert response.status_code == 200

    body = response.json()

    assert [item["name"] for item in body] == [
        "ema-crossover",
        "rsi-threshold",
    ]

    ema, rsi = body

    assert ema["version"] == "1.0.0"
    assert ema["display_name"] == "EMA Crossover"
    assert [parameter["name"] for parameter in ema["parameters"]] == [
        "fast_period",
        "slow_period",
    ]
    assert ema["parameters"][0] == {
        "name": "fast_period",
        "kind": "integer",
        "default_value": "9",
        "minimum": "2",
        "maximum": None,
        "minimum_exclusive": False,
        "maximum_exclusive": False,
    }

    assert rsi["version"] == "1.0.0"
    assert rsi["display_name"] == "RSI Threshold"
    assert [parameter["name"] for parameter in rsi["parameters"]] == [
        "period",
        "oversold_threshold",
        "overbought_threshold",
    ]
    assert rsi["parameters"][1]["kind"] == "decimal"
    assert rsi["parameters"][1]["minimum"] == "0"
    assert rsi["parameters"][1]["maximum"] == "50"
    assert rsi["parameters"][1]["minimum_exclusive"] is True
    assert rsi["parameters"][1]["maximum_exclusive"] is True
