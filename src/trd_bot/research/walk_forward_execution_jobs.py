import hashlib
import json
from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from trd_bot.research.walk_forward_executions import (
    WalkForwardExecution,
    WalkForwardExecutionRepository,
    WalkForwardExecutionStatus,
)


class WalkForwardExecutionJobPayload(BaseModel):
    """Version-one allowlisted payload for a durable walk-forward execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str = Field(pattern=r"^walk-forward-job-[a-f0-9]{16}$")


@dataclass(frozen=True)
class WalkForwardExecutionEnqueueResult:
    """Walk-forward execution and durable job committed as one submission."""

    execution: WalkForwardExecution
    job: BackgroundJob
    created: bool


class WalkForwardExecutionEnqueueError(RuntimeError):
    """Raised when an execution and job cannot be committed atomically."""


class WalkForwardExecutionEnqueuer(Protocol):
    def enqueue(
        self,
        *,
        execution: WalkForwardExecution,
        job: BackgroundJob,
    ) -> WalkForwardExecutionEnqueueResult: ...


def build_walk_forward_execution_idempotency_key(execution: WalkForwardExecution) -> str:
    """Build a stable key from the complete user-controlled execution intent."""

    intent = {
        "dataset_id": execution.dataset_id,
        "strategy_name": execution.strategy_name,
        "strategy_version": execution.strategy_version,
        "parameters": execution.parameters.model_dump(mode="json"),
        "walk_forward_config": execution.walk_forward_config.model_dump(mode="json"),
        "total_folds": execution.total_folds,
    }
    encoded = json.dumps(
        intent,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"walk-forward-execution:{hashlib.sha256(encoded).hexdigest()}"


def validate_walk_forward_execution_enqueue(
    *,
    execution: WalkForwardExecution,
    job: BackgroundJob,
) -> WalkForwardExecutionJobPayload:
    if execution.status is not WalkForwardExecutionStatus.QUEUED:
        raise ValueError("only queued walk-forward executions can be enqueued")
    if job.kind is not BackgroundJobKind.WALK_FORWARD_EXECUTION:
        raise ValueError("walk-forward execution requires a walk-forward background job")
    if job.status is not BackgroundJobStatus.QUEUED:
        raise ValueError("walk-forward background job must be queued")
    if job.idempotency_key is None:
        raise ValueError("walk-forward background job requires an idempotency key")

    payload = WalkForwardExecutionJobPayload.model_validate(job.payload)
    if payload.execution_id != execution.execution_id:
        raise ValueError("walk-forward job payload does not reference its execution")
    if job.idempotency_key != build_walk_forward_execution_idempotency_key(execution):
        raise ValueError("walk-forward background job idempotency key is invalid")
    return payload


class InMemoryWalkForwardExecutionEnqueuer:
    """Serialize idempotent walk-forward submissions for isolated API tests."""

    def __init__(self, executions: WalkForwardExecutionRepository) -> None:
        self._executions = executions
        self.jobs_by_key: dict[str, BackgroundJob] = {}
        self._lock = RLock()

    def enqueue(
        self,
        *,
        execution: WalkForwardExecution,
        job: BackgroundJob,
    ) -> WalkForwardExecutionEnqueueResult:
        validate_walk_forward_execution_enqueue(execution=execution, job=job)
        assert job.idempotency_key is not None

        with self._lock:
            existing_job = self.jobs_by_key.get(job.idempotency_key)
            if existing_job is not None:
                payload = WalkForwardExecutionJobPayload.model_validate(existing_job.payload)
                existing_execution = self._executions.get(payload.execution_id)
                if existing_execution is None:
                    raise WalkForwardExecutionEnqueueError(
                        "walk-forward job exists without its execution"
                    )
                return WalkForwardExecutionEnqueueResult(
                    execution=existing_execution,
                    job=existing_job,
                    created=False,
                )

            if self._executions.get(execution.execution_id) is not None:
                raise WalkForwardExecutionEnqueueError("walk-forward execution ID already exists")
            stored_execution = self._executions.save(execution)
            self.jobs_by_key[job.idempotency_key] = job
            return WalkForwardExecutionEnqueueResult(
                execution=stored_execution,
                job=job,
                created=True,
            )
