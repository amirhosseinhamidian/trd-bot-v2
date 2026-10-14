import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.market_data.service_levels import (
    CapacityBenchmarkReport,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
    default_market_data_service_level_policy,
)

PHASE_TWO_GATE_IDS = (
    "repository_contract",
    "market_data_contract",
    "backend",
    "migration_cycle",
    "postgresql_resilience",
    "frontend",
)
PHASE_TWO_PRIMARY_PROVIDER = "kraken-public"
PHASE_TWO_FALLBACK_PROVIDERS = ("binance-public",)


class PhaseTwoCommandEvidence(BaseModel):
    """Sanitized outcome for one Phase 2 acceptance command."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    command: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    duration_ms: int = Field(ge=0)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("command label cannot be empty")
        return normalized

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not part or "postgresql+" in part for part in value):
            raise ValueError("command evidence cannot contain empty values or database URLs")
        return value

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


class PhaseTwoGateEvidence(BaseModel):
    """Ordered command evidence for one automated Phase 2 gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    commands: tuple[PhaseTwoCommandEvidence, ...] = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return all(command.passed for command in self.commands)


class PhaseTwoCiEvidence(BaseModel):
    """GitHub Actions evidence tied to the exact candidate SHA."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_url: str = Field(
        pattern=r"^https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+$",
        max_length=300,
    )
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    conclusion: Literal["success"]


class PhaseTwoManualEvidence(BaseModel):
    """Owner attestations for observable behavior outside deterministic CI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    local_api_worker_frontend: Literal["pass"]
    watchlist_fallback_freshness: Literal["pass"]
    worker_restart_deduplication: Literal["pass"]
    late_data_replay_monitoring: Literal["pass"]
    retention_hold_and_dry_run: Literal["pass"]
    security_network_inventory: Literal["pass"]


class PhaseTwoPriorFreezeEvidence(BaseModel):
    """Checksummed accepted P0/P1 records that are ancestors of the candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_zero_record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    phase_zero_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    phase_zero_ready: Literal[True]
    phase_one_record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    phase_one_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    phase_one_ready: Literal[True]


class PhaseTwoProviderEvidence(BaseModel):
    """Measured same-SHA provider availability evaluated against frozen budgets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    report_environment_label: str = Field(min_length=1, max_length=64)
    report_generated_at: datetime
    policy_version: Literal["market-data-service-level-policy-v1"] = (
        "market-data-service-level-policy-v1"
    )
    primary_provider: Literal["kraken-public"] = "kraken-public"
    fallback_providers: tuple[str, ...] = PHASE_TWO_FALLBACK_PROVIDERS
    observations: dict[str, Decimal] = Field(default_factory=dict)
    failure_reasons: tuple[str, ...] = ()

    @field_validator("report_environment_label")
    @classmethod
    def normalize_environment_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("provider evidence environment cannot be empty")
        return normalized

    @field_validator("report_generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider evidence timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.fallback_providers != PHASE_TWO_FALLBACK_PROVIDERS:
            raise ValueError("Phase 2 provider order must remain Kraken then Binance")
        if any(value < 0 for value in self.observations.values()):
            raise ValueError("provider observations cannot be negative")
        if not self.failure_reasons:
            policy = default_market_data_service_level_policy()
            expected_metrics = {
                f"{provider_id}.{suffix}"
                for provider_id in (PHASE_TWO_PRIMARY_PROVIDER, *PHASE_TWO_FALLBACK_PROVIDERS)
                for suffix in ("samples", "failure_fraction", "http_latency_p95_ms")
            }
            if set(self.observations) != expected_metrics:
                raise ValueError("passing provider evidence requires every frozen SLO metric")
            for provider_id in (
                PHASE_TWO_PRIMARY_PROVIDER,
                *PHASE_TWO_FALLBACK_PROVIDERS,
            ):
                budget = policy.for_provider(provider_id)
                if self.observations[f"{provider_id}.samples"] < budget.minimum_probe_samples:
                    raise ValueError("passing provider evidence has insufficient samples")
                if (
                    self.observations[f"{provider_id}.failure_fraction"]
                    > budget.maximum_failure_fraction
                ):
                    raise ValueError("passing provider evidence exceeds the failure budget")
                if self.observations[
                    f"{provider_id}.http_latency_p95_ms"
                ] > budget.http_latency_p95_seconds * Decimal(1_000):
                    raise ValueError("passing provider evidence exceeds the latency budget")
        return self

    @property
    def passed(self) -> bool:
        return not self.failure_reasons


class PhaseTwoAcceptanceRecord(BaseModel):
    """Auditable, fail-closed decision that freezes the Phase 2 foundation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["phase-two-acceptance-record-v1"] = "phase-two-acceptance-record-v1"
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    branch: str = Field(min_length=1, max_length=200)
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    scope: Literal["crypto-spot-public-read-only"] = "crypto-spot-public-read-only"
    database_name: Literal["trd_bot_test"] = "trd_bot_test"
    worktree_clean_at_start: Literal[True] = True
    prior_freezes: PhaseTwoPriorFreezeEvidence
    provider: PhaseTwoProviderEvidence
    ci: PhaseTwoCiEvidence
    manual: PhaseTwoManualEvidence
    gates: tuple[PhaseTwoGateEvidence, ...] = Field(min_length=1)

    @field_validator("branch", "environment_label")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("acceptance metadata cannot be empty")
        return normalized

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("acceptance timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        gate_ids = tuple(gate.gate_id for gate in self.gates)
        if gate_ids != PHASE_TWO_GATE_IDS:
            raise ValueError("acceptance record must contain every Phase 2 gate in order")
        if self.ci.head_sha != self.commit_sha:
            raise ValueError("GitHub Actions head SHA must match the accepted commit")
        if self.provider.report_commit_sha != self.commit_sha:
            raise ValueError("provider report SHA must match the accepted commit")
        if self.provider.report_environment_label != self.environment_label:
            raise ValueError("provider report environment must match the acceptance environment")
        maximum_age = timedelta(
            days=default_market_data_service_level_policy().retention.benchmark_evidence_days
        )
        provider_age = self.generated_at - self.provider.report_generated_at
        if provider_age < timedelta(0) or provider_age > maximum_age:
            raise ValueError("provider report must be current at acceptance time")
        return self

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(gate.gate_id for gate in self.gates if not gate.passed)

    @property
    def ready_to_freeze_phase_two(self) -> bool:
        return not self.failed_gates and self.provider.passed


def evaluate_phase_two_provider_evidence(
    report: CapacityBenchmarkReport,
    *,
    report_checksum: str,
) -> PhaseTwoProviderEvidence:
    """Evaluate Kraken and Binance live evidence without trusting derived report state."""

    policy = default_market_data_service_level_policy()
    provider_scope = next(
        (item for item in report.evidence if item.scope is CapacityEvidenceScope.PROVIDER),
        None,
    )
    reasons: list[str] = []
    observations: dict[str, Decimal] = {}
    if provider_scope is None:
        reasons.append("provider evidence scope is missing")
    elif not provider_scope.complete:
        reasons.append("provider evidence scope is incomplete")
    elif provider_scope.method not in {
        CapacityEvidenceMethod.LIVE_PROBE,
        CapacityEvidenceMethod.PRODUCTION_TELEMETRY,
    }:
        reasons.append("provider evidence is not based on live observations")

    for provider_id in (PHASE_TWO_PRIMARY_PROVIDER, *PHASE_TWO_FALLBACK_PROVIDERS):
        budget = policy.for_provider(provider_id)
        for suffix in ("samples", "failure_fraction", "http_latency_p95_ms"):
            metric_name = f"{provider_id}.{suffix}"
            value = None if provider_scope is None else provider_scope.metrics.get(metric_name)
            if value is None:
                reasons.append(f'missing provider metric "{metric_name}"')
                continue
            observations[metric_name] = value
            if suffix == "samples" and value < budget.minimum_probe_samples:
                reasons.append(f'provider "{provider_id}" has insufficient samples')
            elif suffix == "failure_fraction" and value > budget.maximum_failure_fraction:
                reasons.append(f'provider "{provider_id}" exceeds the failure budget')
            elif (
                suffix == "http_latency_p95_ms"
                and value > budget.http_latency_p95_seconds * Decimal(1_000)
            ):
                reasons.append(f'provider "{provider_id}" exceeds the latency budget')

    return PhaseTwoProviderEvidence(
        report_checksum=report_checksum,
        report_commit_sha=report.commit_sha,
        report_environment_label=report.environment_label,
        report_generated_at=report.generated_at,
        fallback_providers=PHASE_TWO_FALLBACK_PROVIDERS,
        observations=observations,
        failure_reasons=tuple(reasons),
    )


def phase_two_acceptance_record_to_dict(record: PhaseTwoAcceptanceRecord) -> dict[str, object]:
    payload = record.model_dump(mode="json")
    gates = payload["gates"]
    if not isinstance(gates, list):
        raise TypeError("serialized Phase 2 gates must be a list")
    for gate_payload, gate in zip(gates, record.gates, strict=True):
        if not isinstance(gate_payload, dict):
            raise TypeError("serialized Phase 2 gate must be an object")
        gate_payload["passed"] = gate.passed
    provider = payload["provider"]
    if not isinstance(provider, dict):
        raise TypeError("serialized Phase 2 provider evidence must be an object")
    provider["passed"] = record.provider.passed
    payload["failed_gates"] = list(record.failed_gates)
    payload["ready_to_freeze_phase_two"] = record.ready_to_freeze_phase_two
    return payload


def serialize_phase_two_acceptance_record(record: PhaseTwoAcceptanceRecord) -> str:
    return json.dumps(
        phase_two_acceptance_record_to_dict(record),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_phase_two_acceptance_record(value: str | bytes) -> PhaseTwoAcceptanceRecord:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("phase two acceptance record is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("phase two acceptance record must be a JSON object")

    payload = dict(raw)
    persisted_ready = payload.pop("ready_to_freeze_phase_two", None)
    persisted_failed = payload.pop("failed_gates", None)
    raw_gates = payload.get("gates")
    persisted_gate_outcomes: list[object] = []
    if isinstance(raw_gates, list):
        for raw_gate in raw_gates:
            if isinstance(raw_gate, dict):
                persisted_gate_outcomes.append(raw_gate.pop("passed", None))
    raw_provider = payload.get("provider")
    persisted_provider_outcome = None
    if isinstance(raw_provider, dict):
        persisted_provider_outcome = raw_provider.pop("passed", None)

    record = PhaseTwoAcceptanceRecord.model_validate(payload)
    expected_gate_outcomes = [gate.passed for gate in record.gates]
    if persisted_gate_outcomes and persisted_gate_outcomes != expected_gate_outcomes:
        raise ValueError("phase two gate outcomes are inconsistent")
    if (
        persisted_provider_outcome is not None
        and persisted_provider_outcome is not record.provider.passed
    ):
        raise ValueError("phase two provider outcome is inconsistent")
    if persisted_failed is not None and persisted_failed != list(record.failed_gates):
        raise ValueError("phase two failed gates are inconsistent")
    if persisted_ready is not None and persisted_ready is not record.ready_to_freeze_phase_two:
        raise ValueError("phase two acceptance decision is inconsistent")
    return record
