from datetime import UTC, datetime
from decimal import Decimal

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.db import DatabaseBase, create_database_engine, create_session_factory
from trd_bot.db.optimization_execution_repositories import (
    SqlAlchemyOptimizationExecutionRepository,
)
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.optimization import OptimizationParameterGrid, OptimizationPlanner
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionBuilder,
    OptimizationExecutionStateMachine,
)


def build_execution() -> OptimizationExecution:
    plan = OptimizationPlanner().plan(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
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
        now=datetime(2026, 9, 1, 6, 0, tzinfo=UTC),
    )


def test_sqlalchemy_repository_round_trips_execution_payload() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        repository = SqlAlchemyOptimizationExecutionRepository(session)
        execution = build_execution()
        repository.save(execution)

        running = OptimizationExecutionStateMachine().start(
            execution,
            now=datetime(2026, 9, 1, 6, 1, tzinfo=UTC),
        )
        repository.save(running)

        stored = repository.get(execution.execution_id)

        assert stored == running
        assert repository.count() == 1
        assert repository.list_page(limit=10, offset=0) == (running,)
