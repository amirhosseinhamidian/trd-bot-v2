from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.datasets import DatasetBuilder, InMemoryDatasetRepository
from trd_bot.research.experiments import (
    InMemoryExperimentRegistry,
    ResearchExperiment,
)
from trd_bot.research.optimization import (
    OptimizationParameterGrid,
    OptimizationPlanner,
)
from trd_bot.research.optimization_executions import (
    InMemoryOptimizationExecutionRepository,
    OptimizationExecution,
    OptimizationExecutionBuilder,
    OptimizationExecutionState,
)
from trd_bot.research.optimization_worker import (
    OptimizationExecutionJobRunner,
    OptimizationWorker,
)


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


def build_job_execution(dataset_id: str) -> OptimizationExecution:
    plan = OptimizationPlanner().plan(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
        parameter_grid=(
            OptimizationParameterGrid(name="fast_period", values=("2", "3")),
            OptimizationParameterGrid(name="slow_period", values=("4",)),
        ),
    )
    return OptimizationExecutionBuilder().build(
        dataset_id=dataset_id,
        plan=plan,
        horizon_candles=1,
        backtest_config=BacktestConfig(
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        now=datetime(2026, 9, 26, tzinfo=UTC),
    )


def build_dataset_repository() -> tuple[InMemoryDatasetRepository, str]:
    repository = InMemoryDatasetRepository()
    start = datetime(2026, 8, 1, tzinfo=UTC)
    prices = ("10", "9", "8", "9", "11", "13", "12", "10", "11", "14", "16", "15")
    candles = tuple(
        OHLCVCandle(
            source="test-exchange",
            pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
            timeframe=Timeframe.HOUR_1,
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
            received_at=start,
            open_price=Decimal(price),
            high_price=Decimal(price) + Decimal("1"),
            low_price=Decimal(price) - Decimal("1"),
            close_price=Decimal(price),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index, price in enumerate(prices)
    )
    dataset = DatasetBuilder().build(name="Optimization worker dataset", candles=candles)
    repository.save(dataset)
    return repository, dataset.dataset_id


def test_job_runner_persists_trials_ranking_and_progress() -> None:
    datasets, dataset_id = build_dataset_repository()
    executions = InMemoryOptimizationExecutionRepository()
    experiments = InMemoryExperimentRegistry()
    execution = executions.save(build_job_execution(dataset_id))
    progress: list[int] = []

    completed = OptimizationExecutionJobRunner(
        executions=executions,
        datasets=datasets,
        experiments=experiments,
    ).run(
        execution.execution_id,
        report_progress=progress.append,
        cancellation_requested=lambda: False,
    )

    assert completed.status is OptimizationExecutionState.SUCCEEDED
    assert completed.completed_trials == completed.total_trials == 2
    assert completed.best_experiment_id in completed.experiment_ids
    assert experiments.count() == 2
    assert progress == sorted(progress)
    assert progress[-1] == 95


class FailAfterFirstExperimentSave(InMemoryExperimentRegistry):
    def __init__(self) -> None:
        super().__init__()
        self._should_fail = True

    def save(self, experiment: ResearchExperiment) -> ResearchExperiment:
        stored = super().save(experiment)
        if self._should_fail:
            self._should_fail = False
            raise RuntimeError("injected worker interruption")
        return stored


def test_job_runner_resumes_idempotently_after_an_interrupted_trial() -> None:
    datasets, dataset_id = build_dataset_repository()
    executions = InMemoryOptimizationExecutionRepository()
    experiments = FailAfterFirstExperimentSave()
    execution = executions.save(build_job_execution(dataset_id))
    runner = OptimizationExecutionJobRunner(
        executions=executions,
        datasets=datasets,
        experiments=experiments,
    )

    with pytest.raises(RuntimeError, match="injected worker interruption"):
        runner.run(
            execution.execution_id,
            report_progress=lambda _: None,
            cancellation_requested=lambda: False,
        )

    interrupted = executions.get(execution.execution_id)
    assert interrupted is not None
    assert interrupted.status is OptimizationExecutionState.RUNNING
    assert interrupted.completed_trials == 0
    assert experiments.count() == 1

    completed = runner.run(
        execution.execution_id,
        report_progress=lambda _: None,
        cancellation_requested=lambda: False,
    )

    assert completed.status is OptimizationExecutionState.SUCCEEDED
    assert completed.completed_trials == 2
    assert experiments.count() == 2


def test_job_runner_fails_closed_when_dataset_is_missing() -> None:
    executions = InMemoryOptimizationExecutionRepository()
    execution = executions.save(build_job_execution("dataset-0000000000000000"))

    failed = OptimizationExecutionJobRunner(
        executions=executions,
        datasets=InMemoryDatasetRepository(),
        experiments=InMemoryExperimentRegistry(),
    ).run(
        execution.execution_id,
        report_progress=lambda _: None,
        cancellation_requested=lambda: False,
    )

    assert failed.status is OptimizationExecutionState.FAILED
    assert failed.error_code == "dataset_not_found"
