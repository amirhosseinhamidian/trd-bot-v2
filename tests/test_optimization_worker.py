from datetime import UTC, datetime
from decimal import Decimal

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.optimization import (
    OptimizationParameterGrid,
    OptimizationPlanner,
)
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionBuilder,
)
from trd_bot.research.optimization_worker import OptimizationWorker


class FakeTrialExecutor:
    def execute_trial(
        self,
        execution: OptimizationExecution,
        parameters: dict[str, str],
    ) -> str:
        return "experiment-001"


def build_execution() -> OptimizationExecution:
    plan = OptimizationPlanner().plan(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
        parameter_grid=(
            OptimizationParameterGrid(
                name="fast_period",
                values=("9",),
            ),
            OptimizationParameterGrid(
                name="slow_period",
                values=("21",),
            ),
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
        now=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_worker_runs_trial() -> None:
    worker = OptimizationWorker(FakeTrialExecutor())

    result = worker.run_trial(
        execution=build_execution(),
        parameters={"fast_period": "9"},
    )

    assert result.experiment_id == "experiment-001"
    assert result.parameters == {"fast_period": "9"}
