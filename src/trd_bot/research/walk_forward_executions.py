from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.research.experiment_executions import (
    StrategyExecutionParameters,
)
from trd_bot.research.walk_forward import WalkForwardConfig


class WalkForwardExecutionStatus(StrEnum):
    """Persistent lifecycle state of a walk-forward job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def _fold_progress_percent(
    *,
    status: WalkForwardExecutionStatus,
    completed_folds: int,
    total_folds: int,
) -> int:
    if status is WalkForwardExecutionStatus.QUEUED:
        return 0

    if status is WalkForwardExecutionStatus.SUCCEEDED:
        return 100

    return min(
        99,
        completed_folds * 100 // total_folds,
    )


class WalkForwardExecution(BaseModel):
    """Persistent state of one asynchronous walk-forward job."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(
        pattern=r"^walk-forward-job-[a-f0-9]{16}$",
    )

    created_at: datetime
    updated_at: datetime

    started_at: datetime | None = None
    finished_at: datetime | None = None

    status: WalkForwardExecutionStatus
    progress_percent: int = Field(ge=0, le=100)

    dataset_id: str = Field(min_length=1, max_length=100)
    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=30)

    parameters: StrategyExecutionParameters
    walk_forward_config: WalkForwardConfig

    total_folds: int = Field(ge=1)
    completed_folds: int = Field(ge=0)

    walk_forward_run_id: str | None = Field(
        default=None,
        pattern=r"^walk-forward-execution-[a-f0-9]{16}$",
    )

    error_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    error_message: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    @field_validator(
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("walk-forward execution timestamps must include timezone information")

        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_execution_state(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated time cannot be before created time")

        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started time cannot be before created time")

        if self.finished_at is not None and self.started_at is None:
            raise ValueError("finished execution must have a started time")

        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished time cannot be before started time")

        if self.completed_folds > self.total_folds:
            raise ValueError("completed folds cannot exceed total folds")

        expected_progress = _fold_progress_percent(
            status=self.status,
            completed_folds=self.completed_folds,
            total_folds=self.total_folds,
        )

        if self.progress_percent != expected_progress:
            raise ValueError("walk-forward execution progress must match completed folds")

        if self.status is WalkForwardExecutionStatus.QUEUED:
            self._validate_queued_state()

        elif self.status is WalkForwardExecutionStatus.RUNNING:
            self._validate_running_state()

        elif self.status is WalkForwardExecutionStatus.SUCCEEDED:
            self._validate_succeeded_state()

        else:
            self._validate_failed_state()

        return self

    def _validate_queued_state(self) -> None:
        if self.completed_folds != 0:
            raise ValueError("queued execution cannot have completed folds")

        if self.started_at is not None or self.finished_at is not None:
            raise ValueError("queued execution cannot have execution timestamps")

        if self.walk_forward_run_id is not None:
            raise ValueError("queued execution cannot reference a walk-forward run")

        if self.error_code is not None or self.error_message is not None:
            raise ValueError("queued execution cannot contain an error")

    def _validate_running_state(self) -> None:
        if self.started_at is None:
            raise ValueError("running execution must have a started time")

        if self.finished_at is not None:
            raise ValueError("running execution cannot have a finished time")

        if self.walk_forward_run_id is not None:
            raise ValueError("running execution cannot reference a walk-forward run")

        if self.error_code is not None or self.error_message is not None:
            raise ValueError("running execution cannot contain an error")

    def _validate_succeeded_state(self) -> None:
        if self.started_at is None or self.finished_at is None:
            raise ValueError("succeeded execution must have start and finish times")

        if self.completed_folds != self.total_folds:
            raise ValueError("succeeded execution must complete all folds")

        if self.walk_forward_run_id is None:
            raise ValueError("succeeded execution must reference a walk-forward run")

        if self.error_code is not None or self.error_message is not None:
            raise ValueError("succeeded execution cannot contain an error")

    def _validate_failed_state(self) -> None:
        if self.started_at is None or self.finished_at is None:
            raise ValueError("failed execution must have start and finish times")

        if self.walk_forward_run_id is not None:
            raise ValueError("failed execution cannot reference a walk-forward run")

        if self.error_code is None or self.error_message is None:
            raise ValueError("failed execution must contain an error")


class WalkForwardExecutionBuilder:
    """Create queued walk-forward jobs."""

    def build(
        self,
        *,
        dataset_id: str,
        parameters: StrategyExecutionParameters,
        walk_forward_config: WalkForwardConfig,
        total_folds: int,
        now: datetime | None = None,
    ) -> WalkForwardExecution:
        created_at = now or datetime.now(UTC)

        return WalkForwardExecution(
            execution_id=f"walk-forward-job-{uuid4().hex[:16]}",
            created_at=created_at,
            updated_at=created_at,
            status=WalkForwardExecutionStatus.QUEUED,
            progress_percent=0,
            dataset_id=dataset_id,
            strategy_name=parameters.strategy_name,
            strategy_version=parameters.strategy_version,
            parameters=parameters,
            walk_forward_config=walk_forward_config,
            total_folds=total_folds,
            completed_folds=0,
        )


class WalkForwardExecutionStateMachine:
    """Apply immutable walk-forward execution transitions."""

    def start(
        self,
        execution: WalkForwardExecution,
        *,
        now: datetime | None = None,
    ) -> WalkForwardExecution:
        self._require_status(
            execution,
            WalkForwardExecutionStatus.QUEUED,
        )

        started_at = now or datetime.now(UTC)

        return self._validated_copy(
            execution,
            status=WalkForwardExecutionStatus.RUNNING,
            started_at=started_at,
            updated_at=started_at,
        )

    def update_completed_folds(
        self,
        execution: WalkForwardExecution,
        *,
        completed_folds: int,
        now: datetime | None = None,
    ) -> WalkForwardExecution:
        self._require_status(
            execution,
            WalkForwardExecutionStatus.RUNNING,
        )

        if completed_folds < execution.completed_folds:
            raise ValueError("completed folds cannot move backwards")

        if completed_folds > execution.total_folds:
            raise ValueError("completed folds cannot exceed total folds")

        updated_at = now or datetime.now(UTC)

        return self._validated_copy(
            execution,
            completed_folds=completed_folds,
            progress_percent=_fold_progress_percent(
                status=WalkForwardExecutionStatus.RUNNING,
                completed_folds=completed_folds,
                total_folds=execution.total_folds,
            ),
            updated_at=updated_at,
        )

    def succeed(
        self,
        execution: WalkForwardExecution,
        *,
        walk_forward_run_id: str,
        now: datetime | None = None,
    ) -> WalkForwardExecution:
        self._require_status(
            execution,
            WalkForwardExecutionStatus.RUNNING,
        )

        if execution.completed_folds != execution.total_folds:
            raise ValueError("cannot succeed before all folds are completed")

        finished_at = now or datetime.now(UTC)

        return self._validated_copy(
            execution,
            status=WalkForwardExecutionStatus.SUCCEEDED,
            progress_percent=100,
            walk_forward_run_id=walk_forward_run_id,
            finished_at=finished_at,
            updated_at=finished_at,
        )

    def fail(
        self,
        execution: WalkForwardExecution,
        *,
        error_code: str,
        error_message: str,
        now: datetime | None = None,
    ) -> WalkForwardExecution:
        self._require_status(
            execution,
            WalkForwardExecutionStatus.RUNNING,
        )

        finished_at = now or datetime.now(UTC)

        return self._validated_copy(
            execution,
            status=WalkForwardExecutionStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            finished_at=finished_at,
            updated_at=finished_at,
        )

    @staticmethod
    def _validated_copy(
        execution: WalkForwardExecution,
        **updates: object,
    ) -> WalkForwardExecution:
        payload = execution.model_dump()
        payload.update(updates)

        return WalkForwardExecution.model_validate(payload)

    @staticmethod
    def _require_status(
        execution: WalkForwardExecution,
        expected_status: WalkForwardExecutionStatus,
    ) -> None:
        if execution.status is not expected_status:
            raise ValueError(
                "walk-forward execution must be "
                f"{expected_status.value} but is {execution.status.value}"
            )


class WalkForwardExecutionRepository(Protocol):
    """Persistence contract for walk-forward execution lifecycle state."""

    def save(
        self,
        execution: WalkForwardExecution,
    ) -> WalkForwardExecution:
        """Insert or update an execution."""

    def get(
        self,
        execution_id: str,
    ) -> WalkForwardExecution | None:
        """Return an execution by ID."""

    def count(self) -> int:
        """Return the number of stored executions."""

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardExecution, ...]:
        """Return executions ordered from newest to oldest."""


class InMemoryWalkForwardExecutionRepository:
    """Store walk-forward execution lifecycle state in memory."""

    def __init__(self) -> None:
        self._executions: dict[str, WalkForwardExecution] = {}

    def save(
        self,
        execution: WalkForwardExecution,
    ) -> WalkForwardExecution:
        self._executions[execution.execution_id] = execution

        return execution

    def get(
        self,
        execution_id: str,
    ) -> WalkForwardExecution | None:
        return self._executions.get(execution_id)

    def count(self) -> int:
        return len(self._executions)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardExecution, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        executions = sorted(
            self._executions.values(),
            key=lambda execution: (
                execution.created_at,
                execution.execution_id,
            ),
            reverse=True,
        )

        return tuple(executions[offset : offset + limit])
