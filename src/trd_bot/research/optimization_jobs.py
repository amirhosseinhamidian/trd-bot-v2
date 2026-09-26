import hashlib
import json
from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionRepository,
    OptimizationExecutionState,
)


class OptimizationExecutionJobPayload(BaseModel):
    """Version-one allowlisted payload for an optimization execution job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str = Field(pattern=r"^optimization-[a-f0-9]{16}$")


@dataclass(frozen=True)
class OptimizationExecutionEnqueueResult:
    """Execution and durable job committed as one submission."""

    execution: OptimizationExecution
    job: BackgroundJob
    created: bool


class OptimizationExecutionEnqueueError(RuntimeError):
    """Raised when an execution and its durable job cannot be committed atomically."""


class OptimizationExecutionEnqueuer(Protocol):
    def enqueue(
        self,
        *,
        execution: OptimizationExecution,
        job: BackgroundJob,
    ) -> OptimizationExecutionEnqueueResult: ...


def build_optimization_execution_idempotency_key(
    execution: OptimizationExecution,
) -> str:
    """Build a stable key from user-controlled execution intent."""

    payload = {
        "dataset_id": execution.dataset_id,
        "strategy_name": execution.strategy_name,
        "strategy_version": execution.strategy_version,
        "objective": execution.objective,
        "plan": execution.plan.model_dump(mode="json"),
        "horizon_candles": execution.horizon_candles,
        "backtest_config": execution.backtest_config.model_dump(mode="json"),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"optimization:{hashlib.sha256(encoded).hexdigest()}"


def validate_optimization_execution_enqueue(
    *,
    execution: OptimizationExecution,
    job: BackgroundJob,
) -> OptimizationExecutionJobPayload:
    """Validate invariants shared by persistent and in-memory enqueue operations."""

    if execution.status is not OptimizationExecutionState.QUEUED:
        raise ValueError("only queued optimization executions can be enqueued")
    if job.kind is not BackgroundJobKind.OPTIMIZATION_EXECUTION:
        raise ValueError("optimization execution requires an optimization background job")
    if job.status is not BackgroundJobStatus.QUEUED:
        raise ValueError("optimization background job must be queued")
    if job.idempotency_key is None:
        raise ValueError("optimization background job requires an idempotency key")

    payload = OptimizationExecutionJobPayload.model_validate(job.payload)
    if payload.execution_id != execution.execution_id:
        raise ValueError("optimization job payload does not reference its execution")
    expected_key = build_optimization_execution_idempotency_key(execution)
    if job.idempotency_key != expected_key:
        raise ValueError("optimization background job idempotency key is invalid")
    return payload


class InMemoryOptimizationExecutionEnqueuer:
    """Serialize idempotent enqueue operations for API tests and isolated use."""

    def __init__(self, executions: OptimizationExecutionRepository) -> None:
        self._executions = executions
        self._jobs_by_key: dict[str, BackgroundJob] = {}
        self._lock = RLock()

    def enqueue(
        self,
        *,
        execution: OptimizationExecution,
        job: BackgroundJob,
    ) -> OptimizationExecutionEnqueueResult:
        validate_optimization_execution_enqueue(execution=execution, job=job)
        assert job.idempotency_key is not None

        with self._lock:
            existing_job = self._jobs_by_key.get(job.idempotency_key)
            if existing_job is not None:
                payload = OptimizationExecutionJobPayload.model_validate(existing_job.payload)
                existing_execution = self._executions.get(payload.execution_id)
                if existing_execution is None:
                    raise OptimizationExecutionEnqueueError(
                        "optimization job exists without its execution"
                    )
                return OptimizationExecutionEnqueueResult(
                    execution=existing_execution,
                    job=existing_job,
                    created=False,
                )

            stored_execution = self._executions.save(execution)
            self._jobs_by_key[job.idempotency_key] = job
            return OptimizationExecutionEnqueueResult(
                execution=stored_execution,
                job=job,
                created=True,
            )
