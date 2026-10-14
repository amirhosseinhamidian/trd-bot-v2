from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BackgroundJobKind(StrEnum):
    """Allowlisted durable work types; arbitrary callables are never persisted."""

    EXPERIMENT_EXECUTION = "experiment_execution"
    WALK_FORWARD_EXECUTION = "walk_forward_execution"
    MARKET_DATA_IMPORT = "market_data_import"
    MARKET_DATA_POLL = "market_data_poll"
    MARKET_DATA_REPLAY = "market_data_replay"
    DATASET_FILE_IMPORT = "dataset_file_import"
    OPTIMIZATION_EXECUTION = "optimization_execution"


class BackgroundJobCancellationMode(StrEnum):
    """Cancellation behavior promised by one allowlisted workload."""

    COOPERATIVE = "cooperative"


MAX_BACKGROUND_JOB_ATTEMPTS = 10
DEFAULT_BACKGROUND_JOB_LEASE_DURATION = timedelta(minutes=5)


@dataclass(frozen=True)
class BackgroundJobPolicy:
    """Central execution policy for one production background workload."""

    kind: BackgroundJobKind
    max_attempts: int
    retry_delays: tuple[timedelta, ...]
    lease_duration: timedelta = DEFAULT_BACKGROUND_JOB_LEASE_DURATION
    cancellation_mode: BackgroundJobCancellationMode = BackgroundJobCancellationMode.COOPERATIVE
    supported_payload_versions: frozenset[int] = frozenset({1})

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= MAX_BACKGROUND_JOB_ATTEMPTS:
            raise ValueError("background job policy attempt budget is invalid")
        if self.lease_duration <= timedelta(0):
            raise ValueError("background job policy lease duration must be positive")
        if len(self.retry_delays) != self.max_attempts - 1:
            raise ValueError("background job policy requires one delay per automatic retry")
        if any(delay < timedelta(0) for delay in self.retry_delays):
            raise ValueError("background job policy retry delays cannot be negative")
        if not self.supported_payload_versions or any(
            version < 1 for version in self.supported_payload_versions
        ):
            raise ValueError("background job policy payload versions are invalid")

    def retry_delay_after(self, attempt_count: int) -> timedelta:
        """Return the delay before the next automatic attempt."""

        if attempt_count < 1:
            raise ValueError("background job retry requires a completed attempt")
        if attempt_count >= self.max_attempts:
            return timedelta(0)
        return self.retry_delays[attempt_count - 1]


_STANDARD_RETRY_DELAYS = (timedelta(seconds=5), timedelta(seconds=30))
BACKGROUND_JOB_POLICIES: Mapping[BackgroundJobKind, BackgroundJobPolicy] = MappingProxyType(
    {
        BackgroundJobKind.EXPERIMENT_EXECUTION: BackgroundJobPolicy(
            kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
            max_attempts=3,
            retry_delays=_STANDARD_RETRY_DELAYS,
        ),
        BackgroundJobKind.WALK_FORWARD_EXECUTION: BackgroundJobPolicy(
            kind=BackgroundJobKind.WALK_FORWARD_EXECUTION,
            max_attempts=3,
            retry_delays=_STANDARD_RETRY_DELAYS,
        ),
        BackgroundJobKind.MARKET_DATA_IMPORT: BackgroundJobPolicy(
            kind=BackgroundJobKind.MARKET_DATA_IMPORT,
            max_attempts=1,
            retry_delays=(),
        ),
        BackgroundJobKind.MARKET_DATA_POLL: BackgroundJobPolicy(
            kind=BackgroundJobKind.MARKET_DATA_POLL,
            max_attempts=3,
            retry_delays=_STANDARD_RETRY_DELAYS,
        ),
        BackgroundJobKind.MARKET_DATA_REPLAY: BackgroundJobPolicy(
            kind=BackgroundJobKind.MARKET_DATA_REPLAY,
            max_attempts=3,
            retry_delays=_STANDARD_RETRY_DELAYS,
        ),
        BackgroundJobKind.DATASET_FILE_IMPORT: BackgroundJobPolicy(
            kind=BackgroundJobKind.DATASET_FILE_IMPORT,
            max_attempts=3,
            retry_delays=_STANDARD_RETRY_DELAYS,
        ),
        BackgroundJobKind.OPTIMIZATION_EXECUTION: BackgroundJobPolicy(
            kind=BackgroundJobKind.OPTIMIZATION_EXECUTION,
            max_attempts=3,
            retry_delays=_STANDARD_RETRY_DELAYS,
        ),
    }
)
PRODUCTION_BACKGROUND_JOB_KINDS = frozenset(BACKGROUND_JOB_POLICIES)
if frozenset(BackgroundJobKind) != PRODUCTION_BACKGROUND_JOB_KINDS:
    raise RuntimeError("background job policy catalog must cover every allowlisted kind")


def get_background_job_policy(kind: BackgroundJobKind) -> BackgroundJobPolicy:
    """Return the frozen production policy for an allowlisted kind."""

    try:
        return BACKGROUND_JOB_POLICIES[kind]
    except KeyError as error:
        raise LookupError(f'background job kind "{kind.value}" has no execution policy') from error


class BackgroundJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_JOB_STATUSES = frozenset(
    {
        BackgroundJobStatus.SUCCEEDED,
        BackgroundJobStatus.FAILED,
        BackgroundJobStatus.CANCELLED,
    }
)


class BackgroundJobConflictError(RuntimeError):
    """Raised when a worker no longer owns the lease it is trying to mutate."""


class BackgroundJobHandlerError(RuntimeError):
    """A sanitized handler failure with an explicit retry policy."""

    def __init__(
        self,
        *,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> None:
        if not error_code.strip() or not error_message.strip():
            raise ValueError("background job handler error requires code and message")
        self.error_code = error_code.strip()
        self.error_message = error_message.strip()
        self.retryable = retryable
        super().__init__(self.error_message)


class BackgroundJob(BaseModel):
    """Persisted lifecycle and lease state for one bounded background operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str = Field(pattern=r"^job-[a-f0-9]{20}$")
    kind: BackgroundJobKind
    payload_version: int = Field(default=1, ge=1)
    payload: dict[str, object]
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)

    status: BackgroundJobStatus
    progress_percent: int = Field(ge=0, le=100)
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1, le=MAX_BACKGROUND_JOB_ATTEMPTS)
    run_after: datetime

    lease_owner: str | None = Field(default=None, min_length=1, max_length=100)
    lease_expires_at: datetime | None = None
    cancel_requested: bool = False

    result_reference: str | None = Field(default=None, min_length=1, max_length=200)
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    error_message: str | None = Field(default=None, min_length=1, max_length=500)

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator(
        "run_after",
        "lease_expires_at",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    )
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("background job timestamps must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.updated_at < self.created_at or self.run_after < self.created_at:
            raise ValueError("background job timestamps are inconsistent")
        if (self.lease_owner is None) != (self.lease_expires_at is None):
            raise ValueError("background job lease owner and expiry must be recorded together")
        if self.attempt_count > self.max_attempts:
            raise ValueError("background job attempts cannot exceed the configured maximum")

        if self.status is BackgroundJobStatus.QUEUED:
            if self.lease_owner is not None or self.finished_at is not None:
                raise ValueError("queued background job cannot have a lease or finish time")
            if (
                self.result_reference is not None
                or self.error_code is not None
                or self.error_message is not None
            ):
                raise ValueError("queued background job cannot contain an outcome")
        elif self.status is BackgroundJobStatus.RUNNING:
            if self.lease_owner is None or self.started_at is None or self.finished_at is not None:
                raise ValueError("running background job requires an active lease and start time")
            if self.attempt_count < 1 or self.progress_percent >= 100:
                raise ValueError("running background job attempt and progress are invalid")
            if (
                self.result_reference is not None
                or self.error_code is not None
                or self.error_message is not None
            ):
                raise ValueError("running background job cannot contain an outcome")
        else:
            if self.finished_at is None or self.lease_owner is not None:
                raise ValueError("terminal background job requires finish time and no lease")
            if self.status is BackgroundJobStatus.SUCCEEDED:
                if (
                    self.progress_percent != 100
                    or self.error_code is not None
                    or self.error_message is not None
                ):
                    raise ValueError("succeeded background job outcome is inconsistent")
            elif self.status is BackgroundJobStatus.FAILED:
                if (
                    self.result_reference is not None
                    or self.error_code is None
                    or self.error_message is None
                ):
                    raise ValueError("failed background job requires an error")
            elif (
                self.result_reference is not None
                or self.error_code is not None
                or self.error_message is not None
            ):
                raise ValueError("cancelled background job cannot contain an outcome")
        return self

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_JOB_STATUSES


class BackgroundJobSummary(BaseModel):
    """Operator-safe job state that never exposes the persisted payload or worker ID."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    kind: BackgroundJobKind
    status: BackgroundJobStatus
    progress_percent: int
    attempt_count: int
    max_attempts: int
    run_after: datetime
    lease_expires_at: datetime | None
    cancel_requested: bool
    result_reference: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_job(cls, job: BackgroundJob) -> Self:
        return cls.model_validate(
            job.model_dump(
                exclude={
                    "payload_version",
                    "payload",
                    "idempotency_key",
                    "lease_owner",
                }
            )
        )


class BackgroundJobBuilder:
    def build(
        self,
        *,
        kind: BackgroundJobKind,
        payload: Mapping[str, object],
        idempotency_key: str | None = None,
        max_attempts: int | None = None,
        run_after: datetime | None = None,
        now: datetime | None = None,
    ) -> BackgroundJob:
        created_at = now or datetime.now(UTC)
        attempt_budget = (
            get_background_job_policy(kind).max_attempts if max_attempts is None else max_attempts
        )
        return BackgroundJob(
            job_id=f"job-{uuid4().hex[:20]}",
            kind=kind,
            payload=dict(payload),
            idempotency_key=idempotency_key,
            status=BackgroundJobStatus.QUEUED,
            progress_percent=0,
            attempt_count=0,
            max_attempts=attempt_budget,
            run_after=run_after or created_at,
            created_at=created_at,
            updated_at=created_at,
        )


class BackgroundJobRepository(Protocol):
    def enqueue(self, job: BackgroundJob) -> tuple[BackgroundJob, bool]: ...
    def get(self, job_id: str) -> BackgroundJob | None: ...
    def count(self, *, statuses: Sequence[BackgroundJobStatus] | None = None) -> int: ...
    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        statuses: Sequence[BackgroundJobStatus] | None = None,
    ) -> tuple[BackgroundJob, ...]: ...
    def claim_next(
        self,
        *,
        worker_id: str,
        lease_duration: timedelta,
        now: datetime | None = None,
    ) -> BackgroundJob | None: ...
    def heartbeat(
        self,
        *,
        job_id: str,
        worker_id: str,
        progress_percent: int,
        lease_duration: timedelta,
        now: datetime | None = None,
    ) -> BackgroundJob: ...
    def succeed(
        self,
        *,
        job_id: str,
        worker_id: str,
        result_reference: str | None = None,
        now: datetime | None = None,
    ) -> BackgroundJob: ...
    def fail(
        self,
        *,
        job_id: str,
        worker_id: str,
        error_code: str,
        error_message: str,
        retryable: bool,
        retry_delay: timedelta | None = None,
        now: datetime | None = None,
    ) -> BackgroundJob: ...
    def request_cancel(self, job_id: str, *, now: datetime | None = None) -> BackgroundJob: ...
    def retry_failed(self, job_id: str, *, now: datetime | None = None) -> BackgroundJob: ...


class BackgroundJobContext:
    """Lease-scoped controls exposed to allowlisted job handlers."""

    def __init__(
        self,
        repository: BackgroundJobRepository,
        job: BackgroundJob,
        worker_id: str,
        lease_duration: timedelta,
    ):
        self._repository = repository
        self.job = job
        self.worker_id = worker_id
        self.lease_duration = lease_duration

    def heartbeat(
        self,
        progress_percent: int,
        *,
        now: datetime | None = None,
    ) -> BackgroundJob:
        self.job = self._repository.heartbeat(
            job_id=self.job.job_id,
            worker_id=self.worker_id,
            progress_percent=progress_percent,
            lease_duration=self.lease_duration,
            now=now,
        )
        return self.job

    def cancellation_requested(self) -> bool:
        current = self._repository.get(self.job.job_id)
        return current is not None and current.cancel_requested


BackgroundJobHandler = Callable[[BackgroundJobContext, Mapping[str, object]], str | None]


class BackgroundJobHandlerRegistry:
    def __init__(self, handlers: Mapping[BackgroundJobKind, BackgroundJobHandler] | None = None):
        self._handlers = dict(handlers or {})

    def register(self, kind: BackgroundJobKind, handler: BackgroundJobHandler) -> None:
        if kind in self._handlers:
            raise ValueError(f'background job handler "{kind.value}" is already registered')
        self._handlers[kind] = handler

    def get(self, kind: BackgroundJobKind) -> BackgroundJobHandler:
        try:
            return self._handlers[kind]
        except KeyError as error:
            raise LookupError(f'background job handler "{kind.value}" is not registered') from error

    @property
    def kinds(self) -> frozenset[BackgroundJobKind]:
        return frozenset(self._handlers)

    def require_exact_allowlist(self, allowed_kinds: frozenset[BackgroundJobKind]) -> None:
        if self.kinds != allowed_kinds:
            missing = sorted(kind.value for kind in allowed_kinds - self.kinds)
            unexpected = sorted(kind.value for kind in self.kinds - allowed_kinds)
            raise ValueError(
                "background job handler allowlist does not match policy catalog: "
                f"missing={missing}, unexpected={unexpected}"
            )


class BackgroundJobWorker:
    """Claim and execute at most one durable job."""

    def __init__(
        self,
        *,
        repository: BackgroundJobRepository,
        handlers: BackgroundJobHandlerRegistry,
        worker_id: str,
        lease_duration: timedelta = DEFAULT_BACKGROUND_JOB_LEASE_DURATION,
    ) -> None:
        if lease_duration <= timedelta(0):
            raise ValueError("background job lease duration must be positive")
        self._repository = repository
        self._handlers = handlers
        self._worker_id = worker_id
        self._lease_duration = lease_duration

    def run_once(self, *, now: datetime | None = None) -> BackgroundJob | None:
        job = self._repository.claim_next(
            worker_id=self._worker_id,
            lease_duration=self._lease_duration,
            now=now,
        )
        if job is None:
            return None
        if job.cancel_requested:
            return self._repository.request_cancel(job.job_id, now=now)

        context = BackgroundJobContext(
            self._repository,
            job,
            self._worker_id,
            self._lease_duration,
        )
        try:
            policy = get_background_job_policy(job.kind)
            if job.payload_version not in policy.supported_payload_versions:
                return self._repository.fail(
                    job_id=job.job_id,
                    worker_id=self._worker_id,
                    error_code="unsupported_job_payload_version",
                    error_message="background job payload version is not supported",
                    retryable=False,
                    now=now,
                )
            try:
                handler = self._handlers.get(job.kind)
            except LookupError:
                return self._repository.fail(
                    job_id=job.job_id,
                    worker_id=self._worker_id,
                    error_code="unsupported_job_kind",
                    error_message="background job kind has no registered handler",
                    retryable=False,
                    now=now,
                )
            try:
                result_reference = handler(context, job.payload)
                if result_reference is not None and not 1 <= len(result_reference) <= 200:
                    raise ValueError("background job result reference is invalid")
            except BackgroundJobHandlerError as error:
                return self._repository.fail(
                    job_id=job.job_id,
                    worker_id=self._worker_id,
                    error_code=error.error_code,
                    error_message=error.error_message,
                    retryable=error.retryable,
                    retry_delay=(
                        policy.retry_delay_after(job.attempt_count) if error.retryable else None
                    ),
                    now=now,
                )
            except Exception:
                return self._repository.fail(
                    job_id=job.job_id,
                    worker_id=self._worker_id,
                    error_code="job_handler_failed",
                    error_message="background job handler failed",
                    retryable=True,
                    retry_delay=policy.retry_delay_after(job.attempt_count),
                    now=now,
                )
            return self._repository.succeed(
                job_id=job.job_id,
                worker_id=self._worker_id,
                result_reference=result_reference,
                now=now,
            )
        except BackgroundJobConflictError:
            return self._repository.get(job.job_id)
