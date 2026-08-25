from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db.base import DatabaseBase
from trd_bot.db.experiment_execution_repositories import (
    SqlAlchemyExperimentExecutionRepository,
)
from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
    ExperimentExecution,
    ExperimentExecutionBuilder,
    ExperimentExecutionStateMachine,
    ExperimentExecutionStatus,
    InMemoryExperimentExecutionRepository,
)


@pytest.fixture
def parameters() -> EMACrossoverExecutionParameters:
    return EMACrossoverExecutionParameters(
        fast_period=12,
        slow_period=26,
        horizon_candles=100,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.50"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )


@pytest.fixture
def execution(
    parameters: EMACrossoverExecutionParameters,
) -> ExperimentExecution:
    return ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=datetime(2026, 8, 25, 8, 30, tzinfo=UTC),
    )


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    DatabaseBase.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    database_session = session_factory()

    try:
        yield database_session
    finally:
        database_session.close()
        engine.dispose()


def test_in_memory_repository_saves_and_updates_execution(
    execution: ExperimentExecution,
) -> None:
    repository = InMemoryExperimentExecutionRepository()
    state_machine = ExperimentExecutionStateMachine()

    repository.save(execution)

    running = state_machine.start(
        execution,
        now=execution.created_at + timedelta(seconds=1),
    )

    repository.save(running)

    stored = repository.get(execution.execution_id)

    assert stored is not None
    assert stored.status is ExperimentExecutionStatus.RUNNING
    assert stored.progress_percent == 1
    assert repository.count() == 1


def test_in_memory_repository_lists_newest_first(
    parameters: EMACrossoverExecutionParameters,
) -> None:
    repository = InMemoryExperimentExecutionRepository()
    builder = ExperimentExecutionBuilder()

    first = builder.build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=datetime(2026, 8, 25, 8, 30, tzinfo=UTC),
    )

    second = builder.build(
        dataset_id="dataset-fedcba0987654321",
        parameters=parameters,
        now=datetime(2026, 8, 25, 8, 31, tzinfo=UTC),
    )

    repository.save(first)
    repository.save(second)

    page = repository.list_page(
        limit=10,
        offset=0,
    )

    assert tuple(item.execution_id for item in page) == (
        second.execution_id,
        first.execution_id,
    )


def test_in_memory_repository_validates_pagination() -> None:
    repository = InMemoryExperimentExecutionRepository()

    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        repository.list_page(
            limit=0,
            offset=0,
        )

    with pytest.raises(
        ValueError,
        match="offset cannot be negative",
    ):
        repository.list_page(
            limit=10,
            offset=-1,
        )


def test_sqlalchemy_repository_saves_and_reads_execution(
    session: Session,
    execution: ExperimentExecution,
) -> None:
    repository = SqlAlchemyExperimentExecutionRepository(session)

    stored = repository.save(execution)
    loaded = repository.get(execution.execution_id)

    assert stored == execution
    assert loaded == execution
    assert repository.count() == 1


def test_sqlalchemy_repository_updates_execution(
    session: Session,
    execution: ExperimentExecution,
) -> None:
    repository = SqlAlchemyExperimentExecutionRepository(session)
    state_machine = ExperimentExecutionStateMachine()

    repository.save(execution)

    running = state_machine.start(
        execution,
        now=execution.created_at + timedelta(seconds=1),
    )

    progressed = state_machine.update_progress(
        running,
        progress_percent=50,
        now=execution.created_at + timedelta(seconds=2),
    )

    repository.save(running)
    repository.save(progressed)

    loaded = repository.get(execution.execution_id)

    assert loaded is not None
    assert loaded.status is ExperimentExecutionStatus.RUNNING
    assert loaded.progress_percent == 50
    assert repository.count() == 1


def test_sqlalchemy_repository_lists_newest_first(
    session: Session,
    parameters: EMACrossoverExecutionParameters,
) -> None:
    repository = SqlAlchemyExperimentExecutionRepository(session)
    builder = ExperimentExecutionBuilder()

    first = builder.build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=datetime(2026, 8, 25, 8, 30, tzinfo=UTC),
    )

    second = builder.build(
        dataset_id="dataset-fedcba0987654321",
        parameters=parameters,
        now=datetime(2026, 8, 25, 8, 31, tzinfo=UTC),
    )

    repository.save(first)
    repository.save(second)

    page = repository.list_page(
        limit=1,
        offset=0,
    )

    assert len(page) == 1
    assert page[0].execution_id == second.execution_id
