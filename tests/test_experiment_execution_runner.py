from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research.datasets import (
    DatasetBuilder,
    InMemoryDatasetRepository,
)
from trd_bot.research.experiment_execution_runner import (
    ExperimentExecutionRunner,
)
from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
    ExperimentExecutionBuilder,
    ExperimentExecutionStateMachine,
    ExperimentExecutionStatus,
    InMemoryExperimentExecutionRepository,
    RSIThresholdExecutionParameters,
)
from trd_bot.research.experiments import InMemoryExperimentRegistry


def build_parameters() -> EMACrossoverExecutionParameters:
    return EMACrossoverExecutionParameters(
        fast_period=9,
        slow_period=21,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )


def build_dataset_candles() -> tuple[OHLCVCandle, ...]:
    start_time = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[OHLCVCandle] = []

    for index in range(60):
        open_time = start_time + timedelta(hours=index)
        close_time = open_time + timedelta(hours=1) - timedelta(milliseconds=1)

        close_price = 200 - index if index < 30 else 170 + (index - 30) * 2

        open_price = Decimal(str(close_price)) - Decimal("0.5")
        high_price = max(
            open_price,
            Decimal(str(close_price)),
        ) + Decimal("1")

        low_price = min(
            open_price,
            Decimal(str(close_price)),
        ) - Decimal("1")

        candle = OHLCVCandle.model_validate(
            {
                "source": "runner-test",
                "pair": {
                    "base_asset": "BTC",
                    "quote_asset": "USDT",
                    "market_type": "spot",
                },
                "timeframe": "1h",
                "open_time": open_time,
                "close_time": close_time,
                "received_at": close_time,
                "open_price": open_price,
                "high_price": high_price,
                "low_price": low_price,
                "close_price": Decimal(str(close_price)),
                "volume": Decimal(str(1000 + index)),
                "is_closed": True,
            }
        )

        candles.append(candle)

    return tuple(candles)


def test_runs_queued_execution_to_success() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = InMemoryExperimentExecutionRepository()
    experiment_registry = InMemoryExperimentRegistry()

    dataset = DatasetBuilder().build(
        name="Runner historical dataset",
        candles=build_dataset_candles(),
    )

    dataset_repository.save(dataset)

    queued = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=build_parameters(),
    )

    execution_repository.save(queued)

    runner = ExperimentExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        experiments=experiment_registry,
    )

    completed = runner.run(queued.execution_id)

    assert completed.status is ExperimentExecutionStatus.SUCCEEDED
    assert completed.progress_percent == 100
    assert completed.started_at is not None
    assert completed.finished_at is not None
    assert completed.experiment_id is not None
    assert completed.error_code is None
    assert completed.error_message is None

    stored_execution = execution_repository.get(queued.execution_id)

    assert stored_execution == completed

    stored_experiment = experiment_registry.get(completed.experiment_id)

    assert stored_experiment is not None
    assert stored_experiment.dataset_id == dataset.dataset_id
    assert stored_experiment.strategy_name == "ema-crossover"
    assert stored_experiment.strategy_fingerprint is not None


def test_runs_queued_rsi_execution_to_success() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = InMemoryExperimentExecutionRepository()
    experiment_registry = InMemoryExperimentRegistry()

    dataset = DatasetBuilder().build(
        name="RSI runner historical dataset",
        candles=build_dataset_candles(),
    )
    dataset_repository.save(dataset)

    queued = ExperimentExecutionBuilder().build(
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
    )
    execution_repository.save(queued)

    completed = ExperimentExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        experiments=experiment_registry,
    ).run(queued.execution_id)

    assert completed.status is ExperimentExecutionStatus.SUCCEEDED
    assert completed.experiment_id is not None

    stored_experiment = experiment_registry.get(completed.experiment_id)

    assert stored_experiment is not None
    assert stored_experiment.strategy_name == "rsi-threshold"
    assert {parameter.name for parameter in stored_experiment.parameters} >= {
        "period",
        "oversold_threshold",
        "overbought_threshold",
    }


def test_marks_execution_failed_for_unregistered_strategy_identity() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = InMemoryExperimentExecutionRepository()
    dataset = DatasetBuilder().build(
        name="Unknown strategy dataset",
        candles=build_dataset_candles(),
    )

    dataset_repository.save(dataset)

    queued = (
        ExperimentExecutionBuilder()
        .build(
            dataset_id=dataset.dataset_id,
            parameters=build_parameters(),
        )
        .model_copy(
            update={
                "strategy_version": "9.9.9",
            }
        )
    )

    execution_repository.save(queued)

    runner = ExperimentExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        experiments=InMemoryExperimentRegistry(),
    )

    completed = runner.run(queued.execution_id)

    assert completed.status is ExperimentExecutionStatus.FAILED
    assert completed.error_code == "execution_failed"


def test_unexpected_runtime_failure_remains_recoverable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    datasets = InMemoryDatasetRepository()
    executions = InMemoryExperimentExecutionRepository()
    dataset = DatasetBuilder().build(
        name="Retryable runner dataset",
        candles=build_dataset_candles(),
    )
    datasets.save(dataset)
    queued = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=build_parameters(),
    )
    executions.save(queued)

    def fail_runtime(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("temporary runtime failure")

    monkeypatch.setattr(
        "trd_bot.research.experiment_execution_runner.ResearchPipeline.run",
        fail_runtime,
    )

    with pytest.raises(RuntimeError, match="temporary runtime failure"):
        ExperimentExecutionRunner(
            executions=executions,
            datasets=datasets,
            experiments=InMemoryExperimentRegistry(),
        ).run(queued.execution_id)

    recoverable = executions.get(queued.execution_id)
    assert recoverable is not None
    assert recoverable.status is ExperimentExecutionStatus.RUNNING
    assert recoverable.progress_percent == 20


def test_marks_execution_failed_when_dataset_is_missing() -> None:
    execution_repository = InMemoryExperimentExecutionRepository()

    queued = ExperimentExecutionBuilder().build(
        dataset_id="dataset-0000000000000000",
        parameters=build_parameters(),
    )

    execution_repository.save(queued)

    runner = ExperimentExecutionRunner(
        executions=execution_repository,
        datasets=InMemoryDatasetRepository(),
        experiments=InMemoryExperimentRegistry(),
    )

    completed = runner.run(queued.execution_id)

    assert completed.status is ExperimentExecutionStatus.FAILED
    assert completed.progress_percent == 1
    assert completed.started_at is not None
    assert completed.finished_at is not None
    assert completed.experiment_id is None
    assert completed.error_code == "dataset_not_found"
    assert completed.error_message == (
        "The historical dataset required for this execution is no longer available."
    )


def test_returns_existing_completed_execution_without_rerunning() -> None:
    dataset_repository = InMemoryDatasetRepository()
    execution_repository = InMemoryExperimentExecutionRepository()
    experiment_registry = InMemoryExperimentRegistry()

    dataset = DatasetBuilder().build(
        name="Idempotent runner dataset",
        candles=build_dataset_candles(),
    )

    dataset_repository.save(dataset)

    queued = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=build_parameters(),
    )

    execution_repository.save(queued)

    runner = ExperimentExecutionRunner(
        executions=execution_repository,
        datasets=dataset_repository,
        experiments=experiment_registry,
    )

    first_result = runner.run(queued.execution_id)
    second_result = runner.run(queued.execution_id)

    assert first_result.status is ExperimentExecutionStatus.SUCCEEDED
    assert second_result == first_result
    assert experiment_registry.count() == 1


def test_resumes_a_running_execution_after_worker_lease_recovery() -> None:
    datasets = InMemoryDatasetRepository()
    executions = InMemoryExperimentExecutionRepository()
    experiments = InMemoryExperimentRegistry()
    dataset = DatasetBuilder().build(
        name="Recovered runner dataset",
        candles=build_dataset_candles(),
    )
    datasets.save(dataset)
    queued = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=build_parameters(),
    )
    state_machine = ExperimentExecutionStateMachine()
    running = state_machine.update_progress(
        state_machine.start(queued),
        progress_percent=90,
    )
    executions.save(running)
    observed_progress: list[int] = []

    completed = ExperimentExecutionRunner(
        executions=executions,
        datasets=datasets,
        experiments=experiments,
    ).run(
        queued.execution_id,
        report_progress=observed_progress.append,
        cancellation_requested=lambda: False,
    )

    assert completed.status is ExperimentExecutionStatus.SUCCEEDED
    assert observed_progress == sorted(observed_progress)
    assert observed_progress[0] == 90
    assert observed_progress[-1] == 95
    assert experiments.count() == 1


def test_cancellation_fails_the_domain_execution_with_a_stable_code() -> None:
    executions = InMemoryExperimentExecutionRepository()
    queued = ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=build_parameters(),
    )
    executions.save(queued)

    cancelled = ExperimentExecutionRunner(
        executions=executions,
        datasets=InMemoryDatasetRepository(),
        experiments=InMemoryExperimentRegistry(),
    ).run(
        queued.execution_id,
        cancellation_requested=lambda: True,
    )

    assert cancelled.status is ExperimentExecutionStatus.FAILED
    assert cancelled.error_code == "experiment_cancelled"


def test_fail_active_transitions_a_queued_execution_after_retry_exhaustion() -> None:
    executions = InMemoryExperimentExecutionRepository()
    queued = ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=build_parameters(),
    )
    executions.save(queued)
    runner = ExperimentExecutionRunner(
        executions=executions,
        datasets=InMemoryDatasetRepository(),
        experiments=InMemoryExperimentRegistry(),
    )

    failed = runner.fail_active(
        queued.execution_id,
        error_code="experiment_attempts_exhausted",
        error_message="Experiment execution stopped after exhausting its retry budget.",
    )

    assert failed.status is ExperimentExecutionStatus.FAILED
    assert failed.error_code == "experiment_attempts_exhausted"


def test_rejects_unknown_execution() -> None:
    runner = ExperimentExecutionRunner(
        executions=InMemoryExperimentExecutionRepository(),
        datasets=InMemoryDatasetRepository(),
        experiments=InMemoryExperimentRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="experiment execution not found",
    ):
        runner.run("execution-0000000000000000")
