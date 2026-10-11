from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.jobs import (
    BACKGROUND_JOB_POLICIES,
    DEFAULT_BACKGROUND_JOB_LEASE_DURATION,
    PRODUCTION_BACKGROUND_JOB_KINDS,
    BackgroundJob,
    BackgroundJobBuilder,
    BackgroundJobCancellationMode,
    BackgroundJobContext,
    BackgroundJobHandlerRegistry,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)

NOW = datetime(2026, 10, 11, 6, 30, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def build_job(
    *,
    kind: BackgroundJobKind = BackgroundJobKind.EXPERIMENT_EXECUTION,
    payload: Mapping[str, object] | None = None,
) -> BackgroundJob:
    return BackgroundJobBuilder().build(
        kind=kind,
        payload=payload or {"execution_id": "execution-1234567890abcdef"},
        idempotency_key=f"policy-test:{kind.value}",
        now=NOW,
    )


def test_policy_catalog_and_production_registry_cover_the_exact_allowlist() -> None:
    assert frozenset(BackgroundJobKind) == PRODUCTION_BACKGROUND_JOB_KINDS
    assert frozenset(BACKGROUND_JOB_POLICIES) == PRODUCTION_BACKGROUND_JOB_KINDS
    assert build_background_job_handler_registry().kinds == PRODUCTION_BACKGROUND_JOB_KINDS

    for kind, policy in BACKGROUND_JOB_POLICIES.items():
        assert policy.kind is kind
        assert policy.lease_duration == DEFAULT_BACKGROUND_JOB_LEASE_DURATION
        assert policy.cancellation_mode is BackgroundJobCancellationMode.COOPERATIVE
        assert policy.supported_payload_versions == frozenset({1})


def test_builder_uses_the_kind_specific_retry_budget() -> None:
    expected_attempts = {
        BackgroundJobKind.EXPERIMENT_EXECUTION: 3,
        BackgroundJobKind.WALK_FORWARD_EXECUTION: 3,
        BackgroundJobKind.MARKET_DATA_IMPORT: 1,
        BackgroundJobKind.DATASET_FILE_IMPORT: 3,
        BackgroundJobKind.OPTIMIZATION_EXECUTION: 3,
    }

    assert {
        kind: build_job(kind=kind).max_attempts for kind in BackgroundJobKind
    } == expected_attempts


def test_worker_applies_policy_backoff_until_the_attempt_budget_is_exhausted(
    session: Session,
) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job())

    def fail_transiently(
        _context: BackgroundJobContext,
        _payload: Mapping[str, object],
    ) -> None:
        raise RuntimeError("internal detail must not escape")

    worker = BackgroundJobWorker(
        repository=repository,
        handlers=BackgroundJobHandlerRegistry(
            {BackgroundJobKind.EXPERIMENT_EXECUTION: fail_transiently}
        ),
        worker_id="policy-worker",
    )

    first = worker.run_once(now=NOW)
    assert first is not None
    assert first.status is BackgroundJobStatus.QUEUED
    assert first.run_after == NOW + timedelta(seconds=5)
    assert first.error_code is None

    second = worker.run_once(now=NOW + timedelta(seconds=5))
    assert second is not None
    assert second.status is BackgroundJobStatus.QUEUED
    assert second.run_after == NOW + timedelta(seconds=35)

    terminal = worker.run_once(now=NOW + timedelta(seconds=35))
    assert terminal is not None
    assert terminal.job_id == queued.job_id
    assert terminal.status is BackgroundJobStatus.FAILED
    assert terminal.attempt_count == 3
    assert terminal.error_code == "job_handler_failed"
    assert terminal.error_message == "background job handler failed"


def test_cancellation_dominates_success_and_prevents_retry(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job())

    def cancel_during_execution(
        context: BackgroundJobContext,
        _payload: Mapping[str, object],
    ) -> str:
        repository.request_cancel(context.job.job_id, now=NOW)
        return "result-must-not-be-published"

    completed = BackgroundJobWorker(
        repository=repository,
        handlers=BackgroundJobHandlerRegistry(
            {BackgroundJobKind.EXPERIMENT_EXECUTION: cancel_during_execution}
        ),
        worker_id="cancellation-worker",
    ).run_once(now=NOW)

    assert completed is not None
    assert completed.job_id == queued.job_id
    assert completed.status is BackgroundJobStatus.CANCELLED
    assert completed.result_reference is None
    assert completed.attempt_count == 1


def test_handler_heartbeat_renews_the_worker_lease(session: Session) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    repository.enqueue(build_job())

    def heartbeat(
        context: BackgroundJobContext,
        _payload: Mapping[str, object],
    ) -> str:
        assert context.lease_duration == DEFAULT_BACKGROUND_JOB_LEASE_DURATION
        renewed = context.heartbeat(50, now=NOW)
        assert renewed.lease_expires_at == NOW + DEFAULT_BACKGROUND_JOB_LEASE_DURATION
        return "execution-1234567890abcdef"

    completed = BackgroundJobWorker(
        repository=repository,
        handlers=BackgroundJobHandlerRegistry({BackgroundJobKind.EXPERIMENT_EXECUTION: heartbeat}),
        worker_id="lease-worker",
    ).run_once(now=NOW)

    assert completed is not None
    assert completed.status is BackgroundJobStatus.SUCCEEDED


def test_worker_rejects_an_unsupported_payload_version_before_dispatch(
    session: Session,
) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    version_two = BackgroundJob.model_validate(
        build_job().model_copy(update={"payload_version": 2}).model_dump()
    )
    repository.enqueue(version_two)
    calls: list[str] = []

    def handler(
        _context: BackgroundJobContext,
        _payload: Mapping[str, object],
    ) -> None:
        calls.append("called")

    failed = BackgroundJobWorker(
        repository=repository,
        handlers=BackgroundJobHandlerRegistry({BackgroundJobKind.EXPERIMENT_EXECUTION: handler}),
        worker_id="payload-version-worker",
    ).run_once(now=NOW)

    assert failed is not None
    assert failed.status is BackgroundJobStatus.FAILED
    assert failed.error_code == "unsupported_job_payload_version"
    assert failed.attempt_count == 1
    assert calls == []


@pytest.mark.parametrize(
    ("kind", "error_code"),
    [
        (
            BackgroundJobKind.EXPERIMENT_EXECUTION,
            "invalid_experiment_job_payload",
        ),
        (
            BackgroundJobKind.WALK_FORWARD_EXECUTION,
            "invalid_walk_forward_job_payload",
        ),
        (
            BackgroundJobKind.MARKET_DATA_IMPORT,
            "invalid_market_data_import_job_payload",
        ),
        (
            BackgroundJobKind.DATASET_FILE_IMPORT,
            "invalid_dataset_file_import_job_payload",
        ),
        (
            BackgroundJobKind.OPTIMIZATION_EXECUTION,
            "invalid_optimization_job_payload",
        ),
    ],
)
def test_every_production_handler_rejects_invalid_payload_without_retry(
    session: Session,
    kind: BackgroundJobKind,
    error_code: str,
) -> None:
    repository = SqlAlchemyBackgroundJobRepository(session)
    queued, _ = repository.enqueue(build_job(kind=kind, payload={"invalid": True}))

    failed = BackgroundJobWorker(
        repository=repository,
        handlers=build_background_job_handler_registry(),
        worker_id="invalid-payload-worker",
    ).run_once(now=NOW)

    assert failed is not None
    assert failed.job_id == queued.job_id
    assert failed.status is BackgroundJobStatus.FAILED
    assert failed.attempt_count == 1
    assert failed.error_code == error_code
