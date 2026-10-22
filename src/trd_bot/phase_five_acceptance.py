import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.decision_intelligence import (
    DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
    DECISION_PIPELINE_BENCHMARK_RUNTIME_BUDGET_MS,
    DecisionPipelineBenchmarkReport,
    decision_candidate_policy_v1,
    decision_pipeline_benchmark_fixture_checksum,
    decision_portfolio_policy_v1,
    decision_risk_policy_v1,
    strategy_context_compatibility_policy_v1,
)
from trd_bot.market_data import default_market_data_service_level_policy

PHASE_FIVE_GATE_IDS = (
    "repository_contract",
    "decision_contract",
    "backend",
    "migration_cycle",
    "postgresql_resilience",
    "frontend",
)


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Phase 5 evidence timestamps must include timezone information")
    return value.astimezone(UTC)


class PhaseFiveCommandEvidence(BaseModel):
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


class PhaseFiveGateEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    gate_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    commands: tuple[PhaseFiveCommandEvidence, ...] = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.commands)


class PhaseFivePriorFreezeEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    phase_four_record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    phase_four_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    phase_four_ready: Literal[True]


class PhaseFiveBenchmarkEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    report_environment_label: str = Field(min_length=1, max_length=64)
    report_generated_at: datetime
    fixture_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    compatibility_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    risk_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    portfolio_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    observations: dict[str, Decimal]
    failure_reasons: tuple[str, ...] = ()

    @field_validator("report_generated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _timestamp(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        expected_observations = {
            "requested_samples",
            "successful_samples",
            "unique_output_fingerprints",
            "runtime_p50_ms",
            "runtime_p95_ms",
            "runtime_budget_ms",
        }
        if set(self.observations) != expected_observations:
            raise ValueError("decision benchmark observations are incomplete")
        reasons: list[str] = []
        if self.observations["requested_samples"] < DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES:
            reasons.append("decision benchmark has insufficient samples")
        if self.observations["successful_samples"] != self.observations["requested_samples"]:
            reasons.append("decision benchmark did not complete every sample")
        if self.observations["unique_output_fingerprints"] != 1:
            reasons.append("decision benchmark output is not deterministic")
        if self.observations["runtime_p95_ms"] > self.observations["runtime_budget_ms"]:
            reasons.append("decision benchmark exceeds its runtime budget")
        if self.failure_reasons != tuple(reasons):
            raise ValueError("decision benchmark failure reasons are inconsistent")
        if self.observations["runtime_budget_ms"] != DECISION_PIPELINE_BENCHMARK_RUNTIME_BUDGET_MS:
            raise ValueError("decision benchmark runtime budget is not canonical")
        if reasons:
            return self
        expected = {
            "fixture_checksum": decision_pipeline_benchmark_fixture_checksum(),
            "compatibility_policy_checksum": (
                strategy_context_compatibility_policy_v1().definition_checksum
            ),
            "candidate_policy_checksum": decision_candidate_policy_v1().definition_checksum,
            "risk_policy_checksum": decision_risk_policy_v1().definition_checksum,
            "portfolio_policy_checksum": decision_portfolio_policy_v1().definition_checksum,
        }
        for field_name, value in expected.items():
            if getattr(self, field_name) != value:
                raise ValueError(f"passing evidence requires canonical {field_name}")
        return self

    @property
    def passed(self) -> bool:
        return not self.failure_reasons


class PhaseFiveCiEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    run_url: str = Field(
        pattern=r"^https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+$", max_length=300
    )
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    conclusion: Literal["success"]


class PhaseFiveManualEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    strategy_signal_candidate_lineage: Literal["pass"]
    risk_gate_fail_closed: Literal["pass"]
    paper_shadow_portfolio_advisory: Literal["pass"]
    worker_restart_and_idempotency: Literal["pass"]
    api_ui_progressive_disclosure: Literal["pass"]
    no_live_trading_security_inventory: Literal["pass"]


class PhaseFiveAcceptanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["phase-five-acceptance-record-v1"] = "phase-five-acceptance-record-v1"
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    branch: str = Field(min_length=1, max_length=200)
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    scope: Literal["crypto-spot-public-read-only-research-shadow-paper"] = (
        "crypto-spot-public-read-only-research-shadow-paper"
    )
    database_name: Literal["trd_bot_test"] = "trd_bot_test"
    worktree_clean_at_start: Literal[True] = True
    prior_freeze: PhaseFivePriorFreezeEvidence
    benchmark: PhaseFiveBenchmarkEvidence
    ci: PhaseFiveCiEvidence
    manual: PhaseFiveManualEvidence
    gates: tuple[PhaseFiveGateEvidence, ...] = Field(min_length=1)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _timestamp(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if tuple(item.gate_id for item in self.gates) != PHASE_FIVE_GATE_IDS:
            raise ValueError("acceptance record must contain every Phase 5 gate in order")
        if self.ci.head_sha != self.commit_sha:
            raise ValueError("GitHub Actions head SHA must match the accepted commit")
        if self.benchmark.report_commit_sha != self.commit_sha:
            raise ValueError("decision benchmark SHA must match the accepted commit")
        if self.benchmark.report_environment_label != self.environment_label:
            raise ValueError("decision benchmark environment must match acceptance")
        maximum_age = timedelta(
            days=default_market_data_service_level_policy().retention.benchmark_evidence_days
        )
        age = self.generated_at - self.benchmark.report_generated_at
        if age < timedelta() or age > maximum_age:
            raise ValueError("decision benchmark must be current at acceptance time")
        return self

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(item.gate_id for item in self.gates if not item.passed)

    @property
    def ready_to_freeze_phase_five(self) -> bool:
        return not self.failed_gates and self.benchmark.passed


def evaluate_phase_five_benchmark(
    report: DecisionPipelineBenchmarkReport, *, report_checksum: str
) -> PhaseFiveBenchmarkEvidence:
    reasons: list[str] = []
    if report.requested_samples < DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES:
        reasons.append("decision benchmark has insufficient samples")
    if report.successful_samples != report.requested_samples:
        reasons.append("decision benchmark did not complete every sample")
    if len(report.unique_output_fingerprints) != 1:
        reasons.append("decision benchmark output is not deterministic")
    if report.runtime_p95_ms > report.runtime_budget_ms:
        reasons.append("decision benchmark exceeds its runtime budget")
    return PhaseFiveBenchmarkEvidence(
        report_checksum=report_checksum,
        report_commit_sha=report.commit_sha,
        report_environment_label=report.environment_label,
        report_generated_at=report.generated_at,
        fixture_checksum=report.fixture_checksum,
        compatibility_policy_checksum=report.compatibility_policy_checksum,
        candidate_policy_checksum=report.candidate_policy_checksum,
        risk_policy_checksum=report.risk_policy_checksum,
        portfolio_policy_checksum=report.portfolio_policy_checksum,
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


def phase_five_acceptance_record_to_dict(record: PhaseFiveAcceptanceRecord) -> dict[str, object]:
    payload = record.model_dump(mode="json")
    for raw, gate in zip(payload["gates"], record.gates, strict=True):
        raw["passed"] = gate.passed
    payload["benchmark"]["passed"] = record.benchmark.passed
    payload["failed_gates"] = list(record.failed_gates)
    payload["ready_to_freeze_phase_five"] = record.ready_to_freeze_phase_five
    return payload


def serialize_phase_five_acceptance_record(record: PhaseFiveAcceptanceRecord) -> str:
    return json.dumps(phase_five_acceptance_record_to_dict(record), indent=2, sort_keys=True)


def parse_phase_five_acceptance_record(value: str | bytes) -> PhaseFiveAcceptanceRecord:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("phase five acceptance record is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("phase five acceptance record must be a JSON object")
    payload = dict(raw)
    persisted_ready = payload.pop("ready_to_freeze_phase_five", None)
    persisted_failed = payload.pop("failed_gates", None)
    gate_outcomes = [item.pop("passed", None) for item in payload.get("gates", [])]
    benchmark_outcome = payload.get("benchmark", {}).pop("passed", None)
    record = PhaseFiveAcceptanceRecord.model_validate(payload)
    if gate_outcomes and gate_outcomes != [item.passed for item in record.gates]:
        raise ValueError("phase five gate outcomes are inconsistent")
    if benchmark_outcome is not None and benchmark_outcome is not record.benchmark.passed:
        raise ValueError("phase five benchmark outcome is inconsistent")
    if persisted_failed is not None and persisted_failed != list(record.failed_gates):
        raise ValueError("phase five failed gates are inconsistent")
    if persisted_ready is not None and persisted_ready is not record.ready_to_freeze_phase_five:
        raise ValueError("phase five acceptance decision is inconsistent")
    return record
