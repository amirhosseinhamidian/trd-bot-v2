from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import (
    BackgroundJobConflictError,
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.jobs import (
    BackgroundJob,
    BackgroundJobBuilder,
    BackgroundJobContext,
    BackgroundJobHandlerError,
    BackgroundJobHandlerRegistry,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)

NOW = datetime(2026, 9, 26, 6, 30, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def build_job(*, key: str = "experiment-1", max_attempts: int = 3) -> BackgroundJob:
    return BackgroundJobBuilder().build(
        kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
        payload={"execution_id": "experiment-execution-1"},
        idempotency_key=key,
        max_attempts=max_attempts,
        now=NOW,
    )


def test_enqueue_is_idempotent_for_kind_and_key(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    first, created = repository.enqueue(build_job())
    duplicate, duplicate_created = repository.enqueue(build_job())

    assert created is True
    assert duplicate_created is False
    assert duplicate.job_id == first.job_id
    assert repository.count() == 1


def test_claim_heartbeat_and_success_persist_across_repository_instances(
    session: Session,
) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job())
    claimed = repository.claim_next(
        worker_id="worker-a",
        lease_duration=timedelta(seconds=30),
        now=NOW,
    )

    assert claimed is not None
    assert claimed.job_id == queued.job_id
    assert claimed.status is BackgroundJobStatus.RUNNING
    assert claimed.attempt_count == 1

    progressed = repository.heartbeat(
        job_id=queued.job_id,
        worker_id="worker-a",
        progress_percent=45,
        lease_duration=timedelta(seconds=30),
        now=NOW + timedelta(seconds=10),
    )
    assert progressed.progress_percent == 45

    completed = repository.succeed(
        job_id=queued.job_id,
        worker_id="worker-a",
        result_reference="experiment-result-1",
        now=NOW + timedelta(seconds=20),
    )
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert completed.progress_percent == 100
    assert completed.result_reference == "experiment-result-1"
    assert SqlAlchemyBackgroundJobRepository(session).get(queued.job_id) == completed


def test_expired_lease_is_reclaimed_and_stale_worker_is_rejected(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job())
    repository.claim_next(
        worker_id="worker-a",
        lease_duration=timedelta(seconds=10),
        now=NOW,
    )
    reclaimed = repository.claim_next(
        worker_id="worker-b",
        lease_duration=timedelta(seconds=10),
        now=NOW + timedelta(seconds=11),
    )

    assert reclaimed is not None
    assert reclaimed.attempt_count == 2
    assert reclaimed.lease_owner == "worker-b"
    with pytest.raises(BackgroundJobConflictError):
        repository.succeed(
            job_id=queued.job_id,
            worker_id="worker-a",
            now=NOW + timedelta(seconds=12),
        )


def test_retryable_failure_requeues_until_attempt_budget_is_exhausted(
    session: Session,
) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job(max_attempts=2))
    repository.claim_next(
        worker_id="worker-a",
        lease_duration=timedelta(seconds=30),
        now=NOW,
    )
    retried = repository.fail(
        job_id=queued.job_id,
        worker_id="worker-a",
        error_code="temporary",
        error_message="retry me",
        retryable=True,
        now=NOW + timedelta(seconds=1),
    )
    assert retried.status is BackgroundJobStatus.QUEUED

    repository.claim_next(
        worker_id="worker-b",
        lease_duration=timedelta(seconds=30),
        now=NOW + timedelta(seconds=2),
    )
    failed = repository.fail(
        job_id=queued.job_id,
        worker_id="worker-b",
        error_code="temporary",
        error_message="budget exhausted",
        retryable=True,
        now=NOW + timedelta(seconds=3),
    )
    assert failed.status is BackgroundJobStatus.FAILED
    assert failed.attempt_count == 2
    assert failed.error_code == "temporary"


def test_queued_job_can_be_cancelled_without_being_claimed(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job())
    cancelled = repository.request_cancel(queued.job_id, now=NOW + timedelta(seconds=1))

    assert cancelled.status is BackgroundJobStatus.CANCELLED
    assert cancelled.cancel_requested is True
    assert (
        repository.claim_next(
            worker_id="worker-a",
            lease_duration=timedelta(seconds=30),
            now=NOW + timedelta(seconds=2),
        )
        is None
    )


def test_expired_cancelled_job_is_not_reclaimed(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job())
    repository.claim_next(
        worker_id="worker-a",
        lease_duration=timedelta(seconds=10),
        now=NOW,
    )
    repository.request_cancel(queued.job_id, now=NOW + timedelta(seconds=1))

    assert (
        repository.claim_next(
            worker_id="worker-b",
            lease_duration=timedelta(seconds=10),
            now=NOW + timedelta(seconds=11),
        )
        is None
    )
    cancelled = repository.get(queued.job_id)
    assert cancelled is not None
    assert cancelled.status is BackgroundJobStatus.CANCELLED


def test_worker_dispatches_only_registered_job_kinds(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job())
    calls: list[str] = []

    def handle(
        context: BackgroundJobContext,
        payload: Mapping[str, object],
    ) -> str:
        calls.append(str(payload["execution_id"]))
        context.heartbeat(75, lease_duration=timedelta(seconds=30), now=NOW)
        return "experiment-result-1"

    worker = BackgroundJobWorker(
        repository=repository,
        handlers=BackgroundJobHandlerRegistry({BackgroundJobKind.EXPERIMENT_EXECUTION: handle}),
        worker_id="worker-a",
    )
    completed = worker.run_once(now=NOW)

    assert completed is not None
    assert completed.job_id == queued.job_id
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert calls == ["experiment-execution-1"]


def test_worker_fails_unregistered_kind_without_retry(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(
        BackgroundJobBuilder().build(
            kind=BackgroundJobKind.MARKET_DATA_IMPORT,
            payload={"import_id": "market-import-1"},
            now=NOW,
        )
    )
    worker = BackgroundJobWorker(
        repository=repository,
        handlers=BackgroundJobHandlerRegistry(),
        worker_id="worker-a",
    )

    failed = worker.run_once(now=NOW)

    assert failed is not None
    assert failed.job_id == queued.job_id
    assert failed.status is BackgroundJobStatus.FAILED
    assert failed.error_code == "unsupported_job_kind"
    assert failed.attempt_count == 1


def test_worker_honors_a_nonretryable_sanitized_handler_failure(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job(max_attempts=3))

    def fail_handler(
        _context: BackgroundJobContext,
        _payload: Mapping[str, object],
    ) -> str | None:
        raise BackgroundJobHandlerError(
            error_code="optimization_failed",
            error_message="Optimization execution failed.",
            retryable=False,
        )

    failed = BackgroundJobWorker(
        repository=repository,
        handlers=BackgroundJobHandlerRegistry(
            {BackgroundJobKind.EXPERIMENT_EXECUTION: fail_handler}
        ),
        worker_id="worker-a",
    ).run_once(now=NOW)

    assert failed is not None
    assert failed.job_id == queued.job_id
    assert failed.status is BackgroundJobStatus.FAILED
    assert failed.error_code == "optimization_failed"
    assert failed.attempt_count == 1


def test_production_registry_allowlists_market_data_import_jobs() -> None:
    handler = build_background_job_handler_registry().get(BackgroundJobKind.MARKET_DATA_IMPORT)

    assert callable(handler)


def test_production_registry_allowlists_optimization_jobs() -> None:
    handler = build_background_job_handler_registry().get(BackgroundJobKind.OPTIMIZATION_EXECUTION)

    assert callable(handler)
