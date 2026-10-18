import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.alerts.contracts import AlertDraft
from trd_bot.market_context import MarketTrendRegime


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("alert simulation timestamp must include timezone information")
    return value.astimezone(UTC)


def _normalize_actor(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("alert simulation actor cannot be empty")
    return normalized


def _checksum(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AlertSimulationMode(StrEnum):
    """Offline-only observation mode; neither mode may submit an order."""

    PAPER = "paper"
    SHADOW = "shadow"


class AlertSimulationStatus(StrEnum):
    """Time-derived lifecycle before P4-07 records an outcome."""

    OBSERVING = "observing"
    AWAITING_OUTCOME = "awaiting_outcome"


def build_alert_simulation_id(
    *,
    alert_id: str,
    mode: AlertSimulationMode,
    horizon_seconds: int,
) -> str:
    identity = {
        "alert_id": alert_id,
        "horizon_seconds": horizon_seconds,
        "mode": mode.value,
    }
    return f"alert-simulation-{_checksum(identity)[:16]}"


class AlertSimulationRecord(BaseModel):
    """Immutable enrollment of one published alert in offline observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-simulation-v1"] = "alert-simulation-v1"
    simulation_id: str = Field(pattern=r"^alert-simulation-[a-f0-9]{16}$")
    alert_id: str = Field(pattern=r"^alert-[a-f0-9]{16}$")
    alert_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_reference_id: str = Field(pattern=r"^alert-source-[a-f0-9]{16}$")
    source_reference_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    rule_id: str = Field(pattern=r"^alert-rule-[a-f0-9]{16}$")
    rule_version: int = Field(ge=1)
    rule_definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: AlertSimulationMode
    expected_trend: MarketTrendRegime
    horizon_seconds: int = Field(ge=900, le=2_592_000)
    started_at: datetime
    ends_at: datetime
    started_by: str = Field(min_length=1, max_length=100)
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("started_at", "ends_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("started_by")
    @classmethod
    def normalize_actor(cls, value: str) -> str:
        return _normalize_actor(value)

    @staticmethod
    def _checksum_payload(
        *,
        simulation_id: str,
        alert: AlertDraft,
        mode: AlertSimulationMode,
        horizon_seconds: int,
        started_at: datetime,
        started_by: str,
    ) -> dict[str, object]:
        started = _normalize_timestamp(started_at)
        return {
            "alert_checksum": alert.draft_checksum,
            "alert_id": alert.alert_id,
            "ends_at": (started + timedelta(seconds=horizon_seconds)).isoformat(),
            "expected_trend": alert.source.trend.value,
            "external_order_submission_allowed": False,
            "horizon_seconds": horizon_seconds,
            "mode": mode.value,
            "offline_only": True,
            "rule_definition_checksum": alert.rule.definition_checksum,
            "rule_id": alert.rule.rule_id,
            "rule_version": alert.rule.rule_version,
            "schema_version": "alert-simulation-v1",
            "simulation_id": simulation_id,
            "source_reference_checksum": alert.source.reference_checksum,
            "source_reference_id": alert.source.reference_id,
            "started_at": started.isoformat(),
            "started_by": _normalize_actor(started_by),
        }

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        expected_id = build_alert_simulation_id(
            alert_id=self.alert_id,
            mode=self.mode,
            horizon_seconds=self.horizon_seconds,
        )
        if self.simulation_id != expected_id:
            raise ValueError("alert simulation ID is inconsistent")
        if self.ends_at != self.started_at + timedelta(seconds=self.horizon_seconds):
            raise ValueError("alert simulation horizon is inconsistent")

        payload = {
            "alert_checksum": self.alert_checksum,
            "alert_id": self.alert_id,
            "ends_at": self.ends_at.isoformat(),
            "expected_trend": self.expected_trend.value,
            "external_order_submission_allowed": False,
            "horizon_seconds": self.horizon_seconds,
            "mode": self.mode.value,
            "offline_only": True,
            "rule_definition_checksum": self.rule_definition_checksum,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "schema_version": self.schema_version,
            "simulation_id": self.simulation_id,
            "source_reference_checksum": self.source_reference_checksum,
            "source_reference_id": self.source_reference_id,
            "started_at": self.started_at.isoformat(),
            "started_by": self.started_by,
        }
        if self.record_checksum != _checksum(payload):
            raise ValueError("alert simulation checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        alert: AlertDraft,
        mode: AlertSimulationMode,
        horizon_seconds: int,
        started_at: datetime,
        started_by: str,
    ) -> Self:
        started = _normalize_timestamp(started_at)
        if started < alert.created_at:
            raise ValueError("alert simulation cannot start before alert publication")
        if started >= alert.expires_at:
            raise ValueError("expired alert cannot start an offline simulation")

        simulation_id = build_alert_simulation_id(
            alert_id=alert.alert_id,
            mode=mode,
            horizon_seconds=horizon_seconds,
        )
        payload = cls._checksum_payload(
            simulation_id=simulation_id,
            alert=alert,
            mode=mode,
            horizon_seconds=horizon_seconds,
            started_at=started,
            started_by=started_by,
        )
        return cls(
            simulation_id=simulation_id,
            alert_id=alert.alert_id,
            alert_checksum=alert.draft_checksum,
            source_reference_id=alert.source.reference_id,
            source_reference_checksum=alert.source.reference_checksum,
            rule_id=alert.rule.rule_id,
            rule_version=alert.rule.rule_version,
            rule_definition_checksum=alert.rule.definition_checksum,
            mode=mode,
            expected_trend=alert.source.trend,
            horizon_seconds=horizon_seconds,
            started_at=started,
            ends_at=started + timedelta(seconds=horizon_seconds),
            started_by=started_by,
            record_checksum=_checksum(payload),
        )


class AlertSimulationView(BaseModel):
    """Time-aware projection used by Alert Center and the later outcome journal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-simulation-view-v1"] = "alert-simulation-view-v1"
    simulation: AlertSimulationRecord
    status: AlertSimulationStatus
    evaluated_at: datetime
    seconds_remaining: int = Field(ge=0)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_view(self) -> Self:
        expected_remaining = max(
            0,
            int((self.simulation.ends_at - self.evaluated_at).total_seconds()),
        )
        expected_status = (
            AlertSimulationStatus.OBSERVING
            if expected_remaining > 0
            else AlertSimulationStatus.AWAITING_OUTCOME
        )
        if self.seconds_remaining != expected_remaining or self.status is not expected_status:
            raise ValueError("alert simulation view lifecycle is inconsistent")
        return self

    @classmethod
    def from_record(
        cls,
        record: AlertSimulationRecord,
        *,
        evaluated_at: datetime,
    ) -> Self:
        evaluated = _normalize_timestamp(evaluated_at)
        remaining = max(0, int((record.ends_at - evaluated).total_seconds()))
        return cls(
            simulation=record,
            status=(
                AlertSimulationStatus.OBSERVING
                if remaining > 0
                else AlertSimulationStatus.AWAITING_OUTCOME
            ),
            evaluated_at=evaluated,
            seconds_remaining=remaining,
        )


class AlertSimulationStartResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-simulation-start-result-v1"] = "alert-simulation-start-result-v1"
    created: bool
    view: AlertSimulationView


class AlertSimulationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-simulation-summary-v1"] = "alert-simulation-summary-v1"
    evaluated_at: datetime
    total: int = Field(ge=0)
    paper: int = Field(ge=0)
    shadow: int = Field(ge=0)
    observing: int = Field(ge=0)
    awaiting_outcome: int = Field(ge=0)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.total != self.paper + self.shadow:
            raise ValueError("alert simulation mode totals are inconsistent")
        if self.total != self.observing + self.awaiting_outcome:
            raise ValueError("alert simulation lifecycle totals are inconsistent")
        return self
