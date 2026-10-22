from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import get_background_job_repository
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.jobs import BackgroundJobBuilder, BackgroundJobKind
from trd_bot.main import app

client = TestClient(app)
NOW = datetime(2026, 9, 26, 7, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[SqlAlchemyBackgroundJobRepository]:
    database_path = tmp_path / "background-jobs-api.db"
    engine = create_database_engine(f"sqlite+pysqlite:///{database_path}")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    def override_repository() -> Iterator[SqlAlchemyBackgroundJobRepository]:
        with factory() as request_session:
            yield SqlAlchemyBackgroundJobRepository(request_session)

    app.dependency_overrides[get_background_job_repository] = override_repository
    try:
        with factory() as session:
            job_repository = SqlAlchemyBackgroundJobRepository(session)
            yield job_repository
    finally:
        app.dependency_overrides.pop(get_background_job_repository, None)
        engine.dispose()


def enqueue(repository: SqlAlchemyBackgroundJobRepository, key: str = "api-job") -> str:
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
        payload={"execution_id": "experiment-execution-api"},
        idempotency_key=key,
        now=NOW,
    )
    stored, _ = repository.enqueue(job)
    return stored.job_id


def test_api_lists_reads_and_cancels_a_queued_job(
    repository: SqlAlchemyBackgroundJobRepository,
) -> None:
    job_id = enqueue(repository)

    listing = client.get("/api/v1/jobs", params={"status": "queued"})
    assert listing.status_code == 200
    assert listing.json()["items"][0]["job_id"] == job_id

    detail = client.get(f"/api/v1/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["progress_percent"] == 0
    assert "payload" not in detail.json()
    assert "idempotency_key" not in detail.json()
    assert "lease_owner" not in detail.json()

    cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_api_retries_only_failed_jobs(
    repository: SqlAlchemyBackgroundJobRepository,
) -> None:
    job_id = enqueue(repository, "failed-api-job")
    repository.claim_next(
        worker_id="api-worker",
        lease_duration=timedelta(seconds=30),
        now=NOW,
    )
    repository.fail(
        job_id=job_id,
        worker_id="api-worker",
        error_code="permanent",
        error_message="failed for API test",
        retryable=False,
        now=NOW + timedelta(seconds=1),
    )

    retried = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "queued"

    conflict = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "job_not_retryable"


def test_api_returns_not_found_for_unknown_job(
    repository: SqlAlchemyBackgroundJobRepository,
) -> None:
    del repository
    response = client.get("/api/v1/jobs/job-00000000000000000000")
    assert response.status_code == 404
