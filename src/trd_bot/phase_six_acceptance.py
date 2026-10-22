import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.outcome_learning import OutcomeLearningReadiness, OutcomeLearningReview
from trd_bot.release_capacity import ReleaseCapacityBenchmarkReport
from trd_bot.release_hardening import ReleaseHardeningReport
from trd_bot.release_installation import ReleaseInstallationVerificationReport
from trd_bot.release_maintenance import ReleaseMaintenancePlan

PHASE_SIX_ACCEPTANCE_SCHEMA_VERSION = "phase-six-acceptance-record-v1"
PHASE_SIX_MAX_EVIDENCE_AGE = timedelta(days=7)
PHASE_SIX_GATE_IDS = (
    "release_contract",
    "phase_six_contract",
    "backend",
    "migration_cycle",
    "postgresql_resilience",
    "frontend",
)


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Phase 6 evidence timestamps must include timezone information")
    return value.astimezone(UTC)


class PhaseSixCommandEvidence(BaseModel):
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


class PhaseSixGateEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    commands: tuple[PhaseSixCommandEvidence, ...] = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.commands)


class PhaseSixPriorFreezeEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_five_record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    phase_five_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    phase_five_ready: Literal[True]


class PhaseSixCapacityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    passed: Literal[True]

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _timestamp(value)


class PhaseSixOutcomeLearningEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    readiness: OutcomeLearningReadiness
    human_review_required: bool
    offline_only: Literal[True]
    automatic_policy_updates_applied: Literal[False]
    production_ml_training_performed: Literal[False]

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _timestamp(value)


class PhaseSixMaintenanceEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    human_approval_required: Literal[False]
    retention_dry_run_audit_written: Literal[True]
    automatic_maintenance_executed: Literal[False]
    immutable_evidence_deletion_allowed: Literal[False]

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _timestamp(value)


class PhaseSixInstallationEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    source_migration_revision: Literal["20260926_0017"]
    target_migration_revision: Literal["20261020_0036"]
    release_inventory_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    passed: Literal[True]

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _timestamp(value)


class PhaseSixInventoryEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    product_version: Literal["0.3.0"]
    counts: dict[str, int]
    passed: Literal[True]

    @field_validator("counts")
    @classmethod
    def validate_counts(cls, value: dict[str, int]) -> dict[str, int]:
        expected = {
            "api_operations",
            "database_tables",
            "frontend_pages",
            "jobs",
            "migration_heads",
            "migration_revisions",
            "providers",
        }
        if set(value) != expected or any(count < 1 for count in value.values()):
            raise ValueError("Phase 6 release inventory counts are incomplete")
        return value


class PhaseSixCiEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_url: str = Field(
        pattern=r"^https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+$",
        max_length=300,
    )
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    conclusion: Literal["success"]


class PhaseSixManualEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fresh_install_upgrade_and_restore: Literal["pass"]
    api_worker_ui_lifecycle: Literal["pass"]
    outcome_learning_human_review: Literal["pass"]
    retention_maintenance_closed: Literal["pass"]
    paper_shadow_decision_lineage: Literal["pass"]
    no_live_trading_security_inventory: Literal["pass"]


class PhaseSixAcceptanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["phase-six-acceptance-record-v1"] = "phase-six-acceptance-record-v1"
    candidate_commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    branch: str = Field(min_length=1, max_length=200)
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    release_version: Literal["0.3.0"] = "0.3.0"
    scope: Literal["crypto-spot-public-read-only-research-shadow-paper"] = (
        "crypto-spot-public-read-only-research-shadow-paper"
    )
    database_name: Literal["trd_bot_test"] = "trd_bot_test"
    worktree_clean_at_start: Literal[True] = True
    freeze_commit_policy: Literal["acceptance-artifact-only"] = "acceptance-artifact-only"
    prior_freeze: PhaseSixPriorFreezeEvidence
    capacity: PhaseSixCapacityEvidence
    outcome_learning: PhaseSixOutcomeLearningEvidence
    maintenance: PhaseSixMaintenanceEvidence
    installation: PhaseSixInstallationEvidence
    inventory: PhaseSixInventoryEvidence
    ci: PhaseSixCiEvidence
    manual: PhaseSixManualEvidence
    gates: tuple[PhaseSixGateEvidence, ...] = Field(min_length=1)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _timestamp(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if tuple(item.gate_id for item in self.gates) != PHASE_SIX_GATE_IDS:
            raise ValueError("acceptance record must contain every Phase 6 gate in order")
        if self.ci.head_sha != self.candidate_commit_sha:
            raise ValueError("GitHub Actions head SHA must match the accepted candidate")
        artifacts = (self.capacity, self.outcome_learning, self.maintenance, self.installation)
        if any(item.commit_sha != self.candidate_commit_sha for item in artifacts):
            raise ValueError("every Phase 6 artifact SHA must match the accepted candidate")
        if any(item.environment_label != self.environment_label for item in artifacts):
            raise ValueError("every Phase 6 artifact environment must match acceptance")
        for item in artifacts:
            age = self.generated_at - item.generated_at
            if age < timedelta() or age > PHASE_SIX_MAX_EVIDENCE_AGE:
                raise ValueError("Phase 6 artifact evidence must be current at acceptance time")
        if self.installation.release_inventory_checksum != self.inventory.definition_checksum:
            raise ValueError("installation and release inventory checksums must match")
        return self

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(item.gate_id for item in self.gates if not item.passed)

    @property
    def ready_to_freeze_v0_3(self) -> bool:
        return not self.failed_gates

    @property
    def record_checksum(self) -> str:
        return _checksum(self.model_dump(mode="json"))


def capacity_evidence(
    report: ReleaseCapacityBenchmarkReport,
    *,
    artifact_checksum: str,
) -> PhaseSixCapacityEvidence:
    if not report.passed:
        raise ValueError("Phase 6 capacity report did not pass")
    return PhaseSixCapacityEvidence(
        artifact_checksum=artifact_checksum,
        report_checksum=report.report_checksum,
        commit_sha=report.commit_sha,
        environment_label=report.environment_label,
        generated_at=report.generated_at,
        policy_checksum=report.policy.definition_checksum,
        passed=True,
    )


def outcome_learning_evidence(
    review: OutcomeLearningReview,
    *,
    artifact_checksum: str,
) -> PhaseSixOutcomeLearningEvidence:
    return PhaseSixOutcomeLearningEvidence(
        artifact_checksum=artifact_checksum,
        report_checksum=review.report_checksum,
        commit_sha=review.commit_sha,
        environment_label=review.environment_label,
        generated_at=review.generated_at,
        policy_checksum=review.policy.definition_checksum,
        readiness=review.readiness,
        human_review_required=review.human_review_required,
        offline_only=review.offline_only,
        automatic_policy_updates_applied=review.automatic_policy_updates_applied,
        production_ml_training_performed=review.production_ml_training_performed,
    )


def maintenance_evidence(
    plan: ReleaseMaintenancePlan,
    *,
    artifact_checksum: str,
) -> PhaseSixMaintenanceEvidence:
    if plan.human_approval_required:
        raise ValueError("Phase 6 maintenance plan still has required, review, or blocked work")
    return PhaseSixMaintenanceEvidence(
        artifact_checksum=artifact_checksum,
        report_checksum=plan.report_checksum,
        commit_sha=plan.commit_sha,
        environment_label=plan.environment_label,
        generated_at=plan.generated_at,
        policy_checksum=plan.policy.definition_checksum,
        human_approval_required=False,
        retention_dry_run_audit_written=plan.retention_dry_run_audit_written,
        automatic_maintenance_executed=plan.automatic_maintenance_executed,
        immutable_evidence_deletion_allowed=plan.immutable_evidence_deletion_allowed,
    )


def installation_evidence(
    report: ReleaseInstallationVerificationReport,
    *,
    artifact_checksum: str,
) -> PhaseSixInstallationEvidence:
    if not report.passed:
        raise ValueError("Phase 6 installation verification did not pass")
    return PhaseSixInstallationEvidence(
        artifact_checksum=artifact_checksum,
        report_checksum=report.report_checksum,
        commit_sha=report.commit_sha,
        environment_label=report.environment_label,
        generated_at=report.generated_at,
        source_migration_revision=report.source_migration_revision,
        target_migration_revision=report.target_migration_revision,
        release_inventory_checksum=report.release_inventory_checksum,
        passed=True,
    )


def inventory_evidence(report: ReleaseHardeningReport) -> PhaseSixInventoryEvidence:
    if not report.passed:
        raise ValueError("Phase 6 release inventory did not pass")
    if report.inventory.product_version != "0.3.0":
        raise ValueError("Phase 6 release inventory is not for v0.3.0")
    return PhaseSixInventoryEvidence(
        definition_checksum=report.inventory.definition_checksum,
        product_version="0.3.0",
        counts=report.inventory.counts,
        passed=True,
    )


def phase_six_acceptance_record_to_dict(
    record: PhaseSixAcceptanceRecord,
) -> dict[str, object]:
    payload = record.model_dump(mode="json")
    for raw, gate in zip(payload["gates"], record.gates, strict=True):
        raw["passed"] = gate.passed
    payload["failed_gates"] = list(record.failed_gates)
    payload["ready_to_freeze_v0_3"] = record.ready_to_freeze_v0_3
    payload["record_checksum"] = record.record_checksum
    return payload


def serialize_phase_six_acceptance_record(record: PhaseSixAcceptanceRecord) -> str:
    return json.dumps(phase_six_acceptance_record_to_dict(record), indent=2, sort_keys=True)


def parse_phase_six_acceptance_record(value: str | bytes) -> PhaseSixAcceptanceRecord:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("phase six acceptance record is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("phase six acceptance record must be a JSON object")
    payload = dict(raw)
    persisted_failed = payload.pop("failed_gates", None)
    persisted_ready = payload.pop("ready_to_freeze_v0_3", None)
    persisted_checksum = payload.pop("record_checksum", None)
    raw_gates = payload.get("gates")
    persisted_gate_outcomes: list[object] = []
    if isinstance(raw_gates, list):
        clean_gates: list[object] = []
        for raw_gate in raw_gates:
            if isinstance(raw_gate, dict):
                gate = dict(raw_gate)
                persisted_gate_outcomes.append(gate.pop("passed", None))
                clean_gates.append(gate)
            else:
                clean_gates.append(raw_gate)
        payload["gates"] = clean_gates
    record = PhaseSixAcceptanceRecord.model_validate(payload)
    if persisted_failed is not None and persisted_failed != list(record.failed_gates):
        raise ValueError("phase six failed gates are inconsistent")
    if persisted_ready is not None and persisted_ready is not record.ready_to_freeze_v0_3:
        raise ValueError("phase six freeze outcome is inconsistent")
    if persisted_checksum is not None and persisted_checksum != record.record_checksum:
        raise ValueError("phase six acceptance checksum is inconsistent")
    if persisted_gate_outcomes and persisted_gate_outcomes != [
        gate.passed for gate in record.gates
    ]:
        raise ValueError("phase six gate outcomes are inconsistent")
    return record


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _checksum(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
