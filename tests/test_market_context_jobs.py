from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_market_context_features import AS_OF, PAIR, SOURCE, complete_input
from trd_bot.api import job_handlers
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import (
    BackgroundJobRow,
    DatabaseBase,
    MarketContextFeatureSnapshotRow,
    MarketContextInputManifestRow,
    MarketRegimeAssessmentRow,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyMarketContextEvaluationEnqueuer,
    SqlAlchemyMarketContextEvaluationRunner,
    SqlAlchemyMarketContextStore,
    SqlAlchemyMarketDataEventStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.jobs import (
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)
from trd_bot.market_context import (
    MarketContextEvaluationCancelled,
    MarketContextEvaluationEnqueueResult,
    MarketContextEvaluationJobPayload,
    MarketContextInputsNotReadyError,
    build_market_context_evaluation_idempotency_key,
    build_market_context_evaluation_job,
)

REQUESTED_AT = AS_OF + timedelta(minutes=5)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def seed_complete_input(factory: sessionmaker[Session]) -> None:
    windows, _ = complete_input()
    with factory.begin() as session:
        store = SqlAlchemyMarketDataEventStore(session)
        for window in windows:
            store.stage_window_version(window)


def enqueue(
    factory: sessionmaker[Session],
    *,
    requested_at: datetime = REQUESTED_AT,
) -> MarketContextEvaluationEnqueueResult:
    with factory() as session:
        return SqlAlchemyMarketContextEvaluationEnqueuer(session).enqueue(
            source=SOURCE,
            pair=PAIR,
            as_of=AS_OF,
            requested_at=requested_at,
        )


def test_payload_freezes_canonical_versions_and_builds_stable_intent_key() -> None:
    first = MarketContextEvaluationJobPayload.build(
        source=f"  {SOURCE}  ",
        pair=PAIR,
        as_of=AS_OF,
        requested_at=REQUESTED_AT,
    )
    later = first.model_copy(update={"requested_at": REQUESTED_AT + timedelta(minutes=10)})

    assert first.source == SOURCE
    assert first.feature_set_version == "market-context-features-v1"
    assert first.algorithm_version == "market-regime-v1"
    assert build_market_context_evaluation_idempotency_key(first) == (
        build_market_context_evaluation_idempotency_key(later)
    )

    with pytest.raises(ValidationError, match="anchor boundary"):
        MarketContextEvaluationJobPayload.build(
            source=SOURCE,
            pair=PAIR,
            as_of=AS_OF + timedelta(minutes=1),
            requested_at=REQUESTED_AT,
        )

    invalid = first.model_dump()
    invalid["feature_set_checksum"] = "0" * 64
    with pytest.raises(ValidationError, match="checksum is not canonical"):
        MarketContextEvaluationJobPayload.model_validate(invalid)


def test_enqueuer_deduplicates_logical_boundary_and_preserves_first_request_time(
    factory: sessionmaker[Session],
) -> None:
    first = enqueue(factory)
    second = enqueue(factory, requested_at=REQUESTED_AT + timedelta(minutes=10))

    assert first.created is True
    assert second.created is False
    assert second.job == first.job
    assert first.job.kind is BackgroundJobKind.MARKET_CONTEXT_EVALUATION
    assert first.job.max_attempts == 3
    assert (
        MarketContextEvaluationJobPayload.model_validate(second.job.payload).requested_at
        == REQUESTED_AT
    )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(BackgroundJobRow)) == 1


def test_runner_commits_complete_pipeline_atomically_and_replays_idempotently(
    factory: sessionmaker[Session],
) -> None:
    seed_complete_input(factory)
    payload = MarketContextEvaluationJobPayload.build(
        source=SOURCE,
        pair=PAIR,
        as_of=AS_OF,
        requested_at=REQUESTED_AT,
    )
    runner = SqlAlchemyMarketContextEvaluationRunner(factory)

    first = runner.run(payload)
    second = runner.run(payload)

    assert second == first
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MarketContextInputManifestRow)) == 1
        assert (
            session.scalar(select(func.count()).select_from(MarketContextFeatureSnapshotRow)) == 1
        )
        assert session.scalar(select(func.count()).select_from(MarketRegimeAssessmentRow)) == 1
        stored = SqlAlchemyMarketContextStore(session).get_assessment(first.assessment_id)
        assert stored == first


def test_runner_rolls_back_partial_pipeline_when_cancellation_is_observed(
    factory: sessionmaker[Session],
) -> None:
    seed_complete_input(factory)
    payload = MarketContextEvaluationJobPayload.build(
        source=SOURCE,
        pair=PAIR,
        as_of=AS_OF,
        requested_at=REQUESTED_AT,
    )
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks == 2

    with pytest.raises(MarketContextEvaluationCancelled):
        SqlAlchemyMarketContextEvaluationRunner(factory).run(
            payload,
            cancellation_requested=cancelled,
        )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MarketContextInputManifestRow)) == 0
        assert (
            session.scalar(select(func.count()).select_from(MarketContextFeatureSnapshotRow)) == 0
        )
        assert session.scalar(select(func.count()).select_from(MarketRegimeAssessmentRow)) == 0


def test_runner_reports_missing_finalized_inputs_without_partial_artifacts(
    factory: sessionmaker[Session],
) -> None:
    payload = MarketContextEvaluationJobPayload.build(
        source=SOURCE,
        pair=PAIR,
        as_of=AS_OF,
        requested_at=REQUESTED_AT,
    )

    with pytest.raises(MarketContextInputsNotReadyError) as raised:
        SqlAlchemyMarketContextEvaluationRunner(factory).run(payload)

    assert raised.value.retryable is True
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MarketContextInputManifestRow)) == 0
        assert (
            session.scalar(select(func.count()).select_from(MarketContextFeatureSnapshotRow)) == 0
        )
        assert session.scalar(select(func.count()).select_from(MarketRegimeAssessmentRow)) == 0


def test_worker_publishes_assessment_reference_and_rejects_invalid_payload(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_complete_input(factory)
    queued = enqueue(factory).job
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)

    with factory() as session:
        repository = SqlAlchemyBackgroundJobRepository(session)
        completed = BackgroundJobWorker(
            repository=repository,
            handlers=build_background_job_handler_registry(),
            worker_id="market-context-worker",
        ).run_once()

    assert completed is not None
    assert completed.job_id == queued.job_id
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert completed.result_reference is not None
    assert completed.result_reference.startswith("market-regime-")

    invalid = build_market_context_evaluation_job(
        source="binance-public",
        pair=PAIR,
        as_of=AS_OF,
        requested_at=REQUESTED_AT + timedelta(hours=1),
    ).model_copy(update={"payload": {"invalid": True}})
    with factory() as session:
        repository = SqlAlchemyBackgroundJobRepository(session)
        repository.enqueue(invalid)
        failed = BackgroundJobWorker(
            repository=repository,
            handlers=build_background_job_handler_registry(),
            worker_id="invalid-market-context-worker",
        ).run_once()

    assert failed is not None
    assert failed.status is BackgroundJobStatus.FAILED
    assert failed.error_code == "invalid_market_context_evaluation_job_payload"


def test_worker_retries_not_ready_inputs_then_preserves_stable_terminal_error(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued = enqueue(factory).job
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)

    with factory() as session:
        worker = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="not-ready-market-context-worker",
        )
        first = worker.run_once()
        assert first is not None
        assert first.status is BackgroundJobStatus.QUEUED
        assert first.attempt_count == 1

        second = worker.run_once(now=first.run_after)
        assert second is not None
        assert second.status is BackgroundJobStatus.QUEUED
        assert second.attempt_count == 2

        terminal = worker.run_once(now=second.run_after)

    assert terminal is not None
    assert terminal.job_id == queued.job_id
    assert terminal.status is BackgroundJobStatus.FAILED
    assert terminal.attempt_count == 3
    assert terminal.error_code == "market_context_inputs_not_ready"
    assert terminal.error_message == (
        "Finalized market-context inputs are not ready for this boundary."
    )


def test_expired_lease_reclaim_reuses_committed_artifacts_without_duplicates(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_complete_input(factory)
    queued = enqueue(factory).job
    payload = MarketContextEvaluationJobPayload.model_validate(queued.payload)
    crashed_at = datetime.now(UTC) - timedelta(seconds=2)

    with factory() as session:
        repository = SqlAlchemyBackgroundJobRepository(session)
        claimed = repository.claim_next(
            worker_id="crashed-market-context-worker",
            lease_duration=timedelta(seconds=1),
            now=crashed_at,
        )
        assert claimed is not None
        assert claimed.attempt_count == 1

    committed_before_reclaim = SqlAlchemyMarketContextEvaluationRunner(factory).run(payload)
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)

    with factory() as session:
        completed = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="reclaim-market-context-worker",
        ).run_once()

    assert completed is not None
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert completed.attempt_count == 2
    assert completed.result_reference == committed_before_reclaim.assessment_id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MarketContextInputManifestRow)) == 1
        assert (
            session.scalar(select(func.count()).select_from(MarketContextFeatureSnapshotRow)) == 1
        )
        assert session.scalar(select(func.count()).select_from(MarketRegimeAssessmentRow)) == 1
