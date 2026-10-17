import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.alerts.contracts import (
    AlertDraft,
    AlertRuleDefinition,
    AlertRuleReference,
    AlertRuleState,
    AlertSourceKind,
    AlertSuppressionReason,
    MarketContextAlertSourceReference,
    build_alert_id,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("alert evaluation timestamp must include timezone information")
    return value.astimezone(UTC)


class AlertEvaluationDisposition(StrEnum):
    """Durable outcome of evaluating one rule version against one source event."""

    PUBLISHED = "published"
    SUPPRESSED = "suppressed"


def build_alert_evaluation_id(
    *,
    rule_id: str,
    rule_version: int,
    source_kind: AlertSourceKind,
    source_event_id: str,
) -> str:
    identity = {
        "rule_id": rule_id,
        "rule_version": rule_version,
        "source_event_id": source_event_id,
        "source_kind": source_kind.value,
    }
    return f"alert-evaluation-{_checksum(identity)[:16]}"


class AlertEvaluationRecord(BaseModel):
    """Immutable publish or suppression decision with complete source lineage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-evaluation-v1"] = "alert-evaluation-v1"
    evaluation_id: str = Field(pattern=r"^alert-evaluation-[a-f0-9]{16}$")
    rule: AlertRuleReference
    source: MarketContextAlertSourceReference
    disposition: AlertEvaluationDisposition
    suppression_reasons: tuple[AlertSuppressionReason, ...] = ()
    alert_id: str | None = Field(default=None, pattern=r"^alert-[a-f0-9]{16}$")
    alert_draft_checksum: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    evaluated_at: datetime
    evaluation_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("suppression_reasons")
    @classmethod
    def validate_suppression_reasons(
        cls,
        value: tuple[AlertSuppressionReason, ...],
    ) -> tuple[AlertSuppressionReason, ...]:
        expected = tuple(sorted(value, key=lambda item: item.value))
        if value != expected:
            raise ValueError("alert suppression reasons must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("alert suppression reasons must be unique")
        return value

    @staticmethod
    def _checksum_payload(
        *,
        evaluation_id: str,
        rule: AlertRuleReference,
        source: MarketContextAlertSourceReference,
        disposition: AlertEvaluationDisposition,
        suppression_reasons: tuple[AlertSuppressionReason, ...],
        alert_id: str | None,
        alert_draft_checksum: str | None,
        evaluated_at: datetime,
    ) -> dict[str, object]:
        return {
            "alert_draft_checksum": alert_draft_checksum,
            "alert_id": alert_id,
            "disposition": disposition.value,
            "evaluated_at": _normalize_timestamp(evaluated_at).isoformat(),
            "evaluation_id": evaluation_id,
            "rule": rule.model_dump(mode="json"),
            "schema_version": "alert-evaluation-v1",
            "source": source.model_dump(mode="json"),
            "suppression_reasons": [reason.value for reason in suppression_reasons],
        }

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        expected_id = build_alert_evaluation_id(
            rule_id=self.rule.rule_id,
            rule_version=self.rule.rule_version,
            source_kind=self.source.source_kind,
            source_event_id=self.source.source_event_id,
        )
        if self.evaluation_id != expected_id:
            raise ValueError("alert evaluation ID is inconsistent")
        if self.source.evaluated_at != self.evaluated_at:
            raise ValueError("alert source and evaluation timestamps must match")

        expected_alert_id = build_alert_id(
            rule_id=self.rule.rule_id,
            rule_version=self.rule.rule_version,
            source_kind=self.source.source_kind,
            source_event_id=self.source.source_event_id,
        )
        if self.disposition is AlertEvaluationDisposition.PUBLISHED:
            if self.suppression_reasons:
                raise ValueError("published alert evaluation cannot contain suppression reasons")
            if self.alert_id != expected_alert_id or self.alert_draft_checksum is None:
                raise ValueError("published alert evaluation requires its exact alert draft")
            if self.rule.state is not AlertRuleState.ENABLED:
                raise ValueError("published alert evaluation requires an enabled rule")
            if not self.source.consumable or self.source.expires_at <= self.evaluated_at:
                raise ValueError("published alert evaluation requires a consumable source")
        else:
            if not self.suppression_reasons:
                raise ValueError("suppressed alert evaluation requires at least one reason")
            if self.alert_id is not None or self.alert_draft_checksum is not None:
                raise ValueError("suppressed alert evaluation cannot reference an alert draft")
            if (
                self.rule.state is AlertRuleState.DISABLED
                and AlertSuppressionReason.RULE_DISABLED not in self.suppression_reasons
            ):
                raise ValueError("disabled rule suppression requires rule_disabled reason")
            if (
                not self.source.consumable
                and AlertSuppressionReason.SOURCE_NOT_CONSUMABLE not in self.suppression_reasons
            ):
                raise ValueError(
                    "non-consumable source suppression requires source_not_consumable reason"
                )
            if (
                self.source.expires_at <= self.evaluated_at
                and AlertSuppressionReason.SOURCE_EXPIRED not in self.suppression_reasons
            ):
                raise ValueError("expired source suppression requires source_expired reason")

        expected_checksum = _checksum(
            self._checksum_payload(
                evaluation_id=self.evaluation_id,
                rule=self.rule,
                source=self.source,
                disposition=self.disposition,
                suppression_reasons=self.suppression_reasons,
                alert_id=self.alert_id,
                alert_draft_checksum=self.alert_draft_checksum,
                evaluated_at=self.evaluated_at,
            )
        )
        if self.evaluation_checksum != expected_checksum:
            raise ValueError("alert evaluation checksum is inconsistent")
        return self

    @classmethod
    def published(cls, draft: AlertDraft) -> Self:
        if draft.created_at != draft.source.evaluated_at:
            raise ValueError("published alert draft must be created at source evaluation time")
        rule = draft.rule
        source = draft.source
        evaluation_id = build_alert_evaluation_id(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            source_kind=source.source_kind,
            source_event_id=source.source_event_id,
        )
        payload = cls._checksum_payload(
            evaluation_id=evaluation_id,
            rule=rule,
            source=source,
            disposition=AlertEvaluationDisposition.PUBLISHED,
            suppression_reasons=(),
            alert_id=draft.alert_id,
            alert_draft_checksum=draft.draft_checksum,
            evaluated_at=draft.created_at,
        )
        return cls(
            evaluation_id=evaluation_id,
            rule=rule,
            source=source,
            disposition=AlertEvaluationDisposition.PUBLISHED,
            alert_id=draft.alert_id,
            alert_draft_checksum=draft.draft_checksum,
            evaluated_at=draft.created_at,
            evaluation_checksum=_checksum(payload),
        )

    @classmethod
    def suppressed(
        cls,
        *,
        rule: AlertRuleDefinition,
        source: MarketContextAlertSourceReference,
        reasons: tuple[AlertSuppressionReason, ...],
    ) -> Self:
        ordered = tuple(sorted(reasons, key=lambda item: item.value))
        rule_reference = AlertRuleReference.from_definition(rule)
        evaluation_id = build_alert_evaluation_id(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            source_kind=source.source_kind,
            source_event_id=source.source_event_id,
        )
        payload = cls._checksum_payload(
            evaluation_id=evaluation_id,
            rule=rule_reference,
            source=source,
            disposition=AlertEvaluationDisposition.SUPPRESSED,
            suppression_reasons=ordered,
            alert_id=None,
            alert_draft_checksum=None,
            evaluated_at=source.evaluated_at,
        )
        return cls(
            evaluation_id=evaluation_id,
            rule=rule_reference,
            source=source,
            disposition=AlertEvaluationDisposition.SUPPRESSED,
            suppression_reasons=ordered,
            evaluated_at=source.evaluated_at,
            evaluation_checksum=_checksum(payload),
        )
