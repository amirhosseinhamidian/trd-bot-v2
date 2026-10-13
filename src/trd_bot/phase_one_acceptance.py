import json
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PHASE_ONE_GATE_IDS = (
    "repository_contract",
    "backend",
    "migration_cycle",
    "postgresql_recovery",
    "frontend",
)


class PhaseOneCommandEvidence(BaseModel):
    """Sanitized outcome for one acceptance command."""

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


class PhaseOneGateEvidence(BaseModel):
    """Ordered command evidence for one final Phase 1 gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    commands: tuple[PhaseOneCommandEvidence, ...] = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return all(command.passed for command in self.commands)


class PhaseOneCiEvidence(BaseModel):
    """Operator-recorded GitHub Actions evidence for the same candidate SHA."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_url: str = Field(
        pattern=r"^https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+$",
        max_length=300,
    )
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    conclusion: Literal["success"]


class PhaseOneManualEvidence(BaseModel):
    """Explicit owner attestations for checks that cannot be inferred from CI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    local_api_worker_frontend: Literal["pass"]
    durable_workload_restart: Literal["pass"]
    monitoring_recovery: Literal["pass"]
    security_network_inventory: Literal["pass"]


class PhaseOneAcceptanceRecord(BaseModel):
    """Auditable, fail-closed decision for entry from P1 into P2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["phase-one-acceptance-record-v1"] = "phase-one-acceptance-record-v1"
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    branch: str = Field(min_length=1, max_length=200)
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    database_name: Literal["trd_bot_test"] = "trd_bot_test"
    worktree_clean_at_start: Literal[True] = True
    ci: PhaseOneCiEvidence
    manual: PhaseOneManualEvidence
    gates: tuple[PhaseOneGateEvidence, ...] = Field(min_length=1)

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
        if gate_ids != PHASE_ONE_GATE_IDS:
            raise ValueError("acceptance record must contain every Phase 1 gate in order")
        if self.ci.head_sha != self.commit_sha:
            raise ValueError("GitHub Actions head SHA must match the accepted commit")
        return self

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(gate.gate_id for gate in self.gates if not gate.passed)

    @property
    def ready_to_enter_phase_two(self) -> bool:
        return not self.failed_gates


def phase_one_acceptance_record_to_dict(record: PhaseOneAcceptanceRecord) -> dict[str, object]:
    payload = record.model_dump(mode="json")
    gates = payload["gates"]
    if not isinstance(gates, list):
        raise TypeError("serialized Phase 1 gates must be a list")
    for gate_payload, gate in zip(gates, record.gates, strict=True):
        if not isinstance(gate_payload, dict):
            raise TypeError("serialized Phase 1 gate must be an object")
        gate_payload["passed"] = gate.passed
    payload["failed_gates"] = list(record.failed_gates)
    payload["ready_to_enter_phase_two"] = record.ready_to_enter_phase_two
    return payload


def serialize_phase_one_acceptance_record(record: PhaseOneAcceptanceRecord) -> str:
    return json.dumps(
        phase_one_acceptance_record_to_dict(record),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_phase_one_acceptance_record(value: str | bytes) -> PhaseOneAcceptanceRecord:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("phase one acceptance record is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("phase one acceptance record must be a JSON object")

    payload = dict(raw)
    persisted_ready = payload.pop("ready_to_enter_phase_two", None)
    persisted_failed = payload.pop("failed_gates", None)
    raw_gates = payload.get("gates")
    persisted_gate_outcomes: list[object] = []
    if isinstance(raw_gates, list):
        for raw_gate in raw_gates:
            if isinstance(raw_gate, dict):
                persisted_gate_outcomes.append(raw_gate.pop("passed", None))

    record = PhaseOneAcceptanceRecord.model_validate(payload)
    expected_gate_outcomes = [gate.passed for gate in record.gates]
    if persisted_gate_outcomes and persisted_gate_outcomes != expected_gate_outcomes:
        raise ValueError("phase one gate outcomes are inconsistent")
    if persisted_failed is not None and persisted_failed != list(record.failed_gates):
        raise ValueError("phase one failed gates are inconsistent")
    if persisted_ready is not None and persisted_ready is not record.ready_to_enter_phase_two:
        raise ValueError("phase one acceptance decision is inconsistent")
    return record
