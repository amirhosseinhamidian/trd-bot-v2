from datetime import UTC, datetime

from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.optimization import (
    OptimizationParameterGrid,
    OptimizationPlanner,
)
from trd_bot.research.optimization_executions import OptimizationExecutionBuilder
from trd_bot.research.optimization_worker import OptimizationWorker


class FakeTrialExecutor:
    def execute_trial(self, execution, parameters):
        return "experiment-001"


def build_execution():
    plan = OptimizationPlanner().plan(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
        parameter_grid=(
            OptimizationParameterGrid(
                name="fast_period",
                values=("9",),
            ),
        ),
    )

    return OptimizationExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        plan=plan,
        horizon_candles=1,
        backtest_config=plan.backtest_config,
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
