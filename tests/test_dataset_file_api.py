import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import get_dataset_repository
from trd_bot.main import app
from trd_bot.research import MAX_DATASET_FILE_BYTES, InMemoryDatasetRepository

client = TestClient(app)

CSV = """timestamp,end,open,high,low,close,vol,closed
2026-08-20T10:00:00+00:00,2026-08-20T11:00:00+00:00,100,102,99,101,1500,true
2026-08-20T11:00:00+00:00,2026-08-20T12:00:00+00:00,101,103,100,102,1600,true
"""


def file_request() -> dict[str, object]:
    return {
        "name": "Uploaded BTC dataset",
        "source": "manual-file",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": "1h",
        "column_mapping": {
            "open_time": "timestamp",
            "close_time": "end",
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "volume": "vol",
            "is_closed": "closed",
        },
    }


@pytest.fixture
def repository() -> Iterator[InMemoryDatasetRepository]:
    dataset_repository = InMemoryDatasetRepository()

    def override_repository() -> InMemoryDatasetRepository:
        return dataset_repository

    app.dependency_overrides[get_dataset_repository] = override_repository
    try:
        yield dataset_repository
    finally:
        app.dependency_overrides.pop(get_dataset_repository, None)


def upload(path: str, *, request: dict[str, object] | None = None) -> Any:
    data = {} if request is None else {"request": json.dumps(request)}
    return client.post(
        path,
        data=data,
        files={"file": ("candles.csv", CSV.encode(), "text/csv")},
    )


def test_api_inspects_dataset_file_without_persisting(
    repository: InMemoryDatasetRepository,
) -> None:
    response = upload("/api/v1/research/datasets/files/inspect")

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_format"] == "csv"
    assert payload["row_count"] == 2
    assert payload["suggested_mapping"]["open_time"] == "timestamp"
    assert payload["can_preview"] is True
    assert repository.count() == 0


def test_api_previews_then_commits_the_exact_canonical_file(
    repository: InMemoryDatasetRepository,
) -> None:
    preview_response = upload(
        "/api/v1/research/datasets/files/preview",
        request=file_request(),
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["ready_to_import"] is True
    assert preview["quality_report"]["acceptance"]["accepted"] is True

    commit_response = upload(
        "/api/v1/research/datasets/files",
        request={**file_request(), "preview_checksum": preview["preview_checksum"]},
    )

    assert commit_response.status_code == 201
    summary = commit_response.json()
    stored = repository.get(summary["dataset_id"])
    assert stored is not None
    assert stored.checksum == preview["preview_checksum"]
    assert stored.provenance.original_filename == "candles.csv"
    assert stored.provenance.original_file_format == "csv"


def test_api_rejects_commit_with_stale_preview_checksum(
    repository: InMemoryDatasetRepository,
) -> None:
    response = upload(
        "/api/v1/research/datasets/files",
        request={**file_request(), "preview_checksum": "0" * 64},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "preview_mismatch"
    assert repository.count() == 0


def test_api_rejects_unsupported_file_extension(
    repository: InMemoryDatasetRepository,
) -> None:
    response = client.post(
        "/api/v1/research/datasets/files/inspect",
        files={"file": ("candles.txt", CSV.encode(), "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_format"


def test_api_rejects_file_larger_than_the_bounded_upload_limit(
    repository: InMemoryDatasetRepository,
) -> None:
    response = client.post(
        "/api/v1/research/datasets/files/inspect",
        files={
            "file": (
                "candles.csv",
                b"x" * (MAX_DATASET_FILE_BYTES + 1),
                "text/csv",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"
    assert repository.count() == 0


def test_api_returns_a_stable_error_for_an_invalid_preview_request(
    repository: InMemoryDatasetRepository,
) -> None:
    response = upload(
        "/api/v1/research/datasets/files/preview",
        request={**file_request(), "column_mapping": {}},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert repository.count() == 0
