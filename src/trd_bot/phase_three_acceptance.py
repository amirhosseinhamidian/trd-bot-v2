import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.market_context import (
    MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES,
    MarketContextGoldenBenchmarkReport,
    MarketContextGoldenScenarioId,
    market_context_feature_set_v1,
    market_context_golden_fixture_v1,
    market_regime_policy_v1,
)
from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
    default_market_data_service_level_policy,
)

PHASE_THREE_GATE_IDS = (
    "repository_contract",
    "market_context_contract",
    "backend",
    "migration_cycle",
    "postgresql_resilience",
    "frontend",
)
PHASE_THREE_BACKGROUND_FIXTURE_REFERENCE = "background-job-workloads-v2+postgresql-queue-v1"
PHASE_THREE_MINIMUM_BACKGROUND_OBSERVATIONS = 410

_GOLDEN_OBSERVATION_KEYS = frozenset(
    f"{scenario_id.value}.{suffix}"
    for scenario_id in MarketContextGoldenScenarioId
    for suffix in ("samples", "runtime_p95_ms")
)
_BACKGROUND_OBSERVATION_KEYS = frozenset(
    {
        "queue_wait_p95_ms",
        "market_context_evaluation.samples",
        "market_context_evaluation.success_fraction",
        "market_context_evaluation.failure_count",
        "market_context_evaluation.runtime_p95_seconds",
        "market_context_evaluation.runtime_target_seconds",
        "market_context_evaluation.runtime_within_target",
        "market_context_evaluation.fixture_finalized_windows",
        "market_context_evaluation.fixture_features",
    }
)


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Phase 3 evidence timestamps must include timezone information")
    return value.astimezone(UTC)


class PhaseThreeCommandEvidence(BaseModel):
    """Sanitized outcome for one command in the final Phase 3 gate."""

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


class PhaseThreeGateEvidence(BaseModel):
    """Ordered command evidence for one automated Phase 3 gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    commands: tuple[PhaseThreeCommandEvidence, ...] = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return all(command.passed for command in self.commands)


class PhaseThreeCiEvidence(BaseModel):
    """GitHub Actions evidence tied to the exact final candidate SHA."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_url: str = Field(
        pattern=r"^https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+$",
        max_length=300,
    )
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    conclusion: Literal["success"]


class PhaseThreeManualEvidence(BaseModel):
    """Owner attestations for observable end-to-end behavior outside deterministic CI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    local_api_worker_frontend: Literal["pass"]
    context_generation_and_ui: Literal["pass"]
    stale_context_fail_closed: Literal["pass"]
    worker_restart_deduplication: Literal["pass"]
    monitoring_freshness_recovery: Literal["pass"]
    security_network_inventory: Literal["pass"]


class PhaseThreePriorFreezeEvidence(BaseModel):
    """Checksummed accepted Phase 2 record anchored in candidate history."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_two_record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    phase_two_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    phase_two_ready: Literal[True]


class PhaseThreeGoldenEvidence(BaseModel):
    """Independently evaluated same-SHA golden context benchmark evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    report_environment_label: str = Field(min_length=1, max_length=64)
    report_generated_at: datetime
    fixture_version: Literal["market-context-golden-v1"] = "market-context-golden-v1"
    fixture_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    feature_set_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    algorithm_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    observations: dict[str, Decimal] = Field(default_factory=dict)
    failure_reasons: tuple[str, ...] = ()

    @field_validator("report_environment_label")
    @classmethod
    def normalize_environment_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("golden evidence environment cannot be empty")
        return normalized

    @field_validator("report_generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_passing_evidence(self) -> Self:
        if self.failure_reasons:
            return self
        fixture = market_context_golden_fixture_v1()
        feature_set = market_context_feature_set_v1()
        policy = market_regime_policy_v1()
        if self.fixture_checksum != fixture.definition_checksum:
            raise ValueError("passing golden evidence requires the canonical fixture checksum")
        if self.algorithm_policy_checksum != policy.definition_checksum:
            raise ValueError("passing golden evidence requires the canonical policy checksum")
        if self.feature_set_checksum != feature_set.definition_checksum:
            raise ValueError("passing golden evidence requires the canonical feature-set checksum")
        if set(self.observations) != _GOLDEN_OBSERVATION_KEYS:
            raise ValueError("passing golden evidence requires every frozen observation")
        runtime_budget_ms = (
            default_market_data_service_level_policy().capacity.job_runtime_p95_seconds[
                "market_context_evaluation"
            ]
            * Decimal(1_000)
        )
        for scenario_id in MarketContextGoldenScenarioId:
            prefix = f"{scenario_id.value}."
            if self.observations[f"{prefix}samples"] < MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES:
                raise ValueError("passing golden evidence has insufficient samples")
            if self.observations[f"{prefix}runtime_p95_ms"] > runtime_budget_ms:
                raise ValueError("passing golden evidence exceeds the runtime budget")
        return self

    @property
    def passed(self) -> bool:
        return not self.failure_reasons


class PhaseThreeBackgroundJobEvidence(BaseModel):
    """Same-SHA capacity evidence for the v2 workload fixture and context job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    report_environment_label: str = Field(min_length=1, max_length=64)
    report_generated_at: datetime
    fixture_reference: str = Field(min_length=1, max_length=100)
    observed_count: int = Field(ge=0)
    observations: dict[str, Decimal] = Field(default_factory=dict)
    failure_reasons: tuple[str, ...] = ()

    @field_validator("report_environment_label", "fixture_reference")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("background-job evidence text cannot be empty")
        return normalized

    @field_validator("report_generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_passing_evidence(self) -> Self:
        if self.failure_reasons:
            return self
        if self.fixture_reference != PHASE_THREE_BACKGROUND_FIXTURE_REFERENCE:
            raise ValueError("passing background-job evidence requires fixture v2")
        if self.observed_count < PHASE_THREE_MINIMUM_BACKGROUND_OBSERVATIONS:
            raise ValueError("passing background-job evidence has insufficient observations")
        if set(self.observations) != _BACKGROUND_OBSERVATION_KEYS:
            raise ValueError("passing background-job evidence requires every frozen observation")
        target_seconds = (
            default_market_data_service_level_policy().capacity.job_runtime_p95_seconds[
                "market_context_evaluation"
            ]
        )
        if self.observations["queue_wait_p95_ms"] > (
            default_market_data_service_level_policy().capacity.job_queue_wait_p95_seconds
            * Decimal(1_000)
        ):
            raise ValueError("passing background-job evidence exceeds the queue-wait budget")
        if self.observations["market_context_evaluation.samples"] < 20:
            raise ValueError("passing background-job evidence has insufficient context samples")
        if self.observations["market_context_evaluation.success_fraction"] != 1:
            raise ValueError("passing background-job evidence requires complete context success")
        if self.observations["market_context_evaluation.failure_count"] != 0:
            raise ValueError("passing background-job evidence cannot contain context failures")
        if (
            self.observations["market_context_evaluation.runtime_target_seconds"] != target_seconds
            or self.observations["market_context_evaluation.runtime_p95_seconds"] > target_seconds
            or self.observations["market_context_evaluation.runtime_within_target"] != 1
        ):
            raise ValueError("passing background-job evidence exceeds the context runtime budget")
        if (
            self.observations["market_context_evaluation.fixture_finalized_windows"] != 56
            or self.observations["market_context_evaluation.fixture_features"] != 5
        ):
            raise ValueError("passing background-job evidence requires the canonical workload")
        return self

    @property
    def passed(self) -> bool:
        return not self.failure_reasons


class PhaseThreeAcceptanceRecord(BaseModel):
    """Auditable, fail-closed decision that freezes the Phase 3 context foundation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["phase-three-acceptance-record-v1"] = "phase-three-acceptance-record-v1"
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    branch: str = Field(min_length=1, max_length=200)
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    scope: Literal["crypto-spot-public-read-only"] = "crypto-spot-public-read-only"
    database_name: Literal["trd_bot_test"] = "trd_bot_test"
    worktree_clean_at_start: Literal[True] = True
    prior_freeze: PhaseThreePriorFreezeEvidence
    golden: PhaseThreeGoldenEvidence
    background_jobs: PhaseThreeBackgroundJobEvidence
    ci: PhaseThreeCiEvidence
    manual: PhaseThreeManualEvidence
    gates: tuple[PhaseThreeGateEvidence, ...] = Field(min_length=1)

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
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if tuple(gate.gate_id for gate in self.gates) != PHASE_THREE_GATE_IDS:
            raise ValueError("acceptance record must contain every Phase 3 gate in order")
        if self.ci.head_sha != self.commit_sha:
            raise ValueError("GitHub Actions head SHA must match the accepted commit")
        for label, report_sha, report_environment, report_generated_at in (
            (
                "golden",
                self.golden.report_commit_sha,
                self.golden.report_environment_label,
                self.golden.report_generated_at,
            ),
            (
                "background-job",
                self.background_jobs.report_commit_sha,
                self.background_jobs.report_environment_label,
                self.background_jobs.report_generated_at,
            ),
        ):
            if report_sha != self.commit_sha:
                raise ValueError(f"{label} report SHA must match the accepted commit")
            if report_environment != self.environment_label:
                raise ValueError(f"{label} report environment must match acceptance")
            maximum_age = timedelta(
                days=default_market_data_service_level_policy().retention.benchmark_evidence_days
            )
            evidence_age = self.generated_at - report_generated_at
            if evidence_age < timedelta(0) or evidence_age > maximum_age:
                raise ValueError(f"{label} report must be current at acceptance time")
        return self

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(gate.gate_id for gate in self.gates if not gate.passed)

    @property
    def ready_to_freeze_phase_three(self) -> bool:
        return not self.failed_gates and self.golden.passed and self.background_jobs.passed


def evaluate_phase_three_golden_evidence(
    report: MarketContextGoldenBenchmarkReport,
    *,
    report_checksum: str,
) -> PhaseThreeGoldenEvidence:
    reasons: list[str] = []
    observations: dict[str, Decimal] = {}
    for scenario in report.scenarios:
        prefix = f"{scenario.scenario_id.value}."
        observations[f"{prefix}samples"] = Decimal(scenario.requested_samples)
        observations[f"{prefix}runtime_p95_ms"] = scenario.runtime_p95_ms
        if not scenario.passed:
            reasons.append(f'golden scenario "{scenario.scenario_id.value}" did not pass')
    if not report.ready_for_phase_three_acceptance:
        reasons.append("golden benchmark is not ready for Phase 3 acceptance")
    return PhaseThreeGoldenEvidence(
        report_checksum=report_checksum,
        report_commit_sha=report.commit_sha,
        report_environment_label=report.environment_label,
        report_generated_at=report.generated_at,
        fixture_checksum=report.fixture_checksum,
        feature_set_checksum=report.feature_set_checksum,
        algorithm_policy_checksum=report.algorithm_policy_checksum,
        observations=observations,
        failure_reasons=tuple(reasons),
    )


def evaluate_phase_three_background_job_evidence(
    report: CapacityBenchmarkReport,
    *,
    report_checksum: str,
) -> PhaseThreeBackgroundJobEvidence:
    evidence = next(
        (item for item in report.evidence if item.scope is CapacityEvidenceScope.BACKGROUND_JOBS),
        None,
    )
    reasons: list[str] = []
    observations: dict[str, Decimal] = {}
    fixture_reference = "missing"
    observed_count = 0
    if evidence is None:
        reasons.append("background-job evidence scope is missing")
    else:
        fixture_reference = evidence.evidence_reference or "missing"
        observed_count = evidence.observed_count
        if not evidence.complete:
            reasons.append("background-job evidence scope is incomplete")
        if evidence.method is not CapacityEvidenceMethod.SYNTHETIC_BENCHMARK:
            reasons.append("background-job evidence is not a synthetic benchmark")
        if fixture_reference != PHASE_THREE_BACKGROUND_FIXTURE_REFERENCE:
            reasons.append("background-job evidence does not use fixture v2")
        for metric_name in sorted(_BACKGROUND_OBSERVATION_KEYS):
            value = evidence.metrics.get(metric_name)
            if value is None:
                reasons.append(f'missing background-job metric "{metric_name}"')
            else:
                observations[metric_name] = value

    if evidence is not None:
        target_seconds = (
            default_market_data_service_level_policy().capacity.job_runtime_p95_seconds[
                "market_context_evaluation"
            ]
        )
        checks = (
            (
                evidence.observed_count >= PHASE_THREE_MINIMUM_BACKGROUND_OBSERVATIONS,
                "background-job evidence has insufficient observations",
            ),
            (
                observations.get("queue_wait_p95_ms", Decimal("Infinity"))
                <= default_market_data_service_level_policy().capacity.job_queue_wait_p95_seconds
                * Decimal(1_000),
                "background-job queue wait exceeds its budget",
            ),
            (
                observations.get("market_context_evaluation.samples", Decimal(0)) >= 20,
                "market-context workload has insufficient samples",
            ),
            (
                observations.get("market_context_evaluation.success_fraction", Decimal(0)) == 1,
                "market-context workload did not succeed completely",
            ),
            (
                observations.get("market_context_evaluation.failure_count", Decimal(1)) == 0,
                "market-context workload recorded failures",
            ),
            (
                observations.get(
                    "market_context_evaluation.runtime_target_seconds",
                    Decimal(0),
                )
                == target_seconds,
                "market-context workload target is inconsistent",
            ),
            (
                observations.get(
                    "market_context_evaluation.runtime_p95_seconds",
                    Decimal("Infinity"),
                )
                <= target_seconds,
                "market-context workload exceeds its runtime budget",
            ),
            (
                observations.get(
                    "market_context_evaluation.runtime_within_target",
                    Decimal(0),
                )
                == 1,
                "market-context workload runtime decision is not accepted",
            ),
            (
                observations.get(
                    "market_context_evaluation.fixture_finalized_windows",
                    Decimal(0),
                )
                == 56,
                "market-context workload window fixture is inconsistent",
            ),
            (
                observations.get("market_context_evaluation.fixture_features", Decimal(0)) == 5,
                "market-context workload feature fixture is inconsistent",
            ),
        )
        reasons.extend(message for passed, message in checks if not passed)

    return PhaseThreeBackgroundJobEvidence(
        report_checksum=report_checksum,
        report_commit_sha=report.commit_sha,
        report_environment_label=report.environment_label,
        report_generated_at=report.generated_at,
        fixture_reference=fixture_reference,
        observed_count=observed_count,
        observations=observations,
        failure_reasons=tuple(reasons),
    )


def phase_three_acceptance_record_to_dict(
    record: PhaseThreeAcceptanceRecord,
) -> dict[str, object]:
    payload = record.model_dump(mode="json")
    gates = payload["gates"]
    if not isinstance(gates, list):
        raise TypeError("serialized Phase 3 gates must be a list")
    for gate_payload, gate in zip(gates, record.gates, strict=True):
        if not isinstance(gate_payload, dict):
            raise TypeError("serialized Phase 3 gate must be an object")
        gate_payload["passed"] = gate.passed
    for field_name, passed in (
        ("golden", record.golden.passed),
        ("background_jobs", record.background_jobs.passed),
    ):
        evidence = payload[field_name]
        if not isinstance(evidence, dict):
            raise TypeError("serialized Phase 3 evidence must be an object")
        evidence["passed"] = passed
    payload["failed_gates"] = list(record.failed_gates)
    payload["ready_to_freeze_phase_three"] = record.ready_to_freeze_phase_three
    return payload


def serialize_phase_three_acceptance_record(record: PhaseThreeAcceptanceRecord) -> str:
    return json.dumps(
        phase_three_acceptance_record_to_dict(record),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_phase_three_acceptance_record(value: str | bytes) -> PhaseThreeAcceptanceRecord:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("phase three acceptance record is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("phase three acceptance record must be a JSON object")

    payload = dict(raw)
    persisted_ready = payload.pop("ready_to_freeze_phase_three", None)
    persisted_failed = payload.pop("failed_gates", None)
    raw_gates = payload.get("gates")
    persisted_gate_outcomes: list[object] = []
    if isinstance(raw_gates, list):
        for raw_gate in raw_gates:
            if isinstance(raw_gate, dict):
                persisted_gate_outcomes.append(raw_gate.pop("passed", None))
    persisted_evidence_outcomes: dict[str, object] = {}
    for field_name in ("golden", "background_jobs"):
        raw_evidence = payload.get(field_name)
        if isinstance(raw_evidence, dict):
            persisted_evidence_outcomes[field_name] = raw_evidence.pop("passed", None)

    record = PhaseThreeAcceptanceRecord.model_validate(payload)
    if persisted_gate_outcomes and persisted_gate_outcomes != [
        gate.passed for gate in record.gates
    ]:
        raise ValueError("phase three gate outcomes are inconsistent")
    expected_evidence_outcomes = {
        "golden": record.golden.passed,
        "background_jobs": record.background_jobs.passed,
    }
    if persisted_evidence_outcomes and persisted_evidence_outcomes != expected_evidence_outcomes:
        raise ValueError("phase three evidence outcomes are inconsistent")
    if persisted_failed is not None and persisted_failed != list(record.failed_gates):
        raise ValueError("phase three failed gates are inconsistent")
    if persisted_ready is not None and persisted_ready is not record.ready_to_freeze_phase_three:
        raise ValueError("phase three acceptance decision is inconsistent")
    return record
