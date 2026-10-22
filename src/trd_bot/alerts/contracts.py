import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import TradingPair
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextProductView,
    MarketContextUnavailableReason,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("alert timestamp must include timezone information")
    return value.astimezone(UTC)


def _normalize_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("alert text cannot be empty")
    return normalized


class AlertSourceKind(StrEnum):
    """Domain event families admitted by the v1 alert contract."""

    MARKET_CONTEXT = "market_context"


class AlertSeverity(StrEnum):
    """Operator-facing importance of one alert."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertRuleState(StrEnum):
    """Whether a specific immutable rule version may publish alerts."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class AlertDeliveryChannel(StrEnum):
    """Delivery surfaces allowed in v0.3."""

    IN_APP = "in_app"


class AlertSuppressionReason(StrEnum):
    """Stable reason codes for fail-closed evaluation and later persistence."""

    RULE_DISABLED = "rule_disabled"
    SOURCE_NOT_CONSUMABLE = "source_not_consumable"
    SOURCE_EXPIRED = "source_expired"
    CONDITION_NOT_MATCHED = "condition_not_matched"
    DUPLICATE = "duplicate"
    COOLDOWN_ACTIVE = "cooldown_active"
    QUIET_HOURS = "quiet_hours"
    SNOOZED = "snoozed"


def build_alert_rule_id(*, rule_key: str) -> str:
    """Build the stable identity shared by every immutable version of a rule."""

    normalized = _normalize_text(rule_key)
    return f"alert-rule-{_checksum({'rule_key': normalized})[:16]}"


def build_alert_id(
    *,
    rule_id: str,
    rule_version: int,
    source_kind: AlertSourceKind,
    source_event_id: str,
) -> str:
    """Build one deterministic alert identity per rule version and source event."""

    identity = {
        "rule_id": rule_id,
        "rule_version": rule_version,
        "source_event_id": source_event_id,
        "source_kind": source_kind.value,
    }
    return f"alert-{_checksum(identity)[:16]}"


def build_alert_deduplication_key(
    *,
    rule_id: str,
    rule_version: int,
    source_kind: AlertSourceKind,
    source_event_id: str,
) -> str:
    """Build the exact-event idempotency key consumed by the durable alert store."""

    identity = {
        "rule_id": rule_id,
        "rule_version": rule_version,
        "source_event_id": source_event_id,
        "source_kind": source_kind.value,
    }
    return f"alert-dedupe-{_checksum(identity)}"


def build_alert_source_event_checksum(assessment: MarketRegimeAssessment) -> str:
    """Checksum the complete immutable assessment referenced by an alert source."""

    return _checksum(assessment.model_dump(mode="json"))


class MarketContextAlertSourceReference(BaseModel):
    """Tamper-evident alert input derived from one market-context product view."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-alert-source-v1"] = "market-context-alert-source-v1"
    reference_id: str = Field(pattern=r"^alert-source-[a-f0-9]{16}$")
    source_kind: Literal[AlertSourceKind.MARKET_CONTEXT] = AlertSourceKind.MARKET_CONTEXT
    source_event_id: str = Field(pattern=r"^market-regime-[a-f0-9]{16}$")
    source_event_schema_version: Literal["market-regime-assessment-v1"] = (
        "market-regime-assessment-v1"
    )
    source_event_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    event_time: datetime
    assessed_at: datetime
    expires_at: datetime
    evaluated_at: datetime
    expected_as_of: datetime
    assessment_status: MarketContextAssessmentStatus
    trend: MarketTrendRegime
    volatility: MarketVolatilityRegime
    confidence: Decimal = Field(ge=0, le=1)
    consumable: bool
    unavailable_reasons: tuple[MarketContextUnavailableReason, ...]
    reference_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("event_time", "assessed_at", "expires_at", "evaluated_at", "expected_as_of")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("unavailable_reasons")
    @classmethod
    def validate_unavailable_reasons(
        cls,
        value: tuple[MarketContextUnavailableReason, ...],
    ) -> tuple[MarketContextUnavailableReason, ...]:
        expected_order = tuple(sorted(value, key=lambda item: item.value))
        if value != expected_order:
            raise ValueError("alert source unavailable reasons must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("alert source unavailable reasons must be unique")
        return value

    @staticmethod
    def _checksum_payload(
        *,
        source_event_id: str,
        source_event_checksum: str,
        source: str,
        pair: TradingPair,
        event_time: datetime,
        assessed_at: datetime,
        expires_at: datetime,
        evaluated_at: datetime,
        expected_as_of: datetime,
        assessment_status: MarketContextAssessmentStatus,
        trend: MarketTrendRegime,
        volatility: MarketVolatilityRegime,
        confidence: Decimal,
        consumable: bool,
        unavailable_reasons: tuple[MarketContextUnavailableReason, ...],
    ) -> dict[str, object]:
        return {
            "assessed_at": _normalize_timestamp(assessed_at).isoformat(),
            "assessment_status": assessment_status.value,
            "confidence": str(confidence),
            "consumable": consumable,
            "evaluated_at": _normalize_timestamp(evaluated_at).isoformat(),
            "event_time": _normalize_timestamp(event_time).isoformat(),
            "expected_as_of": _normalize_timestamp(expected_as_of).isoformat(),
            "expires_at": _normalize_timestamp(expires_at).isoformat(),
            "pair": pair.model_dump(mode="json"),
            "source": _normalize_text(source),
            "source_event_checksum": source_event_checksum,
            "source_event_id": source_event_id,
            "source_event_schema_version": "market-regime-assessment-v1",
            "source_kind": AlertSourceKind.MARKET_CONTEXT.value,
            "trend": trend.value,
            "unavailable_reasons": [item.value for item in unavailable_reasons],
            "volatility": volatility.value,
        }

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        expected_reasons: set[MarketContextUnavailableReason] = set()
        if self.assessment_status is not MarketContextAssessmentStatus.READY:
            expected_reasons.add(MarketContextUnavailableReason.ASSESSMENT_NOT_READY)
        if self.expires_at <= self.evaluated_at:
            expected_reasons.add(MarketContextUnavailableReason.ASSESSMENT_EXPIRED)
        if self.event_time != self.expected_as_of:
            expected_reasons.add(MarketContextUnavailableReason.BOUNDARY_MISMATCH)
        ordered_reasons = tuple(sorted(expected_reasons, key=lambda item: item.value))
        if self.unavailable_reasons != ordered_reasons:
            raise ValueError("alert source consumption reasons are inconsistent")
        if self.consumable != (not ordered_reasons):
            raise ValueError("alert source consumption decision is inconsistent")

        expected_checksum = _checksum(
            self._checksum_payload(
                source_event_id=self.source_event_id,
                source_event_checksum=self.source_event_checksum,
                source=self.source,
                pair=self.pair,
                event_time=self.event_time,
                assessed_at=self.assessed_at,
                expires_at=self.expires_at,
                evaluated_at=self.evaluated_at,
                expected_as_of=self.expected_as_of,
                assessment_status=self.assessment_status,
                trend=self.trend,
                volatility=self.volatility,
                confidence=self.confidence,
                consumable=self.consumable,
                unavailable_reasons=self.unavailable_reasons,
            )
        )
        if self.reference_checksum != expected_checksum:
            raise ValueError("alert source reference checksum is inconsistent")
        if self.reference_id != f"alert-source-{expected_checksum[:16]}":
            raise ValueError("alert source reference ID is inconsistent")
        return self

    @classmethod
    def from_market_context_view(cls, view: MarketContextProductView) -> Self:
        assessment = view.assessment
        source_event_checksum = build_alert_source_event_checksum(assessment)
        payload = cls._checksum_payload(
            source_event_id=assessment.assessment_id,
            source_event_checksum=source_event_checksum,
            source=assessment.source,
            pair=assessment.pair,
            event_time=assessment.as_of,
            assessed_at=assessment.assessed_at,
            expires_at=assessment.expires_at,
            evaluated_at=view.evaluated_at,
            expected_as_of=view.expected_as_of,
            assessment_status=assessment.status,
            trend=assessment.trend,
            volatility=assessment.volatility,
            confidence=assessment.confidence,
            consumable=view.consumable,
            unavailable_reasons=view.unavailable_reasons,
        )
        checksum = _checksum(payload)
        return cls(
            reference_id=f"alert-source-{checksum[:16]}",
            source_event_id=assessment.assessment_id,
            source_event_checksum=source_event_checksum,
            source=assessment.source,
            pair=assessment.pair,
            event_time=assessment.as_of,
            assessed_at=assessment.assessed_at,
            expires_at=assessment.expires_at,
            evaluated_at=view.evaluated_at,
            expected_as_of=view.expected_as_of,
            assessment_status=assessment.status,
            trend=assessment.trend,
            volatility=assessment.volatility,
            confidence=assessment.confidence,
            consumable=view.consumable,
            unavailable_reasons=view.unavailable_reasons,
            reference_checksum=checksum,
        )


class MarketContextAlertCondition(BaseModel):
    """Typed v1 predicate over a consumable market-context assessment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-alert-condition-v1"] = (
        "market-context-alert-condition-v1"
    )
    trends: tuple[MarketTrendRegime, ...] = Field(min_length=1)
    volatilities: tuple[MarketVolatilityRegime, ...] = Field(min_length=1)
    minimum_confidence: Decimal = Field(gt=0, le=1)

    @field_validator("trends")
    @classmethod
    def validate_trends(
        cls,
        value: tuple[MarketTrendRegime, ...],
    ) -> tuple[MarketTrendRegime, ...]:
        if MarketTrendRegime.UNDETERMINED in value:
            raise ValueError("alert condition cannot target an undetermined trend")
        expected = tuple(sorted(value, key=lambda item: item.value))
        if value != expected:
            raise ValueError("alert condition trends must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("alert condition trends must be unique")
        return value

    @field_validator("volatilities")
    @classmethod
    def validate_volatilities(
        cls,
        value: tuple[MarketVolatilityRegime, ...],
    ) -> tuple[MarketVolatilityRegime, ...]:
        if MarketVolatilityRegime.UNDETERMINED in value:
            raise ValueError("alert condition cannot target undetermined volatility")
        expected = tuple(sorted(value, key=lambda item: item.value))
        if value != expected:
            raise ValueError("alert condition volatilities must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("alert condition volatilities must be unique")
        return value

    def matches(self, source: MarketContextAlertSourceReference) -> bool:
        return (
            source.consumable
            and source.trend in self.trends
            and source.volatility in self.volatilities
            and source.confidence >= self.minimum_confidence
        )


class AlertRuleDefinition(BaseModel):
    """Immutable, checksummed version of one operator-owned alert rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-rule-definition-v1"] = "alert-rule-definition-v1"
    rule_id: str = Field(pattern=r"^alert-rule-[a-f0-9]{16}$")
    rule_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    rule_version: int = Field(ge=1)
    supersedes_version: int | None = Field(default=None, ge=1)
    source_kind: Literal[AlertSourceKind.MARKET_CONTEXT] = AlertSourceKind.MARKET_CONTEXT
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    state: AlertRuleState
    severity: AlertSeverity
    condition: MarketContextAlertCondition
    delivery_channel: Literal[AlertDeliveryChannel.IN_APP] = AlertDeliveryChannel.IN_APP
    expires_after_seconds: int = Field(ge=60, le=86_400)
    deduplication_window_seconds: int = Field(ge=60, le=86_400)
    cooldown_seconds: int = Field(ge=0, le=604_800)
    created_at: datetime
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("name", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @staticmethod
    def _checksum_payload(
        *,
        rule_id: str,
        rule_key: str,
        rule_version: int,
        supersedes_version: int | None,
        name: str,
        description: str,
        state: AlertRuleState,
        severity: AlertSeverity,
        condition: MarketContextAlertCondition,
        expires_after_seconds: int,
        deduplication_window_seconds: int,
        cooldown_seconds: int,
        created_at: datetime,
    ) -> dict[str, object]:
        return {
            "condition": condition.model_dump(mode="json"),
            "cooldown_seconds": cooldown_seconds,
            "created_at": _normalize_timestamp(created_at).isoformat(),
            "deduplication_window_seconds": deduplication_window_seconds,
            "delivery_channel": AlertDeliveryChannel.IN_APP.value,
            "description": _normalize_text(description),
            "expires_after_seconds": expires_after_seconds,
            "name": _normalize_text(name),
            "rule_id": rule_id,
            "rule_key": rule_key,
            "rule_version": rule_version,
            "schema_version": "alert-rule-definition-v1",
            "severity": severity.value,
            "source_kind": AlertSourceKind.MARKET_CONTEXT.value,
            "state": state.value,
            "supersedes_version": supersedes_version,
        }

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        if self.rule_id != build_alert_rule_id(rule_key=self.rule_key):
            raise ValueError("alert rule ID is inconsistent")
        if self.rule_version == 1 and self.supersedes_version is not None:
            raise ValueError("first alert rule version cannot supersede another version")
        if self.rule_version > 1 and self.supersedes_version != self.rule_version - 1:
            raise ValueError("alert rule version must supersede its immediate predecessor")
        payload = self._checksum_payload(
            rule_id=self.rule_id,
            rule_key=self.rule_key,
            rule_version=self.rule_version,
            supersedes_version=self.supersedes_version,
            name=self.name,
            description=self.description,
            state=self.state,
            severity=self.severity,
            condition=self.condition,
            expires_after_seconds=self.expires_after_seconds,
            deduplication_window_seconds=self.deduplication_window_seconds,
            cooldown_seconds=self.cooldown_seconds,
            created_at=self.created_at,
        )
        if self.definition_checksum != _checksum(payload):
            raise ValueError("alert rule definition checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        rule_key: str,
        rule_version: int,
        name: str,
        description: str,
        state: AlertRuleState,
        severity: AlertSeverity,
        condition: MarketContextAlertCondition,
        expires_after_seconds: int,
        deduplication_window_seconds: int,
        cooldown_seconds: int,
        created_at: datetime,
    ) -> Self:
        rule_id = build_alert_rule_id(rule_key=rule_key)
        supersedes_version = rule_version - 1 if rule_version > 1 else None
        payload = cls._checksum_payload(
            rule_id=rule_id,
            rule_key=rule_key,
            rule_version=rule_version,
            supersedes_version=supersedes_version,
            name=name,
            description=description,
            state=state,
            severity=severity,
            condition=condition,
            expires_after_seconds=expires_after_seconds,
            deduplication_window_seconds=deduplication_window_seconds,
            cooldown_seconds=cooldown_seconds,
            created_at=created_at,
        )
        return cls(
            rule_id=rule_id,
            rule_key=rule_key,
            rule_version=rule_version,
            supersedes_version=supersedes_version,
            name=name,
            description=description,
            state=state,
            severity=severity,
            condition=condition,
            expires_after_seconds=expires_after_seconds,
            deduplication_window_seconds=deduplication_window_seconds,
            cooldown_seconds=cooldown_seconds,
            created_at=created_at,
            definition_checksum=_checksum(payload),
        )


class AlertRuleReference(BaseModel):
    """Exact immutable rule version carried into every generated alert."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-rule-reference-v1"] = "alert-rule-reference-v1"
    rule_id: str = Field(pattern=r"^alert-rule-[a-f0-9]{16}$")
    rule_version: int = Field(ge=1)
    state: AlertRuleState
    severity: AlertSeverity
    expires_after_seconds: int = Field(ge=60, le=86_400)
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @classmethod
    def from_definition(cls, rule: AlertRuleDefinition) -> Self:
        return cls(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            state=rule.state,
            severity=rule.severity,
            expires_after_seconds=rule.expires_after_seconds,
            definition_checksum=rule.definition_checksum,
        )


class AlertDraft(BaseModel):
    """Publishable in-app alert with exact rule and market-context lineage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-draft-v1"] = "alert-draft-v1"
    alert_id: str = Field(pattern=r"^alert-[a-f0-9]{16}$")
    deduplication_key: str = Field(pattern=r"^alert-dedupe-[a-f0-9]{64}$")
    rule: AlertRuleReference
    source: MarketContextAlertSourceReference
    delivery_channel: Literal[AlertDeliveryChannel.IN_APP] = AlertDeliveryChannel.IN_APP
    severity: AlertSeverity
    title: str = Field(min_length=1, max_length=140)
    message: str = Field(min_length=1, max_length=1000)
    created_at: datetime
    expires_at: datetime
    draft_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("title", "message")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("created_at", "expires_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @staticmethod
    def _checksum_payload(
        *,
        alert_id: str,
        deduplication_key: str,
        rule: AlertRuleReference,
        source: MarketContextAlertSourceReference,
        severity: AlertSeverity,
        title: str,
        message: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> dict[str, object]:
        return {
            "alert_id": alert_id,
            "created_at": _normalize_timestamp(created_at).isoformat(),
            "deduplication_key": deduplication_key,
            "delivery_channel": AlertDeliveryChannel.IN_APP.value,
            "expires_at": _normalize_timestamp(expires_at).isoformat(),
            "message": _normalize_text(message),
            "rule": rule.model_dump(mode="json"),
            "schema_version": "alert-draft-v1",
            "severity": severity.value,
            "source": source.model_dump(mode="json"),
            "title": _normalize_text(title),
        }

    @model_validator(mode="after")
    def validate_draft(self) -> Self:
        if self.rule.state is not AlertRuleState.ENABLED:
            raise ValueError("disabled alert rule cannot create a publishable draft")
        if not self.source.consumable or self.source.unavailable_reasons:
            raise ValueError("non-consumable alert source cannot create a publishable draft")
        if self.created_at < self.source.evaluated_at:
            raise ValueError("alert creation cannot precede source evaluation")
        if self.source.expires_at <= self.created_at:
            raise ValueError("expired alert source cannot create a publishable draft")
        expected_expiry = min(
            self.source.expires_at,
            self.created_at + timedelta(seconds=self.rule.expires_after_seconds),
        )
        if self.expires_at != expected_expiry:
            raise ValueError("alert expiry is inconsistent with rule and source expiry")
        if self.severity is not self.rule.severity:
            raise ValueError("alert severity must match its immutable rule version")

        expected_id = build_alert_id(
            rule_id=self.rule.rule_id,
            rule_version=self.rule.rule_version,
            source_kind=self.source.source_kind,
            source_event_id=self.source.source_event_id,
        )
        if self.alert_id != expected_id:
            raise ValueError("alert ID is inconsistent")
        expected_deduplication_key = build_alert_deduplication_key(
            rule_id=self.rule.rule_id,
            rule_version=self.rule.rule_version,
            source_kind=self.source.source_kind,
            source_event_id=self.source.source_event_id,
        )
        if self.deduplication_key != expected_deduplication_key:
            raise ValueError("alert deduplication key is inconsistent")
        expected_checksum = _checksum(
            self._checksum_payload(
                alert_id=self.alert_id,
                deduplication_key=self.deduplication_key,
                rule=self.rule,
                source=self.source,
                severity=self.severity,
                title=self.title,
                message=self.message,
                created_at=self.created_at,
                expires_at=self.expires_at,
            )
        )
        if self.draft_checksum != expected_checksum:
            raise ValueError("alert draft checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        rule: AlertRuleDefinition,
        source: MarketContextAlertSourceReference,
        title: str,
        message: str,
        created_at: datetime,
    ) -> Self:
        created = _normalize_timestamp(created_at)
        if rule.state is not AlertRuleState.ENABLED:
            raise ValueError(AlertSuppressionReason.RULE_DISABLED.value)
        if not source.consumable:
            raise ValueError(AlertSuppressionReason.SOURCE_NOT_CONSUMABLE.value)
        if source.expires_at <= created:
            raise ValueError(AlertSuppressionReason.SOURCE_EXPIRED.value)
        if not rule.condition.matches(source):
            raise ValueError(AlertSuppressionReason.CONDITION_NOT_MATCHED.value)

        rule_reference = AlertRuleReference.from_definition(rule)
        alert_id = build_alert_id(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            source_kind=source.source_kind,
            source_event_id=source.source_event_id,
        )
        deduplication_key = build_alert_deduplication_key(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            source_kind=source.source_kind,
            source_event_id=source.source_event_id,
        )
        expires_at = min(
            source.expires_at,
            created + timedelta(seconds=rule.expires_after_seconds),
        )
        checksum = _checksum(
            cls._checksum_payload(
                alert_id=alert_id,
                deduplication_key=deduplication_key,
                rule=rule_reference,
                source=source,
                severity=rule.severity,
                title=title,
                message=message,
                created_at=created,
                expires_at=expires_at,
            )
        )
        return cls(
            alert_id=alert_id,
            deduplication_key=deduplication_key,
            rule=rule_reference,
            source=source,
            severity=rule.severity,
            title=title,
            message=message,
            created_at=created,
            expires_at=expires_at,
            draft_checksum=checksum,
        )
