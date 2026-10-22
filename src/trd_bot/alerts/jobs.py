import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from trd_bot.alerts.contracts import (
    AlertDraft,
    AlertRuleDefinition,
    AlertRuleReference,
    AlertRuleState,
    AlertSuppressionReason,
    MarketContextAlertSourceReference,
)
from trd_bot.alerts.evaluations import AlertEvaluationRecord
from trd_bot.jobs import BackgroundJob, BackgroundJobBuilder, BackgroundJobKind, BackgroundJobStatus
from trd_bot.market_context import MarketContextProductView, MarketRegimeAssessment


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("alert evaluation job timestamp must include timezone information")
    return value.astimezone(UTC)


class AlertEvaluationJobPayload(BaseModel):
    """Version-one immutable intent for one rule/source evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-evaluation-job-v1"] = "alert-evaluation-job-v1"
    rule: AlertRuleReference
    source: MarketContextAlertSourceReference
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_intent(self) -> Self:
        if self.source.evaluated_at != self.requested_at:
            raise ValueError("alert evaluation source must be captured at request time")
        return self

    @classmethod
    def build(
        cls,
        *,
        rule: AlertRuleDefinition,
        assessment: MarketRegimeAssessment,
        requested_at: datetime,
    ) -> Self:
        requested = _normalize_timestamp(requested_at)
        source = MarketContextAlertSourceReference.from_market_context_view(
            MarketContextProductView.from_assessment(
                assessment,
                evaluated_at=requested,
            )
        )
        return cls(
            rule=AlertRuleReference.from_definition(rule),
            source=source,
            requested_at=requested,
        )


@dataclass(frozen=True)
class AlertEvaluationEnqueueResult:
    job: BackgroundJob
    created: bool


@dataclass(frozen=True)
class AlertEvaluationOutcome:
    evaluation: AlertEvaluationRecord
    draft: AlertDraft | None


class AlertEvaluationJobError(RuntimeError):
    """Sanitized alert-evaluation failure with an explicit retry policy."""

    def __init__(self, *, code: str, message: str, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class AlertRuleVersionNotFoundError(AlertEvaluationJobError):
    def __init__(self) -> None:
        super().__init__(
            code="alert_rule_version_not_found",
            message="The requested alert rule version no longer exists.",
            retryable=False,
        )


class AlertSourceAssessmentNotFoundError(AlertEvaluationJobError):
    def __init__(self) -> None:
        super().__init__(
            code="alert_source_assessment_not_found",
            message="The requested market-context assessment does not exist.",
            retryable=False,
        )


class AlertEvaluationJobCancelled(RuntimeError):
    """Internal signal used to roll back a cooperatively cancelled evaluation."""


def build_alert_evaluation_idempotency_key(payload: AlertEvaluationJobPayload) -> str:
    """Hash the logical rule/source intent while preserving the first request time."""

    intent = {
        "rule_id": payload.rule.rule_id,
        "rule_version": payload.rule.rule_version,
        "source_event_id": payload.source.source_event_id,
        "source_kind": payload.source.source_kind.value,
    }
    encoded = json.dumps(
        intent,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"alert-evaluation:{hashlib.sha256(encoded).hexdigest()}"


def build_alert_evaluation_job(
    *,
    rule: AlertRuleDefinition,
    assessment: MarketRegimeAssessment,
    requested_at: datetime,
    builder: BackgroundJobBuilder | None = None,
) -> BackgroundJob:
    payload = AlertEvaluationJobPayload.build(
        rule=rule,
        assessment=assessment,
        requested_at=requested_at,
    )
    return (builder or BackgroundJobBuilder()).build(
        kind=BackgroundJobKind.ALERT_EVALUATION,
        payload=payload.model_dump(mode="json"),
        idempotency_key=build_alert_evaluation_idempotency_key(payload),
        now=payload.requested_at,
    )


def validate_alert_evaluation_enqueue(job: BackgroundJob) -> AlertEvaluationJobPayload:
    if job.kind is not BackgroundJobKind.ALERT_EVALUATION:
        raise ValueError("alert evaluation requires its allowlisted job kind")
    if job.status is not BackgroundJobStatus.QUEUED:
        raise ValueError("alert evaluation job must be queued")
    if job.idempotency_key is None:
        raise ValueError("alert evaluation job requires an idempotency key")

    payload = AlertEvaluationJobPayload.model_validate(job.payload)
    if job.created_at != payload.requested_at or job.run_after != payload.requested_at:
        raise ValueError("alert evaluation lifecycle does not match its request timestamp")
    if job.idempotency_key != build_alert_evaluation_idempotency_key(payload):
        raise ValueError("alert evaluation idempotency key is invalid")
    return payload


def evaluate_alert(
    *,
    rule: AlertRuleDefinition,
    source: MarketContextAlertSourceReference,
    publication_suppression_reasons: tuple[AlertSuppressionReason, ...] = (),
) -> AlertEvaluationOutcome:
    reasons: set[AlertSuppressionReason] = set()
    if rule.state is AlertRuleState.DISABLED:
        reasons.add(AlertSuppressionReason.RULE_DISABLED)
    if not source.consumable:
        reasons.add(AlertSuppressionReason.SOURCE_NOT_CONSUMABLE)
    if source.expires_at <= source.evaluated_at:
        reasons.add(AlertSuppressionReason.SOURCE_EXPIRED)

    if reasons:
        evaluation = AlertEvaluationRecord.suppressed(
            rule=rule,
            source=source,
            reasons=tuple(sorted(reasons, key=lambda item: item.value)),
        )
        return AlertEvaluationOutcome(evaluation=evaluation, draft=None)

    if not rule.condition.matches(source):
        evaluation = AlertEvaluationRecord.suppressed(
            rule=rule,
            source=source,
            reasons=(AlertSuppressionReason.CONDITION_NOT_MATCHED,),
        )
        return AlertEvaluationOutcome(evaluation=evaluation, draft=None)

    if publication_suppression_reasons:
        evaluation = AlertEvaluationRecord.suppressed(
            rule=rule,
            source=source,
            reasons=publication_suppression_reasons,
        )
        return AlertEvaluationOutcome(evaluation=evaluation, draft=None)

    draft = AlertDraft.build(
        rule=rule,
        source=source,
        title=rule.name,
        message=rule.description,
        created_at=source.evaluated_at,
    )
    return AlertEvaluationOutcome(
        evaluation=AlertEvaluationRecord.published(draft),
        draft=draft,
    )


def validate_alert_evaluation_result(
    *,
    payload: AlertEvaluationJobPayload,
    outcome: AlertEvaluationOutcome,
) -> None:
    evaluation = outcome.evaluation
    if evaluation.rule != payload.rule or evaluation.source != payload.source:
        raise ValueError("alert evaluation does not match its job intent")
    if outcome.draft is None:
        if evaluation.alert_id is not None:
            raise ValueError("suppressed alert evaluation unexpectedly references an alert")
    elif AlertEvaluationRecord.published(outcome.draft) != evaluation:
        raise ValueError("published alert evaluation does not match its draft")
