from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research.datasets import (
    DatasetBuilder,
    DatasetSnapshot,
    InMemoryDatasetRepository,
)
from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
    RSIThresholdExecutionParameters,
)
from trd_bot.research.walk_forward import (
    WalkForwardConfig,
    WalkForwardExecutionResult,
    WalkForwardExecutor,
    WalkForwardPlanner,
)
from trd_bot.research.walk_forward_execution_runner import (
    WalkForwardExecutionRunner,
)
from trd_bot.research.walk_forward_executions import (
    InMemoryWalkForwardExecutionRepository,
    WalkForwardExecution,
    WalkForwardExecutionBuilder,
    WalkForwardExecutionStatus,
)
from trd_bot.research.walk_forward_runs import (
    InMemoryWalkForwardRunRegistry,
)


class RecordingExecutionRepository(InMemoryWalkForwardExecutionRepository):
    def __init__(self) -> None:
        super().__init__()
        self.saved: list[WalkForwardExecution] = []

    def save(
        self,
        execution: WalkForwardExecution,
    ) -> WalkForwardExecution:
        self.saved.append(execution)
        return super().save(execution)


class FailingWalkForwardExecutor(WalkForwardExecutor):
    def execute(self, **kwargs: object) -> WalkForwardExecutionResult:
        callback = kwargs["on_fold_completed"]

        assert callable(callback)
        callback(1, 3)

        raise RuntimeError("simulated fold failure")


def build_parameters() -> EMACrossoverExecutionParameters:
    return EMACrossoverExecutionParameters(
        fast_period=2,
        slow_period=3,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )


def build_walk_forward_config() -> WalkForwardConfig:
    return WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
        gap_candles=0,
    )


def build_dataset() -> DatasetSnapshot:
    start_time = datetime(2026, 8, 25, tzinfo=UTC)
    candles: list[OHLCVCandle] = []

    for index in range(10):
        open_time = start_time + timedelta(hours=index)
        close_time = open_time + timedelta(hours=1)
        price = Decimal("100") + Decimal(index)

        candles.append(
            OHLCVCandle.model_validate(
                {
                    "source": "walk-forward-runner-test",
                    "pair": {
                        "base_asset": "BTC",
                        "quote_asset": "USDT",
                        "market_type": "spot",
                    },
                    "timeframe": "1h",
                    "open_time": open_time,
                    "close_time": close_time,
                    "received_at": close_time,
                    "open_price": price,
                    "high_price": price + Decimal("1"),
                    "low_price": price - Decimal("1"),
                    "close_price": price + Decimal("0.5"),
                    "volume": Decimal("1000"),
                    "is_closed": True,
                }
            )
        )

    return DatasetBuilder().build(
        name="Walk-forward runner dataset",
        candles=candles,
    )


def build_queued_execution(
    dataset: DatasetSnapshot,
) -> WalkForwardExecution:
    config = build_walk_forward_config()
    plan = WalkForwardPlanner().plan(
        dataset=dataset,
        config=config,
    )

    return WalkForwardExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=build_parameters(),
        walk_forward_config=config,
        total_folds=len(plan.folds),
    )


def test_runs_queued_walk_forward_execution_to_success() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = RecordingExecutionRepository()
    run_registry = InMemoryWalkForwardRunRegistry()
    dataset = build_dataset()

    dataset_repository.save(dataset)

    queued = build_queued_execution(dataset)
    execution_repository.save(queued)

    runner = WalkForwardExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        runs=run_registry,
    )

    completed = runner.run(queued.execution_id)

    assert completed.status is WalkForwardExecutionStatus.SUCCEEDED
    assert completed.completed_folds == 3
    assert completed.progress_percent == 100
    assert completed.started_at is not None
    assert completed.finished_at is not None
    assert completed.walk_forward_run_id is not None
    assert completed.error_code is None
    assert completed.error_message is None

    stored_execution = execution_repository.get(queued.execution_id)
    stored_run = run_registry.get(completed.walk_forward_run_id)

    assert stored_execution == completed
    assert stored_run is not None
    assert stored_run.result.source_dataset_id == dataset.dataset_id

    running_states = [
        execution
        for execution in execution_repository.saved
        if execution.status is WalkForwardExecutionStatus.RUNNING
    ]

    assert [execution.completed_folds for execution in running_states] == [
        0,
        1,
        2,
        3,
    ]
    assert [execution.progress_percent for execution in running_states] == [
        0,
        33,
        66,
        99,
    ]


def test_runs_queued_rsi_walk_forward_execution_to_success() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = InMemoryWalkForwardExecutionRepository()
    run_registry = InMemoryWalkForwardRunRegistry()
    dataset = build_dataset()

    dataset_repository.save(dataset)

    config = build_walk_forward_config()
    plan = WalkForwardPlanner().plan(
        dataset=dataset,
        config=config,
    )

    queued = WalkForwardExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=RSIThresholdExecutionParameters(
            period=2,
            oversold_threshold=Decimal("30"),
            overbought_threshold=Decimal("70"),
            horizon_candles=1,
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        walk_forward_config=config,
        total_folds=len(plan.folds),
    )
    execution_repository.save(queued)

    completed = WalkForwardExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        runs=run_registry,
    ).run(queued.execution_id)

    assert completed.status is WalkForwardExecutionStatus.SUCCEEDED
    assert completed.walk_forward_run_id is not None

    stored_run = run_registry.get(completed.walk_forward_run_id)

    assert stored_run is not None
    assert stored_run.result.strategy_name == "rsi-threshold"
    assert {parameter.name for parameter in stored_run.result.strategy_parameters} == {
        "period",
        "oversold_threshold",
        "overbought_threshold",
    }


def test_marks_walk_forward_execution_failed_for_unregistered_strategy_identity() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = InMemoryWalkForwardExecutionRepository()
    dataset = build_dataset()

    dataset_repository.save(dataset)

    queued = build_queued_execution(dataset).model_copy(
        update={
            "strategy_version": "9.9.9",
        }
    )
    execution_repository.save(queued)

    runner = WalkForwardExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        runs=InMemoryWalkForwardRunRegistry(),
    )

    completed = runner.run(queued.execution_id)

    assert completed.status is WalkForwardExecutionStatus.FAILED
    assert completed.error_code == "execution_failed"


def test_marks_walk_forward_execution_failed_when_dataset_is_missing() -> None:
    execution_repository = InMemoryWalkForwardExecutionRepository()
    queued = WalkForwardExecutionBuilder().build(
        dataset_id="dataset-0000000000000000",
        parameters=build_parameters(),
        walk_forward_config=build_walk_forward_config(),
        total_folds=3,
    )

    execution_repository.save(queued)

    runner = WalkForwardExecutionRunner(
        executions=execution_repository,
        datasets=InMemoryDatasetRepository(),
        runs=InMemoryWalkForwardRunRegistry(),
    )

    completed = runner.run(queued.execution_id)

    assert completed.status is WalkForwardExecutionStatus.FAILED
    assert completed.completed_folds == 0
    assert completed.progress_percent == 0
    assert completed.walk_forward_run_id is None
    assert completed.error_code == "dataset_not_found"
    assert completed.error_message == (
        "The historical dataset required for this walk-forward execution is no longer available."
    )


def test_preserves_completed_fold_progress_when_execution_fails() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = InMemoryWalkForwardExecutionRepository()
    dataset = build_dataset()

    dataset_repository.save(dataset)

    queued = build_queued_execution(dataset)
    execution_repository.save(queued)

    runner = WalkForwardExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        runs=InMemoryWalkForwardRunRegistry(),
        executor=FailingWalkForwardExecutor(),
    )

    completed = runner.run(queued.execution_id)

    assert completed.status is WalkForwardExecutionStatus.FAILED
    assert completed.completed_folds == 1
    assert completed.progress_percent == 33
    assert completed.error_code == "execution_failed"
    assert completed.error_message == "The walk-forward execution could not be completed."


def test_returns_existing_completed_execution_without_rerunning() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = InMemoryWalkForwardExecutionRepository()
    run_registry = InMemoryWalkForwardRunRegistry()
    dataset = build_dataset()

    dataset_repository.save(dataset)

    queued = build_queued_execution(dataset)
    execution_repository.save(queued)

    runner = WalkForwardExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        runs=run_registry,
    )

    first_result = runner.run(queued.execution_id)
    second_result = runner.run(queued.execution_id)

    assert first_result.status is WalkForwardExecutionStatus.SUCCEEDED
    assert second_result == first_result
    assert run_registry.count() == 1


def test_rejects_unknown_walk_forward_execution() -> None:
    runner = WalkForwardExecutionRunner(
        executions=InMemoryWalkForwardExecutionRepository(),
        datasets=InMemoryDatasetRepository(),
        runs=InMemoryWalkForwardRunRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="walk-forward execution not found",
    ):
        runner.run("walk-forward-job-0000000000000000")
