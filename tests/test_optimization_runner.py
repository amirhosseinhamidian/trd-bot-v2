from datetime import UTC, datetime
from decimal import Decimal

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.optimization import OptimizationParameterGrid, OptimizationPlanner
from trd_bot.research.optimization_executions import (
    InMemoryOptimizationExecutionRepository,
    OptimizationExecution,
    OptimizationExecutionBuilder,
    OptimizationExecutionState,
    OptimizationExecutionStateMachine,
)
from trd_bot.research.optimization_runner import OptimizationRunner


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


def test_runner_persists_start_and_success() -> None:
    repository = InMemoryOptimizationExecutionRepository()
    execution = build_execution()
    repository.save(execution)
    runner = OptimizationRunner(repository)

    running = runner.start(execution)
    running = repository.save(
        OptimizationExecutionStateMachine().record_trial(
            running,
            experiment_id="experiment-0000000000000001",
        )
    )
    succeeded = runner.complete(
        running,
        best_experiment_id="experiment-0000000000000001",
    )

    assert succeeded.status is OptimizationExecutionState.SUCCEEDED
    assert repository.get(execution.execution_id) == succeeded
