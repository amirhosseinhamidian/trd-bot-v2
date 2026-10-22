import hashlib
import json
from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from trd_bot.research.experiment_executions import (
    ExperimentExecution,
    ExperimentExecutionRepository,
    ExperimentExecutionStatus,
)


class ExperimentExecutionJobPayload(BaseModel):
    """Version-one allowlisted payload for a durable experiment execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str = Field(pattern=r"^execution-[a-f0-9]{16}$")


@dataclass(frozen=True)
class ExperimentExecutionEnqueueResult:
    """Experiment execution and durable job committed as one submission."""

    execution: ExperimentExecution
    job: BackgroundJob
    created: bool


class ExperimentExecutionEnqueueError(RuntimeError):
    """Raised when an execution and job cannot be committed atomically."""


class ExperimentExecutionEnqueuer(Protocol):
    def enqueue(
        self,
        *,
        execution: ExperimentExecution,
        job: BackgroundJob,
    ) -> ExperimentExecutionEnqueueResult: ...


def build_experiment_execution_idempotency_key(execution: ExperimentExecution) -> str:
    """Build a stable key from the complete user-controlled execution intent."""

    intent = {
        "dataset_id": execution.dataset_id,
        "strategy_name": execution.strategy_name,
        "strategy_version": execution.strategy_version,
        "parameters": execution.parameters.model_dump(mode="json"),
    }
    encoded = json.dumps(
        intent,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"experiment-execution:{hashlib.sha256(encoded).hexdigest()}"


def validate_experiment_execution_enqueue(
    *,
    execution: ExperimentExecution,
    job: BackgroundJob,
) -> ExperimentExecutionJobPayload:
    if execution.status is not ExperimentExecutionStatus.QUEUED:
        raise ValueError("only queued experiment executions can be enqueued")
    if job.kind is not BackgroundJobKind.EXPERIMENT_EXECUTION:
        raise ValueError("experiment execution requires an experiment background job")
    if job.status is not BackgroundJobStatus.QUEUED:
        raise ValueError("experiment background job must be queued")
    if job.idempotency_key is None:
        raise ValueError("experiment background job requires an idempotency key")

    payload = ExperimentExecutionJobPayload.model_validate(job.payload)
    if payload.execution_id != execution.execution_id:
        raise ValueError("experiment job payload does not reference its execution")
    if job.idempotency_key != build_experiment_execution_idempotency_key(execution):
        raise ValueError("experiment background job idempotency key is invalid")
    return payload


class InMemoryExperimentExecutionEnqueuer:
    """Serialize idempotent experiment submissions for isolated API tests."""

    def __init__(self, executions: ExperimentExecutionRepository) -> None:
        self._executions = executions
        self.jobs_by_key: dict[str, BackgroundJob] = {}
        self._lock = RLock()

    def enqueue(
        self,
        *,
        execution: ExperimentExecution,
        job: BackgroundJob,
    ) -> ExperimentExecutionEnqueueResult:
        validate_experiment_execution_enqueue(execution=execution, job=job)
        assert job.idempotency_key is not None

        with self._lock:
            existing_job = self.jobs_by_key.get(job.idempotency_key)
            if existing_job is not None:
                payload = ExperimentExecutionJobPayload.model_validate(existing_job.payload)
                existing_execution = self._executions.get(payload.execution_id)
                if existing_execution is None:
                    raise ExperimentExecutionEnqueueError(
                        "experiment job exists without its execution"
                    )
                return ExperimentExecutionEnqueueResult(
                    execution=existing_execution,
                    job=existing_job,
                    created=False,
                )

            if self._executions.get(execution.execution_id) is not None:
                raise ExperimentExecutionEnqueueError("experiment execution ID already exists")
            stored_execution = self._executions.save(execution)
            self.jobs_by_key[job.idempotency_key] = job
            return ExperimentExecutionEnqueueResult(
                execution=stored_execution,
                job=job,
                created=True,
            )
