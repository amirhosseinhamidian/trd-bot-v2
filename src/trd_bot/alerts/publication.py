import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.alerts.contracts import AlertSeverity, AlertSuppressionReason

DEFAULT_ALERT_PUBLICATION_POLICY_ID: Literal["alert-publication-policy-default"] = (
    "alert-publication-policy-default"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("alert publication timestamp must include timezone information")
    return value.astimezone(UTC)


def _normalize_actor(value: str) -> str:
    actor = value.strip()
    if not actor:
        raise ValueError("alert publication actor cannot be empty")
    return actor


class AlertPublicationPolicy(BaseModel):
    """Immutable revision of the operator's in-app publication preferences."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-publication-policy-v1"] = "alert-publication-policy-v1"
    policy_id: Literal["alert-publication-policy-default"] = DEFAULT_ALERT_PUBLICATION_POLICY_ID
    policy_version: int = Field(ge=0)
    quiet_hours_enabled: bool
    quiet_hours_start_minute: int = Field(ge=0, le=1439)
    quiet_hours_end_minute: int = Field(ge=0, le=1439)
    timezone_name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_+./-]+$")
    critical_bypass_quiet_hours: bool
    updated_by: str = Field(min_length=1, max_length=100)
    updated_at: datetime
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("updated_by")
    @classmethod
    def normalize_updated_by(cls, value: str) -> str:
        return _normalize_actor(value)

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("timezone_name")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("alert publication timezone is unknown") from error
        return value

    @staticmethod
    def _checksum_payload(
        *,
        policy_version: int,
        quiet_hours_enabled: bool,
        quiet_hours_start_minute: int,
        quiet_hours_end_minute: int,
        timezone_name: str,
        critical_bypass_quiet_hours: bool,
        updated_by: str,
        updated_at: datetime,
    ) -> dict[str, object]:
        return {
            "critical_bypass_quiet_hours": critical_bypass_quiet_hours,
            "policy_id": DEFAULT_ALERT_PUBLICATION_POLICY_ID,
            "policy_version": policy_version,
            "quiet_hours_enabled": quiet_hours_enabled,
            "quiet_hours_end_minute": quiet_hours_end_minute,
            "quiet_hours_start_minute": quiet_hours_start_minute,
            "schema_version": "alert-publication-policy-v1",
            "timezone_name": timezone_name,
            "updated_at": _normalize_timestamp(updated_at).isoformat(),
            "updated_by": _normalize_actor(updated_by),
        }

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if (
            self.quiet_hours_enabled
            and self.quiet_hours_start_minute == self.quiet_hours_end_minute
        ):
            raise ValueError("enabled quiet hours require distinct start and end times")
        expected = _checksum(
            self._checksum_payload(
                policy_version=self.policy_version,
                quiet_hours_enabled=self.quiet_hours_enabled,
                quiet_hours_start_minute=self.quiet_hours_start_minute,
                quiet_hours_end_minute=self.quiet_hours_end_minute,
                timezone_name=self.timezone_name,
                critical_bypass_quiet_hours=self.critical_bypass_quiet_hours,
                updated_by=self.updated_by,
                updated_at=self.updated_at,
            )
        )
        if self.policy_checksum != expected:
            raise ValueError("alert publication policy checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        policy_version: int,
        quiet_hours_enabled: bool,
        quiet_hours_start_minute: int,
        quiet_hours_end_minute: int,
        timezone_name: str,
        critical_bypass_quiet_hours: bool,
        updated_by: str,
        updated_at: datetime,
    ) -> Self:
        payload = cls._checksum_payload(
            policy_version=policy_version,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_hours_start_minute=quiet_hours_start_minute,
            quiet_hours_end_minute=quiet_hours_end_minute,
            timezone_name=timezone_name,
            critical_bypass_quiet_hours=critical_bypass_quiet_hours,
            updated_by=updated_by,
            updated_at=updated_at,
        )
        return cls(
            policy_version=policy_version,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_hours_start_minute=quiet_hours_start_minute,
            quiet_hours_end_minute=quiet_hours_end_minute,
            timezone_name=timezone_name,
            critical_bypass_quiet_hours=critical_bypass_quiet_hours,
            updated_by=updated_by,
            updated_at=updated_at,
            policy_checksum=_checksum(payload),
        )

    @classmethod
    def default(cls) -> Self:
        return cls.build(
            policy_version=0,
            quiet_hours_enabled=False,
            quiet_hours_start_minute=22 * 60,
            quiet_hours_end_minute=7 * 60,
            timezone_name="UTC",
            critical_bypass_quiet_hours=True,
            updated_by="system:default",
            updated_at=datetime(1970, 1, 1, tzinfo=UTC),
        )

    def quiet_hours_end(self, *, evaluated_at: datetime) -> datetime | None:
        if not self.quiet_hours_enabled:
            return None
        evaluated = _normalize_timestamp(evaluated_at)
        zone = ZoneInfo(self.timezone_name)
        local = evaluated.astimezone(zone)
        minute = local.hour * 60 + local.minute
        start = self.quiet_hours_start_minute
        end = self.quiet_hours_end_minute
        active = start <= minute < end if start < end else minute >= start or minute < end
        if not active:
            return None

        end_date = local.date()
        if start > end and minute >= start:
            end_date += timedelta(days=1)
        local_end = datetime.combine(
            end_date,
            datetime.min.time(),
            tzinfo=zone,
        ) + timedelta(minutes=end)
        return local_end.astimezone(UTC)

    def suppresses(self, *, severity: AlertSeverity, evaluated_at: datetime) -> bool:
        if severity is AlertSeverity.CRITICAL and self.critical_bypass_quiet_hours:
            return False
        return self.quiet_hours_end(evaluated_at=evaluated_at) is not None


class AlertPublicationDecision(BaseModel):
    """Tamper-evident policy decision for one otherwise publishable evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-publication-decision-v1"] = "alert-publication-decision-v1"
    decision_id: str = Field(pattern=r"^alert-publication-decision-[a-f0-9]{16}$")
    evaluation_id: str = Field(pattern=r"^alert-evaluation-[a-f0-9]{16}$")
    policy_id: str = Field(pattern=r"^alert-publication-policy-[a-z0-9-]+$")
    policy_version: int = Field(ge=0)
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowed: bool
    suppression_reasons: tuple[AlertSuppressionReason, ...] = ()
    previous_alert_id: str | None = Field(default=None, pattern=r"^alert-[a-f0-9]{16}$")
    blocked_until: datetime | None = None
    evaluated_at: datetime
    decision_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("blocked_until", "evaluated_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @field_validator("suppression_reasons")
    @classmethod
    def validate_reasons(
        cls,
        value: tuple[AlertSuppressionReason, ...],
    ) -> tuple[AlertSuppressionReason, ...]:
        allowed = {
            AlertSuppressionReason.DUPLICATE,
            AlertSuppressionReason.COOLDOWN_ACTIVE,
            AlertSuppressionReason.QUIET_HOURS,
            AlertSuppressionReason.SNOOZED,
            AlertSuppressionReason.SOURCE_EXPIRED,
        }
        if not set(value).issubset(allowed):
            raise ValueError("publication decision contains a non-policy suppression reason")
        expected = tuple(sorted(set(value), key=lambda item: item.value))
        if value != expected:
            raise ValueError("publication suppression reasons must be unique and ordered")
        return value

    @staticmethod
    def _checksum_payload(
        *,
        evaluation_id: str,
        policy: AlertPublicationPolicy,
        allowed: bool,
        suppression_reasons: tuple[AlertSuppressionReason, ...],
        previous_alert_id: str | None,
        blocked_until: datetime | None,
        evaluated_at: datetime,
    ) -> dict[str, object]:
        return {
            "allowed": allowed,
            "blocked_until": (
                None if blocked_until is None else _normalize_timestamp(blocked_until).isoformat()
            ),
            "evaluated_at": _normalize_timestamp(evaluated_at).isoformat(),
            "evaluation_id": evaluation_id,
            "policy_checksum": policy.policy_checksum,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "previous_alert_id": previous_alert_id,
            "schema_version": "alert-publication-decision-v1",
            "suppression_reasons": [reason.value for reason in suppression_reasons],
        }

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.allowed == bool(self.suppression_reasons):
            raise ValueError("publication decision and suppression reasons are inconsistent")
        if self.allowed and (self.previous_alert_id is not None or self.blocked_until is not None):
            raise ValueError("allowed publication cannot carry blocking evidence")
        payload = {
            "allowed": self.allowed,
            "blocked_until": (
                None if self.blocked_until is None else self.blocked_until.isoformat()
            ),
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluation_id": self.evaluation_id,
            "policy_checksum": self.policy_checksum,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "previous_alert_id": self.previous_alert_id,
            "schema_version": self.schema_version,
            "suppression_reasons": [reason.value for reason in self.suppression_reasons],
        }
        expected = _checksum(payload)
        if self.decision_id != f"alert-publication-decision-{expected[:16]}":
            raise ValueError("alert publication decision ID is inconsistent")
        if self.decision_checksum != expected:
            raise ValueError("alert publication decision checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        evaluation_id: str,
        policy: AlertPublicationPolicy,
        suppression_reasons: tuple[AlertSuppressionReason, ...],
        previous_alert_id: str | None,
        blocked_until: datetime | None,
        evaluated_at: datetime,
    ) -> Self:
        reasons = tuple(sorted(set(suppression_reasons), key=lambda item: item.value))
        allowed = not reasons
        if allowed:
            previous_alert_id = None
            blocked_until = None
        payload = cls._checksum_payload(
            evaluation_id=evaluation_id,
            policy=policy,
            allowed=allowed,
            suppression_reasons=reasons,
            previous_alert_id=previous_alert_id,
            blocked_until=blocked_until,
            evaluated_at=evaluated_at,
        )
        checksum = _checksum(payload)
        return cls(
            decision_id=f"alert-publication-decision-{checksum[:16]}",
            evaluation_id=evaluation_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            policy_checksum=policy.policy_checksum,
            allowed=allowed,
            suppression_reasons=reasons,
            previous_alert_id=previous_alert_id,
            blocked_until=blocked_until,
            evaluated_at=evaluated_at,
            decision_checksum=checksum,
        )


class AlertExpiryRecord(BaseModel):
    """Append-only evidence that an immutable alert crossed its expiry boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-expiry-record-v1"] = "alert-expiry-record-v1"
    expiry_id: str = Field(pattern=r"^alert-expiry-[a-f0-9]{16}$")
    alert_id: str = Field(pattern=r"^alert-[a-f0-9]{16}$")
    expired_at: datetime
    recorded_at: datetime
    recorded_by: str = Field(min_length=1, max_length=100)
    record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("expired_at", "recorded_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("recorded_by")
    @classmethod
    def normalize_recorded_by(cls, value: str) -> str:
        return _normalize_actor(value)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.recorded_at < self.expired_at:
            raise ValueError("alert expiry cannot be recorded before expiry")
        payload = {
            "alert_id": self.alert_id,
            "expired_at": self.expired_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat(),
            "recorded_by": self.recorded_by,
            "schema_version": self.schema_version,
        }
        checksum = _checksum(payload)
        if self.expiry_id != f"alert-expiry-{checksum[:16]}":
            raise ValueError("alert expiry ID is inconsistent")
        if self.record_checksum != checksum:
            raise ValueError("alert expiry checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        alert_id: str,
        expired_at: datetime,
        recorded_at: datetime,
        recorded_by: str,
    ) -> Self:
        payload = {
            "alert_id": alert_id,
            "expired_at": _normalize_timestamp(expired_at).isoformat(),
            "recorded_at": _normalize_timestamp(recorded_at).isoformat(),
            "recorded_by": _normalize_actor(recorded_by),
            "schema_version": "alert-expiry-record-v1",
        }
        checksum = _checksum(payload)
        return cls(
            expiry_id=f"alert-expiry-{checksum[:16]}",
            alert_id=alert_id,
            expired_at=expired_at,
            recorded_at=recorded_at,
            recorded_by=recorded_by,
            record_checksum=checksum,
        )


class AlertExpirySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-expiry-summary-v1"] = "alert-expiry-summary-v1"
    evaluated_at: datetime
    expired_total: int = Field(ge=0)
    materialized_total: int = Field(ge=0)
    pending_total: int = Field(ge=0)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.expired_total != self.materialized_total + self.pending_total:
            raise ValueError("alert expiry summary counts are inconsistent")
        return self


class AlertExpirySweepResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-expiry-sweep-v1"] = "alert-expiry-sweep-v1"
    evaluated_at: datetime
    recorded_by: str = Field(min_length=1, max_length=100)
    recorded_count: int = Field(ge=0)
    expiry_ids: tuple[str, ...]
    remaining_pending: int = Field(ge=0)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("recorded_by")
    @classmethod
    def normalize_recorded_by(cls, value: str) -> str:
        return _normalize_actor(value)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.recorded_count != len(self.expiry_ids):
            raise ValueError("alert expiry sweep count is inconsistent")
        return self
