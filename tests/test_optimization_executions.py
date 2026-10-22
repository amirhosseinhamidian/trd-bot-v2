from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.optimization import (
    OptimizationParameterGrid,
    OptimizationPlanner,
)
from trd_bot.research.optimization_executions import (
    InMemoryOptimizationExecutionRepository,
    OptimizationExecution,
    OptimizationExecutionBuilder,
    OptimizationExecutionState,
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


def test_execution_records_trials_and_succeeds() -> None:
    machine = OptimizationExecutionStateMachine()
    running = machine.start(
        build_execution(),
        now=datetime(2026, 9, 1, 6, 1, tzinfo=UTC),
    )
    running = machine.record_trial(
        running,
        experiment_id="experiment-0000000000000001",
        now=datetime(2026, 9, 1, 6, 2, tzinfo=UTC),
    )
    succeeded = machine.succeed(
        running,
        best_experiment_id="experiment-0000000000000001",
        now=datetime(2026, 9, 1, 6, 3, tzinfo=UTC),
    )

    assert succeeded.status is OptimizationExecutionState.SUCCEEDED
    assert succeeded.completed_trials == succeeded.total_trials == 1
    assert succeeded.best_experiment_id == "experiment-0000000000000001"


def test_execution_cannot_succeed_before_all_trials_are_recorded() -> None:
    running = OptimizationExecutionStateMachine().start(build_execution())

    with pytest.raises(ValueError, match="complete every trial"):
        OptimizationExecutionStateMachine().succeed(
            running,
            best_experiment_id="experiment-0000000000000001",
        )


def test_in_memory_repository_saves_lifecycle_state() -> None:
    repository = InMemoryOptimizationExecutionRepository()
    execution = build_execution()

    repository.save(execution)

    assert repository.get(execution.execution_id) == execution
    assert repository.count() == 1
    assert repository.list_page(limit=10, offset=0) == (execution,)
