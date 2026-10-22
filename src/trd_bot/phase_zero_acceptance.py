import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.jobs import BackgroundJobKind
from trd_bot.market_data.service_levels import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceScope,
    MarketDataServiceLevelPolicy,
    default_market_data_service_level_policy,
    serialize_capacity_benchmark_report,
)

PHASE_ZERO_REQUIREMENT_IDS: Final = tuple(f"P0-A{index:02d}" for index in range(1, 9))


class PhaseZeroAcceptanceGate(StrEnum):
    """Evidence gates used by the final Phase 0 decision."""

    REPOSITORY_EVIDENCE = "repository_evidence"
    PROVIDER_SELECTION = "provider_selection"
    CAPACITY_TARGETS = "capacity_targets"


class PhaseZeroAcceptanceRequirement(BaseModel):
    """One owned decision and the evidence required to accept it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str = Field(pattern=r"^P0-A[0-9]{2}$")
    decision: str = Field(min_length=1, max_length=300)
    owner: str = Field(min_length=1, max_length=100)
    delivery_phase: str = Field(pattern=r"^(P[0-9]+(?:/P[0-9]+)*|post-v0\.3)$")
    gate: PhaseZeroAcceptanceGate
    evidence_references: tuple[str, ...] = Field(min_length=1)

    @field_validator("decision", "owner")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("acceptance text cannot be empty")
        return normalized

    @field_validator("evidence_references")
    @classmethod
    def validate_evidence_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item or item.startswith("/") or ".." in Path(item).parts for item in normalized):
            raise ValueError("evidence references must be safe repository-relative paths")
        if len(normalized) != len(set(normalized)):
            raise ValueError("acceptance requirement cannot repeat evidence references")
        return normalized


class PhaseZeroAcceptanceMatrix(BaseModel):
    """Versioned owner/evidence/phase matrix for P0-05."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["phase-zero-acceptance-matrix-v1"] = "phase-zero-acceptance-matrix-v1"
    requirements: tuple[PhaseZeroAcceptanceRequirement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_requirements(self) -> Self:
        identifiers = [item.requirement_id for item in self.requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("acceptance matrix cannot repeat requirement IDs")
        if set(identifiers) != set(PHASE_ZERO_REQUIREMENT_IDS):
            raise ValueError("acceptance matrix must contain every frozen requirement ID")
        gates = {item.gate for item in self.requirements}
        if gates != set(PhaseZeroAcceptanceGate):
            raise ValueError("acceptance matrix must cover every gate kind")
        return self


class PhaseZeroAcceptanceCheck(BaseModel):
    """Evaluated outcome for one matrix requirement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement_id: str = Field(pattern=r"^P0-A[0-9]{2}$")
    passed: bool
    evidence_references: tuple[str, ...] = Field(min_length=1)
    observations: dict[str, Decimal] = Field(default_factory=dict)
    failure_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.passed == bool(self.failure_reasons):
            raise ValueError("acceptance check outcome and failure reasons are inconsistent")
        if any(value < 0 for value in self.observations.values()):
            raise ValueError("acceptance observations cannot be negative")
        return self


class PhaseZeroFreezeRecord(BaseModel):
    """Auditable, fail-closed Phase 0 freeze decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["phase-zero-freeze-record-v1"] = "phase-zero-freeze-record-v1"
    matrix_schema_version: Literal["phase-zero-acceptance-matrix-v1"] = (
        "phase-zero-acceptance-matrix-v1"
    )
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    capacity_report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    primary_provider: str = Field(min_length=1, max_length=50)
    fallback_providers: tuple[str, ...] = Field(min_length=1)
    checks: tuple[PhaseZeroAcceptanceCheck, ...] = Field(min_length=1)

    @field_validator("primary_provider")
    @classmethod
    def normalize_primary_provider(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("primary provider cannot be empty")
        return normalized

    @field_validator("fallback_providers")
    @classmethod
    def normalize_fallback_providers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise ValueError("fallback providers cannot contain empty values")
        return normalized

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("freeze record timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        providers = (self.primary_provider, *self.fallback_providers)
        if len(providers) != len(set(providers)):
            raise ValueError("provider order cannot contain duplicates")
        requirement_ids = [item.requirement_id for item in self.checks]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("freeze record cannot repeat requirement IDs")
        if set(requirement_ids) != set(PHASE_ZERO_REQUIREMENT_IDS):
            raise ValueError("freeze record must contain every frozen requirement ID")
        return self

    @property
    def missing_requirements(self) -> tuple[str, ...]:
        return tuple(item.requirement_id for item in self.checks if not item.passed)

    @property
    def ready_to_freeze(self) -> bool:
        return not self.missing_requirements


def default_phase_zero_acceptance_matrix() -> PhaseZeroAcceptanceMatrix:
    """Return the fixed P0-05 acceptance inventory."""

    return PhaseZeroAcceptanceMatrix(
        requirements=(
            PhaseZeroAcceptanceRequirement(
                requirement_id="P0-A01",
                decision="Crypto Spot scope, user scale, and execution boundary are explicit.",
                owner="Product and Architecture",
                delivery_phase="P0",
                gate=PhaseZeroAcceptanceGate.REPOSITORY_EVIDENCE,
                evidence_references=("docs/v0.3/00-scope-and-market-target.md",),
            ),
            PhaseZeroAcceptanceRequirement(
                requirement_id="P0-A02",
                decision="Live execution and private trading credentials remain excluded.",
                owner="Security",
                delivery_phase="P0",
                gate=PhaseZeroAcceptanceGate.REPOSITORY_EVIDENCE,
                evidence_references=(
                    "docs/v0.3/00-scope-and-market-target.md",
                    "tests/test_release_security_boundary.py",
                ),
            ),
            PhaseZeroAcceptanceRequirement(
                requirement_id="P0-A03",
                decision="Every inherited v0.2 debt has an owner and delivery phase.",
                owner="Platform",
                delivery_phase="P1",
                gate=PhaseZeroAcceptanceGate.REPOSITORY_EVIDENCE,
                evidence_references=("docs/v0.3/01-baseline-debt-capacity-inventory.md",),
            ),
            PhaseZeroAcceptanceRequirement(
                requirement_id="P0-A04",
                decision="Event identity, ordering, watermark, and window lifecycle are frozen.",
                owner="Market Data",
                delivery_phase="P2",
                gate=PhaseZeroAcceptanceGate.REPOSITORY_EVIDENCE,
                evidence_references=(
                    "docs/v0.3/02-event-contract-and-window-semantics.md",
                    "tests/test_market_data_events.py",
                ),
            ),
            PhaseZeroAcceptanceRequirement(
                requirement_id="P0-A05",
                decision="SLO, retention, request budgets, and capacity targets are versioned.",
                owner="Market Data and Operations",
                delivery_phase="P0",
                gate=PhaseZeroAcceptanceGate.REPOSITORY_EVIDENCE,
                evidence_references=(
                    "docs/v0.3/03-service-level-retention-capacity-budget.md",
                    "tests/test_market_data_service_levels.py",
                ),
            ),
            PhaseZeroAcceptanceRequirement(
                requirement_id="P0-A06",
                decision="Primary and fallback providers satisfy measured reference budgets.",
                owner="Market Data",
                delivery_phase="P2",
                gate=PhaseZeroAcceptanceGate.PROVIDER_SELECTION,
                evidence_references=("docs/v0.3/03-service-level-retention-capacity-budget.md",),
            ),
            PhaseZeroAcceptanceRequirement(
                requirement_id="P0-A07",
                decision="All five capacity scopes are complete and satisfy frozen targets.",
                owner="Platform and Operations",
                delivery_phase="P2/P6",
                gate=PhaseZeroAcceptanceGate.CAPACITY_TARGETS,
                evidence_references=("docs/v0.3/03-service-level-retention-capacity-budget.md",),
            ),
            PhaseZeroAcceptanceRequirement(
                requirement_id="P0-A08",
                decision="P1 debt closure remains mandatory before Live Data Foundation.",
                owner="Platform",
                delivery_phase="P1",
                gate=PhaseZeroAcceptanceGate.REPOSITORY_EVIDENCE,
                evidence_references=("docs/v0.3/01-baseline-debt-capacity-inventory.md",),
            ),
        )
    )


def _evidence_by_scope(
    report: CapacityBenchmarkReport,
) -> dict[CapacityEvidenceScope, CapacityEvidence]:
    return {item.scope: item for item in report.evidence}


def _metric(
    evidence: CapacityEvidence | None,
    name: str,
    *,
    reasons: list[str],
) -> Decimal | None:
    if evidence is None:
        reasons.append(f'missing evidence scope for metric "{name}"')
        return None
    value = evidence.metrics.get(name)
    if value is None:
        reasons.append(f'missing capacity metric "{name}"')
    return value


def _evaluate_provider_selection(
    *,
    report: CapacityBenchmarkReport,
    primary_provider: str,
    fallback_providers: tuple[str, ...],
    policy: MarketDataServiceLevelPolicy,
) -> tuple[list[str], dict[str, Decimal]]:
    reasons: list[str] = []
    observations: dict[str, Decimal] = {}
    selected = (primary_provider, *fallback_providers)
    if len(selected) != len(set(selected)):
        reasons.append("primary and fallback provider order contains duplicates")

    evidence = _evidence_by_scope(report).get(CapacityEvidenceScope.PROVIDER)
    if evidence is None or not evidence.complete:
        reasons.append("provider evidence is not complete")
        return reasons, observations

    for provider_id in selected:
        try:
            budget = policy.for_provider(provider_id)
        except ValueError:
            reasons.append(f'provider "{provider_id}" has no frozen request budget')
            continue
        prefix = f"{provider_id}."
        samples = _metric(evidence, f"{prefix}samples", reasons=reasons)
        failure_fraction = _metric(
            evidence,
            f"{prefix}failure_fraction",
            reasons=reasons,
        )
        latency = _metric(
            evidence,
            f"{prefix}http_latency_p95_ms",
            reasons=reasons,
        )
        if samples is not None:
            observations[f"{prefix}samples"] = samples
            if samples < budget.minimum_probe_samples:
                reasons.append(f'provider "{provider_id}" has insufficient probe samples')
        if failure_fraction is not None:
            observations[f"{prefix}failure_fraction"] = failure_fraction
            if failure_fraction > budget.maximum_failure_fraction:
                reasons.append(f'provider "{provider_id}" exceeds the failure budget')
        if latency is not None:
            observations[f"{prefix}http_latency_p95_ms"] = latency
            if latency > budget.http_latency_p95_seconds * Decimal(1_000):
                reasons.append(f'provider "{provider_id}" exceeds the latency budget')
    return reasons, observations


def _check_maximum(
    *,
    evidence: CapacityEvidence | None,
    metric_name: str,
    maximum: Decimal,
    observations: dict[str, Decimal],
    reasons: list[str],
) -> None:
    value = _metric(evidence, metric_name, reasons=reasons)
    if value is None:
        return
    observations[metric_name] = value
    if value > maximum:
        reasons.append(f'capacity metric "{metric_name}" exceeds its target')


def _check_minimum(
    *,
    evidence: CapacityEvidence | None,
    metric_name: str,
    minimum: Decimal,
    observations: dict[str, Decimal],
    reasons: list[str],
) -> None:
    value = _metric(evidence, metric_name, reasons=reasons)
    if value is None:
        return
    observations[metric_name] = value
    if value < minimum:
        reasons.append(f'capacity metric "{metric_name}" is below its target')


def _evaluate_capacity_targets(
    *,
    report: CapacityBenchmarkReport,
    policy: MarketDataServiceLevelPolicy,
) -> tuple[list[str], dict[str, Decimal]]:
    reasons = [f'missing complete scope "{scope.value}"' for scope in report.missing_scopes]
    observations: dict[str, Decimal] = {}
    evidence = _evidence_by_scope(report)
    event = evidence.get(CapacityEvidenceScope.EVENT_PROCESSING)
    database = evidence.get(CapacityEvidenceScope.DATABASE)
    jobs = evidence.get(CapacityEvidenceScope.BACKGROUND_JOBS)
    storage = evidence.get(CapacityEvidenceScope.STORAGE)
    budget = policy.capacity

    _check_maximum(
        evidence=event,
        metric_name="contract_latency_p95_ms",
        maximum=budget.event_processing_latency_p95_milliseconds,
        observations=observations,
        reasons=reasons,
    )
    _check_minimum(
        evidence=event,
        metric_name="contract_throughput_per_second",
        minimum=budget.event_processing_throughput_per_second,
        observations=observations,
        reasons=reasons,
    )
    for metric_name in (
        "inbox_lookup_latency_p95_ms",
        "current_window_latency_p95_ms",
        "time_range_latency_p95_ms",
    ):
        _check_maximum(
            evidence=database,
            metric_name=metric_name,
            maximum=budget.database_query_latency_p95_milliseconds,
            observations=observations,
            reasons=reasons,
        )
    _check_maximum(
        evidence=database,
        metric_name="pool_utilization_p95_fraction",
        maximum=budget.database_pool_utilization_p95_fraction,
        observations=observations,
        reasons=reasons,
    )
    _check_maximum(
        evidence=jobs,
        metric_name="queue_wait_p95_ms",
        maximum=budget.job_queue_wait_p95_seconds * Decimal(1_000),
        observations=observations,
        reasons=reasons,
    )
    for kind in BackgroundJobKind:
        _check_maximum(
            evidence=jobs,
            metric_name=f"{kind.value}.runtime_p95_seconds",
            maximum=budget.job_runtime_p95_seconds[kind.value],
            observations=observations,
            reasons=reasons,
        )

    event_count = _metric(database, "event_count", reasons=reasons)
    event_bytes = _metric(storage, "events_total_bytes", reasons=reasons)
    projected_events = _metric(
        storage,
        "projected_events_per_30_days",
        reasons=reasons,
    )
    if event_count is not None and event_bytes is not None and projected_events is not None:
        if event_count <= 0:
            reasons.append("database event count must be positive for storage projection")
        else:
            projected_bytes = event_bytes / event_count * projected_events
            metric_name = "projected_actual_storage_bytes_per_30_days"
            observations[metric_name] = projected_bytes
            if projected_bytes > budget.maximum_storage_growth_bytes_per_30_days:
                reasons.append(f'capacity metric "{metric_name}" exceeds its target')
    return reasons, observations


def evaluate_phase_zero_acceptance(
    *,
    capacity_report: CapacityBenchmarkReport,
    primary_provider: str,
    fallback_providers: tuple[str, ...],
    repository_root: Path,
    generated_at: datetime | None = None,
) -> PhaseZeroFreezeRecord:
    """Evaluate every P0-05 requirement without an operator override path."""

    matrix = default_phase_zero_acceptance_matrix()
    policy = default_market_data_service_level_policy()
    provider_reasons, provider_observations = _evaluate_provider_selection(
        report=capacity_report,
        primary_provider=primary_provider,
        fallback_providers=fallback_providers,
        policy=policy,
    )
    capacity_reasons, capacity_observations = _evaluate_capacity_targets(
        report=capacity_report,
        policy=policy,
    )

    checks: list[PhaseZeroAcceptanceCheck] = []
    for requirement in matrix.requirements:
        missing_paths = tuple(
            reference
            for reference in requirement.evidence_references
            if not (repository_root / reference).is_file()
        )
        reasons = [f'missing repository evidence "{path}"' for path in missing_paths]
        observations: dict[str, Decimal] = {}
        if requirement.gate is PhaseZeroAcceptanceGate.PROVIDER_SELECTION:
            reasons.extend(provider_reasons)
            observations.update(provider_observations)
        elif requirement.gate is PhaseZeroAcceptanceGate.CAPACITY_TARGETS:
            reasons.extend(capacity_reasons)
            observations.update(capacity_observations)
        checks.append(
            PhaseZeroAcceptanceCheck(
                requirement_id=requirement.requirement_id,
                passed=not reasons,
                evidence_references=requirement.evidence_references,
                observations=observations,
                failure_reasons=tuple(dict.fromkeys(reasons)),
            )
        )

    return PhaseZeroFreezeRecord(
        commit_sha=capacity_report.commit_sha,
        capacity_report_checksum=hashlib.sha256(
            serialize_capacity_benchmark_report(capacity_report).encode("utf-8")
        ).hexdigest(),
        environment_label=capacity_report.environment_label,
        generated_at=generated_at or datetime.now(UTC),
        primary_provider=primary_provider,
        fallback_providers=fallback_providers,
        checks=tuple(checks),
    )


def phase_zero_freeze_record_to_dict(record: PhaseZeroFreezeRecord) -> dict[str, object]:
    payload = record.model_dump(mode="json")
    payload["ready_to_freeze"] = record.ready_to_freeze
    payload["missing_requirements"] = list(record.missing_requirements)
    return payload


def serialize_phase_zero_freeze_record(record: PhaseZeroFreezeRecord) -> str:
    return json.dumps(
        phase_zero_freeze_record_to_dict(record),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_phase_zero_freeze_record(value: str | bytes) -> PhaseZeroFreezeRecord:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("phase zero freeze record is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("phase zero freeze record must be a JSON object")
    payload = dict(raw)
    persisted_ready = payload.pop("ready_to_freeze", None)
    persisted_missing = payload.pop("missing_requirements", None)
    record = PhaseZeroFreezeRecord.model_validate(payload)
    if persisted_ready is not None and persisted_ready is not record.ready_to_freeze:
        raise ValueError("phase zero freeze decision is inconsistent")
    expected_missing = list(record.missing_requirements)
    if persisted_missing is not None and persisted_missing != expected_missing:
        raise ValueError("phase zero missing requirements are inconsistent")
    return record
