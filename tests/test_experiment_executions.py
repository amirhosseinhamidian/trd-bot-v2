from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
    ExperimentExecution,
    ExperimentExecutionBuilder,
    ExperimentExecutionStateMachine,
    ExperimentExecutionStatus,
    RSIThresholdExecutionParameters,
    SMACrossoverExecutionParameters,
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


def test_builds_queued_execution(
    parameters: EMACrossoverExecutionParameters,
) -> None:
    created_at = datetime(2026, 8, 25, 8, 30, tzinfo=UTC)

    execution = ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=created_at,
    )

    assert execution.execution_id.startswith("execution-")
    assert execution.created_at == created_at
    assert execution.updated_at == created_at
    assert execution.status is ExperimentExecutionStatus.QUEUED
    assert execution.progress_percent == 0
    assert execution.started_at is None
    assert execution.finished_at is None
    assert execution.experiment_id is None


def test_builds_queued_rsi_execution_and_round_trips_parameters() -> None:
    parameters = RSIThresholdExecutionParameters(
        period=14,
        oversold_threshold=Decimal("30"),
        overbought_threshold=Decimal("70"),
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )

    execution = ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=datetime(2026, 8, 30, 8, 30, tzinfo=UTC),
    )

    restored = ExperimentExecution.model_validate_json(execution.model_dump_json())

    assert execution.strategy_name == "rsi-threshold"
    assert execution.strategy_version == "1.0.0"
    assert isinstance(restored.parameters, RSIThresholdExecutionParameters)
    assert restored.parameters == parameters


def test_builds_queued_sma_execution_and_round_trips_parameters() -> None:
    parameters = SMACrossoverExecutionParameters(
        fast_period=9,
        slow_period=21,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )

    execution = ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=datetime(2026, 8, 31, 8, 30, tzinfo=UTC),
    )

    restored = ExperimentExecution.model_validate_json(execution.model_dump_json())

    assert execution.strategy_name == "sma-crossover"
    assert isinstance(restored.parameters, SMACrossoverExecutionParameters)
    assert restored.parameters == parameters


def test_execution_parameters_reject_foreign_strategy_fields(
    parameters: EMACrossoverExecutionParameters,
) -> None:
    payload = parameters.model_dump()
    payload["period"] = 14

    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        EMACrossoverExecutionParameters.model_validate(payload)


def test_rejects_invalid_ema_period_relationship() -> None:
    with pytest.raises(
        ValidationError,
        match="fast period must be smaller than slow period",
    ):
        EMACrossoverExecutionParameters(
            fast_period=26,
            slow_period=12,
            horizon_candles=100,
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.50"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        )


def test_moves_execution_through_successful_lifecycle(
    parameters: EMACrossoverExecutionParameters,
) -> None:
    created_at = datetime(2026, 8, 25, 8, 30, tzinfo=UTC)
    started_at = created_at + timedelta(seconds=1)
    progressed_at = created_at + timedelta(seconds=2)
    finished_at = created_at + timedelta(seconds=3)

    builder = ExperimentExecutionBuilder()
    state_machine = ExperimentExecutionStateMachine()

    queued = builder.build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=created_at,
    )

    running = state_machine.start(
        queued,
        now=started_at,
    )

    progressed = state_machine.update_progress(
        running,
        progress_percent=60,
        now=progressed_at,
    )

    succeeded = state_machine.succeed(
        progressed,
        experiment_id="experiment-1234567890abcdef",
        now=finished_at,
    )

    assert running.status is ExperimentExecutionStatus.RUNNING
    assert running.progress_percent == 1
    assert running.started_at == started_at

    assert progressed.status is ExperimentExecutionStatus.RUNNING
    assert progressed.progress_percent == 60
    assert progressed.updated_at == progressed_at

    assert succeeded.status is ExperimentExecutionStatus.SUCCEEDED
    assert succeeded.progress_percent == 100
    assert succeeded.experiment_id == "experiment-1234567890abcdef"
    assert succeeded.finished_at == finished_at


def test_moves_running_execution_to_failed(
    parameters: EMACrossoverExecutionParameters,
) -> None:
    created_at = datetime(2026, 8, 25, 8, 30, tzinfo=UTC)

    builder = ExperimentExecutionBuilder()
    state_machine = ExperimentExecutionStateMachine()

    queued = builder.build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=created_at,
    )

    running = state_machine.start(
        queued,
        now=created_at + timedelta(seconds=1),
    )

    failed = state_machine.fail(
        running,
        error_code="execution_failed",
        error_message="The historical experiment could not be completed.",
        now=created_at + timedelta(seconds=2),
    )

    assert failed.status is ExperimentExecutionStatus.FAILED
    assert failed.progress_percent == 1
    assert failed.finished_at == created_at + timedelta(seconds=2)
    assert failed.error_code == "execution_failed"
    assert failed.error_message == ("The historical experiment could not be completed.")


def test_rejects_progress_moving_backwards(
    parameters: EMACrossoverExecutionParameters,
) -> None:
    created_at = datetime(2026, 8, 25, 8, 30, tzinfo=UTC)

    state_machine = ExperimentExecutionStateMachine()

    queued = ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=created_at,
    )

    running = state_machine.start(
        queued,
        now=created_at + timedelta(seconds=1),
    )

    progressed = state_machine.update_progress(
        running,
        progress_percent=70,
        now=created_at + timedelta(seconds=2),
    )

    with pytest.raises(
        ValueError,
        match="execution progress cannot move backwards",
    ):
        state_machine.update_progress(
            progressed,
            progress_percent=40,
            now=created_at + timedelta(seconds=3),
        )


def test_rejects_starting_completed_execution(
    parameters: EMACrossoverExecutionParameters,
) -> None:
    created_at = datetime(2026, 8, 25, 8, 30, tzinfo=UTC)

    state_machine = ExperimentExecutionStateMachine()

    queued = ExperimentExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        now=created_at,
    )

    running = state_machine.start(
        queued,
        now=created_at + timedelta(seconds=1),
    )

    succeeded = state_machine.succeed(
        running,
        experiment_id="experiment-1234567890abcdef",
        now=created_at + timedelta(seconds=2),
    )

    with pytest.raises(
        ValueError,
        match="execution must be queued but is succeeded",
    ):
        state_machine.start(succeeded)
