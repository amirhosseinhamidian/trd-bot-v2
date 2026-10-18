import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.alerts.contracts import AlertDraft


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("alert inbox timestamp must include timezone information")
    return value.astimezone(UTC)


def _normalize_actor(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("alert action actor cannot be empty")
    return normalized


def _checksum(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AlertInboxStatus(StrEnum):
    ACTIVE = "active"
    SNOOZED = "snoozed"
    ACKNOWLEDGED = "acknowledged"
    EXPIRED = "expired"


class AlertActionKind(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    SNOOZED = "snoozed"


class AlertInboxState(BaseModel):
    """Mutable operator state kept separately from an immutable alert draft."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-inbox-state-v1"] = "alert-inbox-state-v1"
    alert_id: str = Field(pattern=r"^alert-[a-f0-9]{16}$")
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = Field(default=None, min_length=1, max_length=100)
    snoozed_until: datetime | None = None
    snoozed_by: str | None = Field(default=None, min_length=1, max_length=100)
    updated_at: datetime

    @field_validator("acknowledged_at", "snoozed_until", "updated_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @field_validator("acknowledged_by", "snoozed_by")
    @classmethod
    def normalize_actors(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_actor(value)

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if (self.acknowledged_at is None) != (self.acknowledged_by is None):
            raise ValueError("alert acknowledgement fields must be set together")
        if (self.snoozed_until is None) != (self.snoozed_by is None):
            raise ValueError("alert snooze fields must be set together")
        if self.acknowledged_at is not None:
            if self.snoozed_until is not None:
                raise ValueError("acknowledged alert cannot remain snoozed")
            if self.updated_at < self.acknowledged_at:
                raise ValueError("alert state update cannot precede acknowledgement")
        return self

    @classmethod
    def initial(cls, *, alert_id: str, created_at: datetime) -> Self:
        return cls(alert_id=alert_id, updated_at=created_at)

    def acknowledge(self, *, acted_by: str, occurred_at: datetime) -> Self:
        occurred = _normalize_timestamp(occurred_at)
        if self.acknowledged_at is not None:
            return self
        if occurred < self.updated_at:
            raise ValueError("alert acknowledgement cannot precede its current state")
        return self.model_copy(
            update={
                "acknowledged_at": occurred,
                "acknowledged_by": _normalize_actor(acted_by),
                "snoozed_until": None,
                "snoozed_by": None,
                "updated_at": occurred,
            }
        )

    def snooze(
        self,
        *,
        acted_by: str,
        occurred_at: datetime,
        duration_seconds: int,
    ) -> Self:
        occurred = _normalize_timestamp(occurred_at)
        if self.acknowledged_at is not None:
            raise ValueError("acknowledged alert cannot be snoozed")
        if occurred < self.updated_at:
            raise ValueError("alert snooze cannot precede its current state")
        if duration_seconds < 300 or duration_seconds > 86_400:
            raise ValueError("alert snooze duration must be between 300 and 86400 seconds")
        return self.model_copy(
            update={
                "snoozed_until": occurred + timedelta(seconds=duration_seconds),
                "snoozed_by": _normalize_actor(acted_by),
                "updated_at": occurred,
            }
        )


class AlertActionRecord(BaseModel):
    """Immutable audit evidence for an operator acknowledgement or snooze."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-action-v1"] = "alert-action-v1"
    action_id: str = Field(pattern=r"^alert-action-[a-f0-9]{16}$")
    alert_id: str = Field(pattern=r"^alert-[a-f0-9]{16}$")
    kind: AlertActionKind
    acted_by: str = Field(min_length=1, max_length=100)
    occurred_at: datetime
    snoozed_until: datetime | None = None
    action_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("acted_by")
    @classmethod
    def normalize_acted_by(cls, value: str) -> str:
        return _normalize_actor(value)

    @field_validator("occurred_at", "snoozed_until")
    @classmethod
    def normalize_action_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @staticmethod
    def _payload(
        *,
        alert_id: str,
        kind: AlertActionKind,
        acted_by: str,
        occurred_at: datetime,
        snoozed_until: datetime | None,
    ) -> dict[str, object]:
        return {
            "acted_by": _normalize_actor(acted_by),
            "alert_id": alert_id,
            "kind": kind.value,
            "occurred_at": _normalize_timestamp(occurred_at).isoformat(),
            "schema_version": "alert-action-v1",
            "snoozed_until": (
                None if snoozed_until is None else _normalize_timestamp(snoozed_until).isoformat()
            ),
        }

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if (self.kind is AlertActionKind.SNOOZED) != (self.snoozed_until is not None):
            raise ValueError("only a snooze action may contain snoozed_until")
        if self.snoozed_until is not None and self.snoozed_until <= self.occurred_at:
            raise ValueError("alert snooze must end after the action time")
        checksum = _checksum(
            self._payload(
                alert_id=self.alert_id,
                kind=self.kind,
                acted_by=self.acted_by,
                occurred_at=self.occurred_at,
                snoozed_until=self.snoozed_until,
            )
        )
        if self.action_checksum != checksum:
            raise ValueError("alert action checksum is inconsistent")
        if self.action_id != f"alert-action-{checksum[:16]}":
            raise ValueError("alert action ID is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        alert_id: str,
        kind: AlertActionKind,
        acted_by: str,
        occurred_at: datetime,
        snoozed_until: datetime | None = None,
    ) -> Self:
        payload = cls._payload(
            alert_id=alert_id,
            kind=kind,
            acted_by=acted_by,
            occurred_at=occurred_at,
            snoozed_until=snoozed_until,
        )
        checksum = _checksum(payload)
        return cls(
            action_id=f"alert-action-{checksum[:16]}",
            alert_id=alert_id,
            kind=kind,
            acted_by=acted_by,
            occurred_at=occurred_at,
            snoozed_until=snoozed_until,
            action_checksum=checksum,
        )


class AlertInboxItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-inbox-item-v1"] = "alert-inbox-item-v1"
    alert: AlertDraft
    state: AlertInboxState
    status: AlertInboxStatus
    evaluated_at: datetime
    seconds_until_expiry: int = Field(ge=0)
    seconds_until_unsnooze: int = Field(ge=0)
    can_acknowledge: bool
    can_snooze: bool

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @classmethod
    def build(
        cls,
        *,
        alert: AlertDraft,
        state: AlertInboxState,
        evaluated_at: datetime,
    ) -> Self:
        evaluated = _normalize_timestamp(evaluated_at)
        if alert.alert_id != state.alert_id:
            raise ValueError("alert inbox state does not belong to its draft")
        if state.acknowledged_at is not None:
            status = AlertInboxStatus.ACKNOWLEDGED
        elif alert.expires_at <= evaluated:
            status = AlertInboxStatus.EXPIRED
        elif state.snoozed_until is not None and state.snoozed_until > evaluated:
            status = AlertInboxStatus.SNOOZED
        else:
            status = AlertInboxStatus.ACTIVE
        actionable = status not in {
            AlertInboxStatus.ACKNOWLEDGED,
            AlertInboxStatus.EXPIRED,
        }
        return cls(
            alert=alert,
            state=state,
            status=status,
            evaluated_at=evaluated,
            seconds_until_expiry=max(int((alert.expires_at - evaluated).total_seconds()), 0),
            seconds_until_unsnooze=(
                max(int((state.snoozed_until - evaluated).total_seconds()), 0)
                if state.snoozed_until is not None
                else 0
            ),
            can_acknowledge=actionable,
            can_snooze=actionable,
        )


class AlertInboxSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-inbox-summary-v1"] = "alert-inbox-summary-v1"
    evaluated_at: datetime
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    snoozed: int = Field(ge=0)
    acknowledged: int = Field(ge=0)
    expired: int = Field(ge=0)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_summary_time(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.total != self.active + self.snoozed + self.acknowledged + self.expired:
            raise ValueError("alert inbox summary counts must partition total")
        return self


class AlertActionConflictError(ValueError):
    def __init__(self, *, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
