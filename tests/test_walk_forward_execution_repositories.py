from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db.base import DatabaseBase
from trd_bot.db.walk_forward_execution_repositories import (
    SqlAlchemyWalkForwardExecutionRepository,
)
from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
    RSIThresholdExecutionParameters,
)
from trd_bot.research.walk_forward import WalkForwardConfig, WalkForwardMode
from trd_bot.research.walk_forward_executions import (
    WalkForwardExecution,
    WalkForwardExecutionBuilder,
    WalkForwardExecutionStateMachine,
    WalkForwardExecutionStatus,
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
def walk_forward_config() -> WalkForwardConfig:
    return WalkForwardConfig(
        train_candles=200,
        test_candles=50,
        step_candles=50,
        gap_candles=5,
        mode=WalkForwardMode.ROLLING,
    )


@pytest.fixture
def execution(
    parameters: EMACrossoverExecutionParameters,
    walk_forward_config: WalkForwardConfig,
) -> WalkForwardExecution:
    return WalkForwardExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=datetime(2026, 8, 25, 9, tzinfo=UTC),
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


def test_sqlalchemy_repository_saves_and_reads_execution(
    session: Session,
    execution: WalkForwardExecution,
) -> None:
    repository = SqlAlchemyWalkForwardExecutionRepository(session)

    stored = repository.save(execution)
    loaded = repository.get(execution.execution_id)

    assert stored == execution
    assert loaded == execution
    assert repository.count() == 1


def test_sqlalchemy_repository_round_trips_rsi_parameters(
    session: Session,
    walk_forward_config: WalkForwardConfig,
) -> None:
    repository = SqlAlchemyWalkForwardExecutionRepository(session)
    execution = WalkForwardExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=RSIThresholdExecutionParameters(
            period=14,
            oversold_threshold=Decimal("30"),
            overbought_threshold=Decimal("70"),
            horizon_candles=1,
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=datetime(2026, 8, 30, 9, tzinfo=UTC),
    )

    repository.save(execution)
    loaded = repository.get(execution.execution_id)

    assert loaded is not None
    assert loaded.strategy_name == "rsi-threshold"
    assert isinstance(loaded.parameters, RSIThresholdExecutionParameters)
    assert loaded.parameters == execution.parameters


def test_sqlalchemy_repository_updates_fold_progress(
    session: Session,
    execution: WalkForwardExecution,
) -> None:
    repository = SqlAlchemyWalkForwardExecutionRepository(session)
    state_machine = WalkForwardExecutionStateMachine()

    repository.save(execution)

    running = state_machine.start(
        execution,
        now=execution.created_at + timedelta(seconds=1),
    )
    progressed = state_machine.update_completed_folds(
        running,
        completed_folds=2,
        now=execution.created_at + timedelta(seconds=2),
    )

    repository.save(running)
    repository.save(progressed)

    loaded = repository.get(execution.execution_id)

    assert loaded is not None
    assert loaded.status is WalkForwardExecutionStatus.RUNNING
    assert loaded.completed_folds == 2
    assert loaded.progress_percent == 50
    assert repository.count() == 1


def test_sqlalchemy_repository_lists_newest_first(
    session: Session,
    parameters: EMACrossoverExecutionParameters,
    walk_forward_config: WalkForwardConfig,
) -> None:
    repository = SqlAlchemyWalkForwardExecutionRepository(session)
    builder = WalkForwardExecutionBuilder()

    first = builder.build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=datetime(2026, 8, 25, 9, tzinfo=UTC),
    )
    second = builder.build(
        dataset_id="dataset-fedcba0987654321",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=datetime(2026, 8, 25, 9, 1, tzinfo=UTC),
    )

    repository.save(first)
    repository.save(second)

    page = repository.list_page(
        limit=1,
        offset=0,
    )

    assert len(page) == 1
    assert page[0].execution_id == second.execution_id


def test_sqlalchemy_repository_validates_pagination(
    session: Session,
) -> None:
    repository = SqlAlchemyWalkForwardExecutionRepository(session)

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
