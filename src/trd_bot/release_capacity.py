import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.jobs import BackgroundJobKind
from trd_bot.market_data import default_market_data_service_level_policy

RELEASE_CAPACITY_SCHEMA_VERSION = "v0.3-release-capacity-benchmark-v1"
RELEASE_CAPACITY_POLICY_SCHEMA_VERSION = "v0.3-release-capacity-policy-v1"


class QueuePressureLevel(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    OVERLOAD = "overload"


class ReleaseCapacityPolicy(BaseModel):
    """Fail-closed Phase 6 capacity and recovery policy for the local release."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["v0.3-release-capacity-policy-v1"] = "v0.3-release-capacity-policy-v1"
    queue_warning_depth: int = Field(ge=1)
    queue_overload_depth: int = Field(ge=2)
    worker_concurrency: Literal[1] = 1
    minimum_contention_workers: int = Field(ge=2)
    database_operation_p95_budget_milliseconds: Decimal = Field(gt=0)
    queue_wait_p95_budget_milliseconds: Decimal = Field(gt=0)
    minimum_overload_drain_throughput_per_second: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.queue_overload_depth <= self.queue_warning_depth:
            raise ValueError("release queue overload depth must exceed warning depth")
        return self

    @property
    def definition_checksum(self) -> str:
        return _checksum(self.model_dump(mode="json"))


class ReleaseCapacityObservations(BaseModel):
    """Sanitized observations from one isolated PostgreSQL benchmark run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_jobs: int = Field(ge=1)
    covered_job_kinds: tuple[str, ...] = Field(min_length=1)
    overload_depth_observed: int = Field(ge=0)
    overload_level: QueuePressureLevel
    succeeded_jobs: int = Field(ge=0)
    failed_jobs: int = Field(ge=0)
    remaining_active_jobs: int = Field(ge=0)
    enqueue_latency_p95_milliseconds: Decimal = Field(ge=0)
    queue_wait_p95_milliseconds: Decimal = Field(ge=0)
    worker_cycle_latency_p95_milliseconds: Decimal = Field(ge=0)
    overload_drain_throughput_per_second: Decimal = Field(ge=0)
    duplicate_enqueue_attempts: int = Field(ge=2)
    duplicate_created_count: int = Field(ge=0)
    duplicate_unique_job_count: int = Field(ge=0)
    contention_workers: int = Field(ge=2)
    contention_claim_winner_count: int = Field(ge=0)
    contention_unique_job_count: int = Field(ge=0)
    recovery_attempt_count: int = Field(ge=0)
    recovery_reused_job: bool
    stale_owner_fenced: bool
    retry_attempt_count: int = Field(ge=0)
    retry_reused_job: bool
    recovery_transition_milliseconds: Decimal = Field(ge=0)
    cleanup_verified: bool

    @model_validator(mode="after")
    def validate_canonical_kinds(self) -> Self:
        if self.covered_job_kinds != tuple(sorted(set(self.covered_job_kinds))):
            raise ValueError("covered release job kinds must be sorted and unique")
        return self


class ReleaseCapacityBenchmarkReport(BaseModel):
    """Commit-bound P6-02 evidence without credentials, DSNs, or job payloads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["v0.3-release-capacity-benchmark-v1"] = (
        "v0.3-release-capacity-benchmark-v1"
    )
    environment_label: str = Field(min_length=1, max_length=64)
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    generated_at: datetime
    python_version: str = Field(min_length=1, max_length=50)
    platform: str = Field(min_length=1, max_length=200)
    database_backend: Literal["postgresql"] = "postgresql"
    policy: ReleaseCapacityPolicy
    observations: ReleaseCapacityObservations
    failure_reasons: tuple[str, ...] = ()

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("release capacity timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        expected = evaluate_release_capacity(self.policy, self.observations)
        if self.failure_reasons != expected:
            raise ValueError("release capacity failure reasons are inconsistent")
        return self

    @property
    def passed(self) -> bool:
        return not self.failure_reasons

    @property
    def report_checksum(self) -> str:
        return _checksum(self.model_dump(mode="json"))


def default_release_capacity_policy() -> ReleaseCapacityPolicy:
    baseline = default_market_data_service_level_policy().capacity
    if baseline.worker_concurrency != 1:
        raise RuntimeError("v0.3 release benchmark requires single-worker concurrency")
    wait_budget_ms = baseline.job_queue_wait_p95_seconds * Decimal(1_000)
    return ReleaseCapacityPolicy(
        queue_warning_depth=baseline.queue_depth_warning,
        queue_overload_depth=baseline.queue_depth_overload,
        worker_concurrency=1,
        minimum_contention_workers=8,
        database_operation_p95_budget_milliseconds=(
            baseline.database_query_latency_p95_milliseconds
        ),
        queue_wait_p95_budget_milliseconds=wait_budget_ms,
        minimum_overload_drain_throughput_per_second=(
            Decimal(baseline.queue_depth_overload) / baseline.job_queue_wait_p95_seconds
        ),
    )


def classify_queue_pressure(
    depth: int,
    policy: ReleaseCapacityPolicy | None = None,
) -> QueuePressureLevel:
    if depth < 0:
        raise ValueError("queue depth cannot be negative")
    active_policy = policy or default_release_capacity_policy()
    if depth >= active_policy.queue_overload_depth:
        return QueuePressureLevel.OVERLOAD
    if depth >= active_policy.queue_warning_depth:
        return QueuePressureLevel.WARNING
    return QueuePressureLevel.NORMAL


def evaluate_release_capacity(
    policy: ReleaseCapacityPolicy,
    observations: ReleaseCapacityObservations,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected_kinds = tuple(sorted(kind.value for kind in BackgroundJobKind))
    if observations.covered_job_kinds != expected_kinds:
        reasons.append("release benchmark does not cover every background job kind")
    if observations.requested_jobs < policy.queue_overload_depth:
        reasons.append("release benchmark did not reach the configured overload depth")
    if (
        observations.overload_depth_observed < policy.queue_overload_depth
        or observations.overload_level is not QueuePressureLevel.OVERLOAD
    ):
        reasons.append("release queue did not expose the overload state")
    if (
        observations.succeeded_jobs != observations.requested_jobs
        or observations.failed_jobs != 0
        or observations.remaining_active_jobs != 0
    ):
        reasons.append("release overload queue did not drain successfully")
    operation_budget = policy.database_operation_p95_budget_milliseconds
    if observations.enqueue_latency_p95_milliseconds > operation_budget:
        reasons.append("release enqueue latency exceeded the database p95 budget")
    if observations.worker_cycle_latency_p95_milliseconds > operation_budget:
        reasons.append("release worker cycle latency exceeded the database p95 budget")
    if observations.queue_wait_p95_milliseconds > policy.queue_wait_p95_budget_milliseconds:
        reasons.append("release queue wait exceeded the p95 budget")
    if (
        observations.overload_drain_throughput_per_second
        < policy.minimum_overload_drain_throughput_per_second
    ):
        reasons.append("release overload drain throughput is below the minimum budget")
    if observations.duplicate_created_count != 1 or observations.duplicate_unique_job_count != 1:
        reasons.append("release concurrent enqueue is not idempotent")
    if observations.contention_workers < policy.minimum_contention_workers:
        reasons.append("release claim contention used too few workers")
    if (
        observations.contention_claim_winner_count != 1
        or observations.contention_unique_job_count != 1
    ):
        reasons.append("release queue allowed duplicate concurrent claims")
    if (
        observations.recovery_attempt_count != 2
        or not observations.recovery_reused_job
        or not observations.stale_owner_fenced
    ):
        reasons.append("release expired-lease recovery or stale-owner fencing failed")
    if observations.retry_attempt_count != 2 or not observations.retry_reused_job:
        reasons.append("release retry did not preserve the durable job identity")
    if observations.recovery_transition_milliseconds > operation_budget:
        reasons.append("release recovery transition exceeded the database p95 budget")
    if not observations.cleanup_verified:
        reasons.append("release benchmark rows were not fully cleaned up")
    return tuple(reasons)


def build_release_capacity_report(
    *,
    environment_label: str,
    commit_sha: str,
    generated_at: datetime,
    python_version: str,
    platform: str,
    observations: ReleaseCapacityObservations,
    policy: ReleaseCapacityPolicy | None = None,
) -> ReleaseCapacityBenchmarkReport:
    active_policy = policy or default_release_capacity_policy()
    return ReleaseCapacityBenchmarkReport(
        environment_label=environment_label,
        commit_sha=commit_sha,
        generated_at=generated_at,
        python_version=python_version,
        platform=platform,
        policy=active_policy,
        observations=observations,
        failure_reasons=evaluate_release_capacity(active_policy, observations),
    )


def release_capacity_report_to_dict(
    report: ReleaseCapacityBenchmarkReport,
) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    payload["passed"] = report.passed
    payload["policy_checksum"] = report.policy.definition_checksum
    payload["report_checksum"] = report.report_checksum
    return payload


def serialize_release_capacity_report(report: ReleaseCapacityBenchmarkReport) -> str:
    return json.dumps(
        release_capacity_report_to_dict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_release_capacity_report(value: str | bytes) -> ReleaseCapacityBenchmarkReport:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("release capacity report is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("release capacity report must be a JSON object")
    payload = dict(raw)
    persisted_passed = payload.pop("passed", None)
    persisted_policy_checksum = payload.pop("policy_checksum", None)
    persisted_report_checksum = payload.pop("report_checksum", None)
    report = ReleaseCapacityBenchmarkReport.model_validate(payload)
    if persisted_passed is not None and persisted_passed is not report.passed:
        raise ValueError("release capacity outcome is inconsistent")
    if (
        persisted_policy_checksum is not None
        and persisted_policy_checksum != report.policy.definition_checksum
    ):
        raise ValueError("release capacity policy checksum is inconsistent")
    if (
        persisted_report_checksum is not None
        and persisted_report_checksum != report.report_checksum
    ):
        raise ValueError("release capacity report checksum is inconsistent")
    return report


def _checksum(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
