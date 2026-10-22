from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyOptimizationExecutionEnqueuer,
    SqlAlchemyOptimizationExecutionRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.jobs import BackgroundJob, BackgroundJobBuilder, BackgroundJobKind
from trd_bot.research.optimization import OptimizationParameterGrid, OptimizationPlanner
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionBuilder,
)
from trd_bot.research.optimization_jobs import (
    OptimizationExecutionJobPayload,
    build_optimization_execution_idempotency_key,
)

NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def build_execution() -> OptimizationExecution:
    plan = OptimizationPlanner().plan(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        parameter_grid=(
            OptimizationParameterGrid(name="fast_period", values=("9",)),
            OptimizationParameterGrid(name="slow_period", values=("21",)),
        ),
    )
    return OptimizationExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        plan=plan,
        horizon_candles=1,
        backtest_config=BacktestConfig(
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        now=NOW,
    )


def build_job(execution: OptimizationExecution) -> BackgroundJob:
    return BackgroundJobBuilder().build(
        kind=BackgroundJobKind.OPTIMIZATION_EXECUTION,
        payload=OptimizationExecutionJobPayload(
            execution_id=execution.execution_id,
        ).model_dump(mode="json"),
        idempotency_key=build_optimization_execution_idempotency_key(execution),
        now=NOW,
    )


def test_atomically_enqueues_an_execution_and_job(session: Session) -> None:
    execution = build_execution()
    result = SqlAlchemyOptimizationExecutionEnqueuer(session).enqueue(
        execution=execution,
        job=build_job(execution),
    )

    assert result.created is True
    assert result.execution == execution
    assert result.job.kind is BackgroundJobKind.OPTIMIZATION_EXECUTION
    assert SqlAlchemyOptimizationExecutionRepository(session).count() == 1
    assert SqlAlchemyBackgroundJobRepository(session).count() == 1


def test_duplicate_intent_reuses_the_existing_execution_and_job(session: Session) -> None:
    first_execution = build_execution()
    enqueuer = SqlAlchemyOptimizationExecutionEnqueuer(session)
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
    assert SqlAlchemyOptimizationExecutionRepository(session).count() == 1
    assert SqlAlchemyBackgroundJobRepository(session).count() == 1


def test_enqueue_rolls_back_the_job_when_execution_staging_fails(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = build_execution()

    def fail_stage(
        _repository: SqlAlchemyOptimizationExecutionRepository,
        _staged_execution: OptimizationExecution,
    ) -> tuple[OptimizationExecution, bool]:
        raise RuntimeError("injected execution staging failure")

    monkeypatch.setattr(SqlAlchemyOptimizationExecutionRepository, "stage", fail_stage)

    with pytest.raises(RuntimeError, match="injected execution staging failure"):
        SqlAlchemyOptimizationExecutionEnqueuer(session).enqueue(
            execution=execution,
            job=build_job(execution),
        )

    assert SqlAlchemyOptimizationExecutionRepository(session).count() == 0
    assert SqlAlchemyBackgroundJobRepository(session).count() == 0
