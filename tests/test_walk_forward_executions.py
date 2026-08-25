from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
)
from trd_bot.research.walk_forward import (
    WalkForwardConfig,
    WalkForwardMode,
)
from trd_bot.research.walk_forward_executions import (
    WalkForwardExecution,
    WalkForwardExecutionBuilder,
    WalkForwardExecutionStateMachine,
    WalkForwardExecutionStatus,
)


@pytest.fixture
def parameters() -> EMACrossoverExecutionParameters:
    return EMACrossoverExecutionParameters(
        fast_period=12,
        slow_period=26,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.50"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )


@pytest.fixture
def walk_forward_config() -> WalkForwardConfig:
    return WalkForwardConfig(
        train_candles=100,
        test_candles=20,
        step_candles=20,
        gap_candles=2,
        mode=WalkForwardMode.ROLLING,
    )


def test_builds_queued_walk_forward_execution(
    parameters: EMACrossoverExecutionParameters,
    walk_forward_config: WalkForwardConfig,
) -> None:
    created_at = datetime(2026, 8, 25, 12, tzinfo=UTC)

    execution = WalkForwardExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=created_at,
    )

    assert execution.execution_id.startswith("walk-forward-job-")
    assert execution.created_at == created_at
    assert execution.updated_at == created_at
    assert execution.status is WalkForwardExecutionStatus.QUEUED
    assert execution.progress_percent == 0
    assert execution.total_folds == 4
    assert execution.completed_folds == 0
    assert execution.started_at is None
    assert execution.finished_at is None
    assert execution.walk_forward_run_id is None


def test_moves_execution_through_successful_lifecycle(
    parameters: EMACrossoverExecutionParameters,
    walk_forward_config: WalkForwardConfig,
) -> None:
    created_at = datetime(2026, 8, 25, 12, tzinfo=UTC)
    state_machine = WalkForwardExecutionStateMachine()

    queued = WalkForwardExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=created_at,
    )

    running = state_machine.start(
        queued,
        now=created_at + timedelta(seconds=1),
    )

    half_complete = state_machine.update_completed_folds(
        running,
        completed_folds=2,
        now=created_at + timedelta(seconds=2),
    )

    all_folds_complete = state_machine.update_completed_folds(
        half_complete,
        completed_folds=4,
        now=created_at + timedelta(seconds=3),
    )

    succeeded = state_machine.succeed(
        all_folds_complete,
        walk_forward_run_id="walk-forward-execution-1234567890abcdef",
        now=created_at + timedelta(seconds=4),
    )

    assert running.status is WalkForwardExecutionStatus.RUNNING
    assert running.progress_percent == 0

    assert half_complete.completed_folds == 2
    assert half_complete.progress_percent == 50

    assert all_folds_complete.completed_folds == 4
    assert all_folds_complete.progress_percent == 99

    assert succeeded.status is WalkForwardExecutionStatus.SUCCEEDED
    assert succeeded.progress_percent == 100
    assert succeeded.walk_forward_run_id == ("walk-forward-execution-1234567890abcdef")
    assert succeeded.finished_at == created_at + timedelta(seconds=4)


def test_moves_running_execution_to_failed(
    parameters: EMACrossoverExecutionParameters,
    walk_forward_config: WalkForwardConfig,
) -> None:
    created_at = datetime(2026, 8, 25, 12, tzinfo=UTC)
    state_machine = WalkForwardExecutionStateMachine()

    queued = WalkForwardExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=created_at,
    )

    running = state_machine.start(
        queued,
        now=created_at + timedelta(seconds=1),
    )

    progressed = state_machine.update_completed_folds(
        running,
        completed_folds=1,
        now=created_at + timedelta(seconds=2),
    )

    failed = state_machine.fail(
        progressed,
        error_code="walk_forward_failed",
        error_message="The walk-forward job could not be completed.",
        now=created_at + timedelta(seconds=3),
    )

    assert failed.status is WalkForwardExecutionStatus.FAILED
    assert failed.completed_folds == 1
    assert failed.progress_percent == 25
    assert failed.finished_at == created_at + timedelta(seconds=3)
    assert failed.error_code == "walk_forward_failed"
    assert failed.walk_forward_run_id is None


def test_rejects_completed_folds_moving_backwards(
    parameters: EMACrossoverExecutionParameters,
    walk_forward_config: WalkForwardConfig,
) -> None:
    created_at = datetime(2026, 8, 25, 12, tzinfo=UTC)
    state_machine = WalkForwardExecutionStateMachine()

    queued = WalkForwardExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=created_at,
    )

    running = state_machine.start(
        queued,
        now=created_at + timedelta(seconds=1),
    )

    progressed = state_machine.update_completed_folds(
        running,
        completed_folds=3,
        now=created_at + timedelta(seconds=2),
    )

    with pytest.raises(
        ValueError,
        match="completed folds cannot move backwards",
    ):
        state_machine.update_completed_folds(
            progressed,
            completed_folds=2,
            now=created_at + timedelta(seconds=3),
        )


def test_rejects_success_before_all_folds_are_completed(
    parameters: EMACrossoverExecutionParameters,
    walk_forward_config: WalkForwardConfig,
) -> None:
    created_at = datetime(2026, 8, 25, 12, tzinfo=UTC)
    state_machine = WalkForwardExecutionStateMachine()

    queued = WalkForwardExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=created_at,
    )

    running = state_machine.start(
        queued,
        now=created_at + timedelta(seconds=1),
    )

    with pytest.raises(
        ValueError,
        match="cannot succeed before all folds are completed",
    ):
        state_machine.succeed(
            running,
            walk_forward_run_id="walk-forward-execution-1234567890abcdef",
            now=created_at + timedelta(seconds=2),
        )


def test_rejects_progress_not_derived_from_fold_counts(
    parameters: EMACrossoverExecutionParameters,
    walk_forward_config: WalkForwardConfig,
) -> None:
    queued = WalkForwardExecutionBuilder().build(
        dataset_id="dataset-1234567890abcdef",
        parameters=parameters,
        walk_forward_config=walk_forward_config,
        total_folds=4,
        now=datetime(2026, 8, 25, 12, tzinfo=UTC),
    )

    payload = queued.model_dump()
    payload["progress_percent"] = 25

    with pytest.raises(
        ValidationError,
        match="progress must match completed folds",
    ):
        WalkForwardExecution.model_validate(payload)
