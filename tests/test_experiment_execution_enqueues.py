from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyExperimentExecutionEnqueuer,
    SqlAlchemyExperimentExecutionRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.jobs import BackgroundJob, BackgroundJobBuilder, BackgroundJobKind
from trd_bot.research import (
    EMACrossoverExecutionParameters,
    ExperimentExecution,
    ExperimentExecutionBuilder,
    ExperimentExecutionJobPayload,
    build_experiment_execution_idempotency_key,
)

NOW = datetime(2026, 10, 10, 10, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def build_execution() -> ExperimentExecution:
    return ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=EMACrossoverExecutionParameters(
            fast_period=9,
            slow_period=21,
            horizon_candles=1,
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        now=NOW,
    )


def build_job(execution: ExperimentExecution) -> BackgroundJob:
    return BackgroundJobBuilder().build(
        kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
        payload=ExperimentExecutionJobPayload(
            execution_id=execution.execution_id,
        ).model_dump(mode="json"),
        idempotency_key=build_experiment_execution_idempotency_key(execution),
        now=NOW,
    )


def test_atomically_enqueues_an_experiment_execution_and_job(session: Session) -> None:
    execution = build_execution()

    result = SqlAlchemyExperimentExecutionEnqueuer(session).enqueue(
        execution=execution,
        job=build_job(execution),
    )

    assert result.created is True
    assert result.execution == execution
    assert result.job.kind is BackgroundJobKind.EXPERIMENT_EXECUTION
    assert SqlAlchemyExperimentExecutionRepository(session).count() == 1
    assert SqlAlchemyBackgroundJobRepository(session).count() == 1


def test_duplicate_intent_reuses_the_existing_execution_and_job(session: Session) -> None:
    enqueuer = SqlAlchemyExperimentExecutionEnqueuer(session)
    first_execution = build_execution()
    first = enqueuer.enqueue(
        execution=first_execution,
        job=build_job(first_execution),
    )
    duplicate_execution = build_execution()
    duplicate = enqueuer.enqueue(
        execution=duplicate_execution,
        job=build_job(duplicate_execution),
    )

    assert duplicate.created is False
    assert duplicate.execution.execution_id == first.execution.execution_id
    assert duplicate.job.job_id == first.job.job_id
    assert SqlAlchemyExperimentExecutionRepository(session).count() == 1
    assert SqlAlchemyBackgroundJobRepository(session).count() == 1


def test_enqueue_rolls_back_the_job_when_execution_staging_fails(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = build_execution()

    def fail_stage(
        _repository: SqlAlchemyExperimentExecutionRepository,
        _execution: ExperimentExecution,
    ) -> tuple[ExperimentExecution, bool]:
        raise RuntimeError("injected experiment staging failure")

    monkeypatch.setattr(SqlAlchemyExperimentExecutionRepository, "stage", fail_stage)

    with pytest.raises(RuntimeError, match="injected experiment staging failure"):
        SqlAlchemyExperimentExecutionEnqueuer(session).enqueue(
            execution=execution,
            job=build_job(execution),
        )

    assert SqlAlchemyExperimentExecutionRepository(session).count() == 0
    assert SqlAlchemyBackgroundJobRepository(session).count() == 0


def test_enqueue_rejects_a_job_bound_to_another_execution(session: Session) -> None:
    execution = build_execution()
    other_execution = build_execution()

    with pytest.raises(ValueError, match="does not reference"):
        SqlAlchemyExperimentExecutionEnqueuer(session).enqueue(
            execution=execution,
            job=build_job(other_execution),
        )

    assert SqlAlchemyExperimentExecutionRepository(session).count() == 0
    assert SqlAlchemyBackgroundJobRepository(session).count() == 0
