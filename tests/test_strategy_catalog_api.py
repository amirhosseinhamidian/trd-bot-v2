from typing import get_args

from fastapi.testclient import TestClient
from pydantic import BaseModel

from trd_bot.api.routes.research import (
    StoredDatasetEMACrossoverExecutionRequest,
    StoredDatasetEMACrossoverWalkForwardExecutionRequest,
    StoredDatasetRSIThresholdExecutionRequest,
    StoredDatasetRSIThresholdWalkForwardExecutionRequest,
    StoredDatasetSMACrossoverExecutionRequest,
    StoredDatasetSMACrossoverWalkForwardExecutionRequest,
)
from trd_bot.main import app
from trd_bot.strategies import build_default_strategy_registry

client = TestClient(app)


def test_lists_versioned_research_strategy_metadata() -> None:
    response = client.get("/api/v1/research/strategies")

    assert response.status_code == 200

    body = response.json()

    assert [item["name"] for item in body] == [
        "ema-crossover",
        "rsi-threshold",
        "sma-crossover",
    ]

    ema, rsi, sma = body

    assert ema["version"] == "1.0.0"
    assert ema["display_name"] == "EMA Crossover"
    assert ema["lifecycle_status"] == "active"
    assert ema["supersedes_version"] is None
    assert ema["behavior_fingerprint"].startswith("sha256:")
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

    assert sma["version"] == "1.0.0"
    assert sma["display_name"] == "SMA Crossover"
    assert [parameter["name"] for parameter in sma["parameters"]] == [
        "fast_period",
        "slow_period",
    ]


def test_gets_exact_strategy_version_and_lists_its_lineage() -> None:
    detail_response = client.get("/api/v1/research/strategies/ema-crossover/versions/1.0.0")
    versions_response = client.get("/api/v1/research/strategies/ema-crossover/versions")

    assert detail_response.status_code == 200
    assert versions_response.status_code == 200
    assert detail_response.json() == versions_response.json()[0]
    assert detail_response.json()["behavior_fingerprint"].startswith("sha256:")


def test_exact_strategy_version_returns_not_found_without_fallback() -> None:
    response = client.get("/api/v1/research/strategies/ema-crossover/versions/9.9.9")

    assert response.status_code == 404
    assert response.json() == {"detail": "strategy version not found"}


def _request_identity(request_model: type[BaseModel]) -> tuple[str, str]:
    name_values = get_args(request_model.model_fields["strategy_name"].annotation)
    version_values = get_args(request_model.model_fields["strategy_version"].annotation)

    assert len(name_values) == 1
    assert len(version_values) == 1

    return str(name_values[0]), str(version_values[0])


def test_execution_request_identities_match_strategy_catalog() -> None:
    catalog_identities = {
        (metadata.name, metadata.version)
        for metadata in build_default_strategy_registry().list_metadata()
    }
    experiment_identities = {
        _request_identity(StoredDatasetEMACrossoverExecutionRequest),
        _request_identity(StoredDatasetRSIThresholdExecutionRequest),
        _request_identity(StoredDatasetSMACrossoverExecutionRequest),
    }
    walk_forward_identities = {
        _request_identity(StoredDatasetEMACrossoverWalkForwardExecutionRequest),
        _request_identity(StoredDatasetRSIThresholdWalkForwardExecutionRequest),
        _request_identity(StoredDatasetSMACrossoverWalkForwardExecutionRequest),
    }

    assert experiment_identities == catalog_identities
    assert walk_forward_identities == catalog_identities
