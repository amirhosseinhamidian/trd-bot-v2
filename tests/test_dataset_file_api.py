import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_file_import_enqueuer,
    get_dataset_repository,
)
from trd_bot.main import app
from trd_bot.research import (
    MAX_DATASET_FILE_BYTES,
    InMemoryDatasetFileImportEnqueuer,
    InMemoryDatasetRepository,
)

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


@pytest.fixture
def file_enqueuer() -> Iterator[InMemoryDatasetFileImportEnqueuer]:
    enqueuer = InMemoryDatasetFileImportEnqueuer()

    def override_enqueuer() -> InMemoryDatasetFileImportEnqueuer:
        return enqueuer

    app.dependency_overrides[get_dataset_file_import_enqueuer] = override_enqueuer
    try:
        yield enqueuer
    finally:
        app.dependency_overrides.pop(get_dataset_file_import_enqueuer, None)


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


def test_api_previews_then_stages_the_exact_file_for_a_durable_job(
    repository: InMemoryDatasetRepository,
    file_enqueuer: InMemoryDatasetFileImportEnqueuer,
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

    assert commit_response.status_code == 202
    summary = commit_response.json()
    assert summary["kind"] == "dataset_file_import"
    assert summary["status"] == "queued"
    assert repository.count() == 0
    assert len(file_enqueuer.stages) == 1
    staged = next(iter(file_enqueuer.stages.values()))
    assert staged.file_name == "candles.csv"
    assert staged.request.preview_checksum == preview["preview_checksum"]
    assert staged.content == CSV.encode()


def test_api_stages_a_stale_preview_for_fail_closed_worker_revalidation(
    repository: InMemoryDatasetRepository,
    file_enqueuer: InMemoryDatasetFileImportEnqueuer,
) -> None:
    response = upload(
        "/api/v1/research/datasets/files",
        request={**file_request(), "preview_checksum": "0" * 64},
    )

    assert response.status_code == 202
    assert repository.count() == 0
    assert len(file_enqueuer.stages) == 1


def test_api_reuses_the_same_job_for_duplicate_import_intent(
    repository: InMemoryDatasetRepository,
    file_enqueuer: InMemoryDatasetFileImportEnqueuer,
) -> None:
    preview_response = upload(
        "/api/v1/research/datasets/files/preview",
        request=file_request(),
    )
    request = {
        **file_request(),
        "preview_checksum": preview_response.json()["preview_checksum"],
    }

    first = upload("/api/v1/research/datasets/files", request=request)
    second = upload("/api/v1/research/datasets/files", request=request)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["job_id"] == first.json()["job_id"]
    assert len(file_enqueuer.stages) == 1
    assert len(file_enqueuer.jobs_by_key) == 1
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
