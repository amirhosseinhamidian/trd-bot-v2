import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.alerts import (
    ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
    AlertPipelineBenchmarkReport,
    alert_outcome_policy_checksum,
    alert_pipeline_benchmark_fixture_checksum,
)
from trd_bot.alerts.publication import AlertPublicationPolicy
from trd_bot.market_data import default_market_data_service_level_policy

PHASE_FOUR_GATE_IDS = (
    "repository_contract",
    "alert_contract",
    "backend",
    "migration_cycle",
    "postgresql_resilience",
    "frontend",
)


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Phase 4 evidence timestamps must include timezone information")
    return value.astimezone(UTC)


class PhaseFourCommandEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    label: str = Field(min_length=1, max_length=100)
    command: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    duration_ms: int = Field(ge=0)

    @field_validator("command")
    @classmethod
    def reject_secrets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or "postgresql+" in item for item in value):
            raise ValueError("command evidence cannot contain empty values or database URLs")
        return value

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


class PhaseFourGateEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    gate_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    commands: tuple[PhaseFourCommandEvidence, ...] = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.commands)


class PhaseFourPriorFreezeEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    phase_three_record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    phase_three_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    phase_three_ready: Literal[True]


class PhaseFourBenchmarkEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    report_environment_label: str = Field(min_length=1, max_length=64)
    report_generated_at: datetime
    fixture_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    publication_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    outcome_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    observations: dict[str, Decimal]
    failure_reasons: tuple[str, ...] = ()

    @field_validator("report_generated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _timestamp(value)

    @model_validator(mode="after")
    def validate_passing_evidence(self) -> Self:
        if self.failure_reasons:
            return self
        if self.fixture_checksum != alert_pipeline_benchmark_fixture_checksum():
            raise ValueError("passing evidence requires the canonical alert fixture")
        if self.publication_policy_checksum != AlertPublicationPolicy.default().policy_checksum:
            raise ValueError("passing evidence requires the canonical publication policy")
        if self.outcome_policy_checksum != alert_outcome_policy_checksum():
            raise ValueError("passing evidence requires the canonical outcome policy")
        return self

    @property
    def passed(self) -> bool:
        return not self.failure_reasons


class PhaseFourCiEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    run_url: str = Field(
        pattern=r"^https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+$", max_length=300
    )
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    conclusion: Literal["success"]


class PhaseFourManualEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    alert_center_and_actions: Literal["pass"]
    quiet_hours_expiry_and_deduplication: Literal["pass"]
    worker_restart_and_reclaim: Literal["pass"]
    paper_shadow_outcome_journal: Literal["pass"]
    monitoring_and_audit_lineage: Literal["pass"]
    no_live_trading_security_inventory: Literal["pass"]


class PhaseFourAcceptanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["phase-four-acceptance-record-v1"] = "phase-four-acceptance-record-v1"
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    branch: str = Field(min_length=1, max_length=200)
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    scope: Literal["crypto-spot-public-read-only-offline-alerts"] = (
        "crypto-spot-public-read-only-offline-alerts"
    )
    database_name: Literal["trd_bot_test"] = "trd_bot_test"
    worktree_clean_at_start: Literal[True] = True
    prior_freeze: PhaseFourPriorFreezeEvidence
    benchmark: PhaseFourBenchmarkEvidence
    ci: PhaseFourCiEvidence
    manual: PhaseFourManualEvidence
    gates: tuple[PhaseFourGateEvidence, ...] = Field(min_length=1)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _timestamp(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if tuple(item.gate_id for item in self.gates) != PHASE_FOUR_GATE_IDS:
            raise ValueError("acceptance record must contain every Phase 4 gate in order")
        if self.ci.head_sha != self.commit_sha:
            raise ValueError("GitHub Actions head SHA must match the accepted commit")
        if self.benchmark.report_commit_sha != self.commit_sha:
            raise ValueError("alert benchmark SHA must match the accepted commit")
        if self.benchmark.report_environment_label != self.environment_label:
            raise ValueError("alert benchmark environment must match acceptance")
        maximum_age = timedelta(
            days=default_market_data_service_level_policy().retention.benchmark_evidence_days
        )
        age = self.generated_at - self.benchmark.report_generated_at
        if age < timedelta() or age > maximum_age:
            raise ValueError("alert benchmark must be current at acceptance time")
        return self

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(item.gate_id for item in self.gates if not item.passed)

    @property
    def ready_to_freeze_phase_four(self) -> bool:
        return not self.failed_gates and self.benchmark.passed


def evaluate_phase_four_benchmark(
    report: AlertPipelineBenchmarkReport, *, report_checksum: str
) -> PhaseFourBenchmarkEvidence:
    reasons: list[str] = []
    if report.requested_samples < ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES:
        reasons.append("alert benchmark has insufficient samples")
    if report.successful_samples != report.requested_samples:
        reasons.append("alert benchmark did not complete every sample")
    if len(report.unique_output_fingerprints) != 1:
        reasons.append("alert benchmark output is not deterministic")
    if report.runtime_p95_ms > report.runtime_budget_ms:
        reasons.append("alert benchmark exceeds its runtime budget")
    return PhaseFourBenchmarkEvidence(
        report_checksum=report_checksum,
        report_commit_sha=report.commit_sha,
        report_environment_label=report.environment_label,
        report_generated_at=report.generated_at,
        fixture_checksum=report.fixture_checksum,
        publication_policy_checksum=report.publication_policy_checksum,
        outcome_policy_checksum=report.outcome_policy_checksum,
        observations={
            "requested_samples": Decimal(report.requested_samples),
            "successful_samples": Decimal(report.successful_samples),
            "unique_output_fingerprints": Decimal(len(report.unique_output_fingerprints)),
            "runtime_p50_ms": report.runtime_p50_ms,
            "runtime_p95_ms": report.runtime_p95_ms,
            "runtime_budget_ms": report.runtime_budget_ms,
        },
        failure_reasons=tuple(reasons),
    )


def phase_four_acceptance_record_to_dict(record: PhaseFourAcceptanceRecord) -> dict[str, object]:
    payload = record.model_dump(mode="json")
    for raw, gate in zip(payload["gates"], record.gates, strict=True):
        raw["passed"] = gate.passed
    payload["benchmark"]["passed"] = record.benchmark.passed
    payload["failed_gates"] = list(record.failed_gates)
    payload["ready_to_freeze_phase_four"] = record.ready_to_freeze_phase_four
    return payload


def serialize_phase_four_acceptance_record(record: PhaseFourAcceptanceRecord) -> str:
    return json.dumps(phase_four_acceptance_record_to_dict(record), indent=2, sort_keys=True)


def parse_phase_four_acceptance_record(value: str | bytes) -> PhaseFourAcceptanceRecord:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("phase four acceptance record is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("phase four acceptance record must be a JSON object")
    payload = dict(raw)
    persisted_ready = payload.pop("ready_to_freeze_phase_four", None)
    persisted_failed = payload.pop("failed_gates", None)
    gate_outcomes = [item.pop("passed", None) for item in payload.get("gates", [])]
    benchmark_outcome = payload.get("benchmark", {}).pop("passed", None)
    record = PhaseFourAcceptanceRecord.model_validate(payload)
    if gate_outcomes and gate_outcomes != [item.passed for item in record.gates]:
        raise ValueError("phase four gate outcomes are inconsistent")
    if benchmark_outcome is not None and benchmark_outcome is not record.benchmark.passed:
        raise ValueError("phase four benchmark outcome is inconsistent")
    if persisted_failed is not None and persisted_failed != list(record.failed_gates):
        raise ValueError("phase four failed gates are inconsistent")
    if persisted_ready is not None and persisted_ready is not record.ready_to_freeze_phase_four:
        raise ValueError("phase four acceptance decision is inconsistent")
    return record
