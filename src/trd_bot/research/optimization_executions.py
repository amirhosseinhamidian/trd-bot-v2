from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.optimization import OptimizationPlan


class OptimizationExecutionState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OptimizationExecution(BaseModel):
    """Persistent lifecycle state for one bounded historical optimization."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(pattern=r"^optimization-[a-f0-9]{16}$")
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    status: OptimizationExecutionState
    dataset_id: str = Field(min_length=1, max_length=100)
    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=30)
    objective: ExperimentComparisonMetric
    plan: OptimizationPlan
    horizon_candles: int = Field(ge=1)
    backtest_config: BacktestConfig

    total_trials: int = Field(ge=1)
    completed_trials: int = Field(ge=0)
    experiment_ids: tuple[str, ...] = ()
    best_experiment_id: str | None = None

    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    error_message: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
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

        if self.plan.strategy_name != self.strategy_name:
            raise ValueError("optimization plan strategy name does not match execution")

        if self.plan.strategy_version != self.strategy_version:
            raise ValueError("optimization plan strategy version does not match execution")

        if self.plan.objective != self.objective:
            raise ValueError("optimization plan objective does not match execution")

        if self.total_trials != self.plan.total_trials:
            raise ValueError("optimization total trials must match the plan")

        if self.completed_trials != len(self.experiment_ids):
            raise ValueError("completed trial count must match stored experiment IDs")

        if self.completed_trials > self.total_trials:
            raise ValueError("completed trials cannot exceed total trials")

        if len(self.experiment_ids) != len(set(self.experiment_ids)):
            raise ValueError("optimization experiment IDs must be unique")

        if self.status is OptimizationExecutionState.QUEUED:
            self._validate_queued()
        elif self.status is OptimizationExecutionState.RUNNING:
            self._validate_running()
        elif self.status is OptimizationExecutionState.SUCCEEDED:
            self._validate_succeeded()
        else:
            self._validate_failed()

        return self

    def _validate_queued(self) -> None:
        if self.started_at is not None or self.finished_at is not None:
            raise ValueError("queued optimization cannot have execution timestamps")
        if self.completed_trials != 0 or self.experiment_ids:
            raise ValueError("queued optimization cannot contain completed trials")
        if self.best_experiment_id is not None:
            raise ValueError("queued optimization cannot contain a best experiment")
        if self.error_code is not None or self.error_message is not None:
            raise ValueError("queued optimization cannot contain an error")

    def _validate_running(self) -> None:
        if self.started_at is None or self.finished_at is not None:
            raise ValueError("running optimization must have only a started time")
        if self.best_experiment_id is not None:
            raise ValueError("running optimization cannot contain a best experiment")
        if self.error_code is not None or self.error_message is not None:
            raise ValueError("running optimization cannot contain an error")

    def _validate_succeeded(self) -> None:
        if self.started_at is None or self.finished_at is None:
            raise ValueError("succeeded optimization must have execution timestamps")
        if self.completed_trials != self.total_trials:
            raise ValueError("succeeded optimization must complete every trial")
        if self.best_experiment_id is None:
            raise ValueError("succeeded optimization requires a best experiment")
        if self.best_experiment_id not in self.experiment_ids:
            raise ValueError("best experiment must belong to the optimization")
        if self.error_code is not None or self.error_message is not None:
            raise ValueError("succeeded optimization cannot contain an error")

    def _validate_failed(self) -> None:
        if self.started_at is None or self.finished_at is None:
            raise ValueError("failed optimization must have execution timestamps")
        if self.best_experiment_id is not None:
            raise ValueError("failed optimization cannot contain a best experiment")
        if self.error_code is None or self.error_message is None:
            raise ValueError("failed optimization requires an error")


class OptimizationExecutionBuilder:
    """Build a queued optimization execution from a validated plan."""

    def build(
        self,
        *,
        dataset_id: str,
        plan: OptimizationPlan,
        horizon_candles: int,
        backtest_config: BacktestConfig,
        now: datetime | None = None,
    ) -> OptimizationExecution:
        created_at = now or datetime.now(UTC)

        return OptimizationExecution(
            execution_id=f"optimization-{uuid4().hex[:16]}",
            created_at=created_at,
            updated_at=created_at,
            status=OptimizationExecutionState.QUEUED,
            dataset_id=dataset_id,
            strategy_name=plan.strategy_name,
            strategy_version=plan.strategy_version,
            objective=plan.objective,
            plan=plan,
            horizon_candles=horizon_candles,
            backtest_config=backtest_config,
            total_trials=plan.total_trials,
            completed_trials=0,
        )


class OptimizationExecutionStateMachine:
    """Apply validated immutable optimization lifecycle transitions."""

    def start(
        self,
        execution: OptimizationExecution,
        *,
        now: datetime | None = None,
    ) -> OptimizationExecution:
        self._require_status(execution, OptimizationExecutionState.QUEUED)
        started_at = now or datetime.now(UTC)
        return self._validated_copy(
            execution,
            status=OptimizationExecutionState.RUNNING,
            started_at=started_at,
            updated_at=started_at,
        )

    def record_trial(
        self,
        execution: OptimizationExecution,
        *,
        experiment_id: str,
        now: datetime | None = None,
    ) -> OptimizationExecution:
        self._require_status(execution, OptimizationExecutionState.RUNNING)

        if experiment_id in execution.experiment_ids:
            raise ValueError("optimization experiment is already recorded")

        if execution.completed_trials >= execution.total_trials:
            raise ValueError("optimization has already completed every trial")

        updated_at = now or datetime.now(UTC)
        experiment_ids = (*execution.experiment_ids, experiment_id)

        return self._validated_copy(
            execution,
            completed_trials=len(experiment_ids),
            experiment_ids=experiment_ids,
            updated_at=updated_at,
        )

    def succeed(
        self,
        execution: OptimizationExecution,
        *,
        best_experiment_id: str,
        now: datetime | None = None,
    ) -> OptimizationExecution:
        self._require_status(execution, OptimizationExecutionState.RUNNING)
        finished_at = now or datetime.now(UTC)
        return self._validated_copy(
            execution,
            status=OptimizationExecutionState.SUCCEEDED,
            best_experiment_id=best_experiment_id,
            finished_at=finished_at,
            updated_at=finished_at,
        )

    def fail(
        self,
        execution: OptimizationExecution,
        *,
        error_code: str,
        error_message: str,
        now: datetime | None = None,
    ) -> OptimizationExecution:
        self._require_status(execution, OptimizationExecutionState.RUNNING)
        finished_at = now or datetime.now(UTC)
        return self._validated_copy(
            execution,
            status=OptimizationExecutionState.FAILED,
            error_code=error_code,
            error_message=error_message,
            finished_at=finished_at,
            updated_at=finished_at,
        )

    @staticmethod
    def _validated_copy(
        execution: OptimizationExecution,
        **updates: object,
    ) -> OptimizationExecution:
        payload = execution.model_dump()
        payload.update(updates)
        return OptimizationExecution.model_validate(payload)

    @staticmethod
    def _require_status(
        execution: OptimizationExecution,
        expected: OptimizationExecutionState,
    ) -> None:
        if execution.status is not expected:
            raise ValueError(
                f"optimization execution must be {expected.value} but is {execution.status.value}"
            )


class OptimizationExecutionRepository(Protocol):
    def save(self, execution: OptimizationExecution) -> OptimizationExecution: ...

    def get(self, execution_id: str) -> OptimizationExecution | None: ...

    def count(self) -> int: ...

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[OptimizationExecution, ...]: ...


class InMemoryOptimizationExecutionRepository:
    def __init__(self) -> None:
        self._items: dict[str, OptimizationExecution] = {}

    def save(self, execution: OptimizationExecution) -> OptimizationExecution:
        self._items[execution.execution_id] = execution
        return execution

    def get(self, execution_id: str) -> OptimizationExecution | None:
        return self._items.get(execution_id)

    def count(self) -> int:
        return len(self._items)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[OptimizationExecution, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        ordered = sorted(
            self._items.values(),
            key=lambda item: (item.created_at, item.execution_id),
            reverse=True,
        )
        return tuple(ordered[offset : offset + limit])
