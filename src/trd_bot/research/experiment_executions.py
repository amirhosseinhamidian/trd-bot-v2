from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExperimentExecutionStatus(StrEnum):
    """Persistent lifecycle state of an experiment execution."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EMACrossoverExecutionParameters(BaseModel):
    """Reproducible input parameters for one stored-dataset EMA execution."""

    model_config = ConfigDict(frozen=True)

    fast_period: int = Field(ge=1)
    slow_period: int = Field(ge=2)
    horizon_candles: int = Field(ge=1)

    starting_balance: Decimal = Field(gt=0)
    allocation_fraction: Decimal = Field(gt=0, le=1)
    fee_rate: Decimal = Field(ge=0, lt=1)
    slippage_rate: Decimal = Field(ge=0, lt=1)

    @model_validator(mode="after")
    def validate_period_relationship(self) -> Self:
        if self.fast_period >= self.slow_period:
            raise ValueError("fast period must be smaller than slow period")

        return self


class ExperimentExecution(BaseModel):
    """Persistent state of one historical research execution."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(
        pattern=r"^execution-[a-f0-9]{16}$",
    )

    created_at: datetime
    updated_at: datetime

    started_at: datetime | None = None
    finished_at: datetime | None = None

    status: ExperimentExecutionStatus
    progress_percent: int = Field(ge=0, le=100)

    dataset_id: str = Field(min_length=1, max_length=100)
    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=30)

    parameters: EMACrossoverExecutionParameters

    experiment_id: str | None = Field(
        default=None,
        pattern=r"^experiment-[a-f0-9]{16}$",
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
            raise ValueError("execution timestamps must include timezone information")

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

        if self.status is ExperimentExecutionStatus.QUEUED:
            self._validate_queued_state()

        elif self.status is ExperimentExecutionStatus.RUNNING:
            self._validate_running_state()

        elif self.status is ExperimentExecutionStatus.SUCCEEDED:
            self._validate_succeeded_state()

        else:
            self._validate_failed_state()

        return self

    def _validate_queued_state(self) -> None:
        if self.progress_percent != 0:
            raise ValueError("queued execution progress must be zero")

        if self.started_at is not None or self.finished_at is not None:
            raise ValueError("queued execution cannot have execution timestamps")

        if self.experiment_id is not None:
            raise ValueError("queued execution cannot reference an experiment")

        if self.error_code is not None or self.error_message is not None:
            raise ValueError("queued execution cannot contain an error")

    def _validate_running_state(self) -> None:
        if self.started_at is None:
            raise ValueError("running execution must have a started time")

        if self.finished_at is not None:
            raise ValueError("running execution cannot have a finished time")

        if not 1 <= self.progress_percent <= 99:
            raise ValueError("running execution progress must be between 1 and 99")

        if self.experiment_id is not None:
            raise ValueError("running execution cannot reference an experiment")

        if self.error_code is not None or self.error_message is not None:
            raise ValueError("running execution cannot contain an error")

    def _validate_succeeded_state(self) -> None:
        if self.started_at is None or self.finished_at is None:
            raise ValueError("succeeded execution must have start and finish times")

        if self.progress_percent != 100:
            raise ValueError("succeeded execution progress must be 100")

        if self.experiment_id is None:
            raise ValueError("succeeded execution must reference an experiment")

        if self.error_code is not None or self.error_message is not None:
            raise ValueError("succeeded execution cannot contain an error")

    def _validate_failed_state(self) -> None:
        if self.started_at is None or self.finished_at is None:
            raise ValueError("failed execution must have start and finish times")

        if self.progress_percent >= 100:
            raise ValueError("failed execution progress must be smaller than 100")

        if self.experiment_id is not None:
            raise ValueError("failed execution cannot reference an experiment")

        if self.error_code is None or self.error_message is None:
            raise ValueError("failed execution must contain an error")


class ExperimentExecutionBuilder:
    """Create queued experiment executions."""

    def build(
        self,
        *,
        dataset_id: str,
        parameters: EMACrossoverExecutionParameters,
        now: datetime | None = None,
    ) -> ExperimentExecution:
        created_at = now or datetime.now(UTC)

        return ExperimentExecution(
            execution_id=f"execution-{uuid4().hex[:16]}",
            created_at=created_at,
            updated_at=created_at,
            status=ExperimentExecutionStatus.QUEUED,
            progress_percent=0,
            dataset_id=dataset_id,
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            parameters=parameters,
        )


class ExperimentExecutionStateMachine:
    """Apply valid immutable execution-state transitions."""

    def start(
        self,
        execution: ExperimentExecution,
        *,
        now: datetime | None = None,
    ) -> ExperimentExecution:
        self._require_status(
            execution,
            ExperimentExecutionStatus.QUEUED,
        )

        started_at = now or datetime.now(UTC)

        return self._validated_copy(
            execution,
            status=ExperimentExecutionStatus.RUNNING,
            progress_percent=1,
            started_at=started_at,
            updated_at=started_at,
        )

    def update_progress(
        self,
        execution: ExperimentExecution,
        *,
        progress_percent: int,
        now: datetime | None = None,
    ) -> ExperimentExecution:
        self._require_status(
            execution,
            ExperimentExecutionStatus.RUNNING,
        )

        if not 1 <= progress_percent <= 99:
            raise ValueError("running progress must be between 1 and 99")

        if progress_percent < execution.progress_percent:
            raise ValueError("execution progress cannot move backwards")

        updated_at = now or datetime.now(UTC)

        return self._validated_copy(
            execution,
            progress_percent=progress_percent,
            updated_at=updated_at,
        )

    def succeed(
        self,
        execution: ExperimentExecution,
        *,
        experiment_id: str,
        now: datetime | None = None,
    ) -> ExperimentExecution:
        self._require_status(
            execution,
            ExperimentExecutionStatus.RUNNING,
        )

        finished_at = now or datetime.now(UTC)

        return self._validated_copy(
            execution,
            status=ExperimentExecutionStatus.SUCCEEDED,
            progress_percent=100,
            experiment_id=experiment_id,
            finished_at=finished_at,
            updated_at=finished_at,
        )

    def fail(
        self,
        execution: ExperimentExecution,
        *,
        error_code: str,
        error_message: str,
        now: datetime | None = None,
    ) -> ExperimentExecution:
        self._require_status(
            execution,
            ExperimentExecutionStatus.RUNNING,
        )

        finished_at = now or datetime.now(UTC)

        return self._validated_copy(
            execution,
            status=ExperimentExecutionStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            finished_at=finished_at,
            updated_at=finished_at,
        )

    @staticmethod
    def _validated_copy(
        execution: ExperimentExecution,
        **updates: object,
    ) -> ExperimentExecution:
        payload = execution.model_dump()
        payload.update(updates)

        return ExperimentExecution.model_validate(payload)

    @staticmethod
    def _require_status(
        execution: ExperimentExecution,
        expected_status: ExperimentExecutionStatus,
    ) -> None:
        if execution.status is not expected_status:
            raise ValueError(
                f"execution must be {expected_status.value} but is {execution.status.value}"
            )


class ExperimentExecutionRepository(Protocol):
    """Persistence contract for experiment executions."""

    def save(
        self,
        execution: ExperimentExecution,
    ) -> ExperimentExecution:
        """Insert or update an execution."""

    def get(
        self,
        execution_id: str,
    ) -> ExperimentExecution | None:
        """Return an execution by ID."""

    def count(self) -> int:
        """Return the number of stored executions."""

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[ExperimentExecution, ...]:
        """Return executions ordered from newest to oldest."""


class InMemoryExperimentExecutionRepository:
    """Store experiment executions in memory."""

    def __init__(self) -> None:
        self._executions: dict[str, ExperimentExecution] = {}

    def save(
        self,
        execution: ExperimentExecution,
    ) -> ExperimentExecution:
        self._executions[execution.execution_id] = execution

        return execution

    def get(
        self,
        execution_id: str,
    ) -> ExperimentExecution | None:
        return self._executions.get(execution_id)

    def count(self) -> int:
        return len(self._executions)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[ExperimentExecution, ...]:
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        executions = sorted(
            self._executions.values(),
            key=lambda execution: (
                execution.created_at,
                execution.execution_id,
            ),
            reverse=True,
        )

        return tuple(executions[offset : offset + limit])

    @staticmethod
    def _validate_pagination(
        *,
        limit: int,
        offset: int,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")
