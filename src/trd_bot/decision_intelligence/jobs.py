import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.decision_intelligence.contracts import (
    DecisionEvaluationIntent,
    build_decision_evaluation_idempotency_key,
)
from trd_bot.decision_intelligence.evaluation import (
    StrategyEvaluationRecord,
    strategy_context_compatibility_policy_v1,
)
from trd_bot.jobs import BackgroundJob, BackgroundJobBuilder, BackgroundJobKind, BackgroundJobStatus


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("decision evaluation job timestamp must include timezone information")
    return value.astimezone(UTC)


class DecisionEvaluationJobPayload(BaseModel):
    """Immutable worker intent for one persisted strategy evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-evaluation-job-v1"] = "decision-evaluation-job-v1"
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    intent_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    compatibility_policy_version: Literal["strategy-context-compatibility-v1"] = (
        "strategy-context-compatibility-v1"
    )
    compatibility_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    requested_at: datetime
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    payload_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "compatibility_policy_checksum": self.compatibility_policy_checksum,
            "compatibility_policy_version": self.compatibility_policy_version,
            "evaluation_id": self.evaluation_id,
            "external_order_submission_allowed": False,
            "intent_checksum": self.intent_checksum,
            "offline_only": True,
            "requested_at": self.requested_at.isoformat(),
            "schema_version": self.schema_version,
        }

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        policy = strategy_context_compatibility_policy_v1()
        if (
            self.compatibility_policy_version != policy.policy_version
            or self.compatibility_policy_checksum != policy.definition_checksum
        ):
            raise ValueError("decision evaluation job compatibility policy is not canonical")
        if self.payload_checksum != _checksum(self._checksum_payload()):
            raise ValueError("decision evaluation job payload checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        intent: DecisionEvaluationIntent,
        requested_at: datetime,
    ) -> Self:
        requested = _normalize_timestamp(requested_at)
        if requested < intent.requested_at:
            raise ValueError("decision evaluation cannot be queued before its intent")
        policy = strategy_context_compatibility_policy_v1()
        unvalidated = cls.model_construct(
            evaluation_id=intent.evaluation_id,
            intent_checksum=intent.intent_checksum,
            compatibility_policy_version=policy.policy_version,
            compatibility_policy_checksum=policy.definition_checksum,
            requested_at=requested,
            payload_checksum="0" * 64,
        )
        payload = unvalidated.model_dump()
        payload["payload_checksum"] = _checksum(unvalidated._checksum_payload())
        return cls.model_validate(payload)


@dataclass(frozen=True)
class DecisionEvaluationEnqueueResult:
    job: BackgroundJob
    created: bool


class DecisionEvaluationJobError(RuntimeError):
    """Sanitized decision-evaluation failure with a stable retry policy."""

    def __init__(self, *, code: str, message: str, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class DecisionEvaluationIntentNotFoundError(DecisionEvaluationJobError):
    def __init__(self) -> None:
        super().__init__(
            code="decision_evaluation_intent_not_found",
            message="The requested decision evaluation intent does not exist.",
            retryable=False,
        )


class DecisionEvaluationJobCancelled(RuntimeError):
    """Internal signal used to roll back a cooperatively cancelled evaluation."""


def _checksum(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_decision_evaluation_job(
    *,
    intent: DecisionEvaluationIntent,
    requested_at: datetime,
    builder: BackgroundJobBuilder | None = None,
) -> BackgroundJob:
    payload = DecisionEvaluationJobPayload.build(
        intent=intent,
        requested_at=requested_at,
    )
    return (builder or BackgroundJobBuilder()).build(
        kind=BackgroundJobKind.DECISION_EVALUATION,
        payload=payload.model_dump(mode="json"),
        idempotency_key=build_decision_evaluation_idempotency_key(intent),
        now=payload.requested_at,
    )


def validate_decision_evaluation_enqueue(
    job: BackgroundJob,
    *,
    intent: DecisionEvaluationIntent,
) -> DecisionEvaluationJobPayload:
    if job.kind is not BackgroundJobKind.DECISION_EVALUATION:
        raise ValueError("decision evaluation requires its allowlisted job kind")
    if job.status is not BackgroundJobStatus.QUEUED:
        raise ValueError("decision evaluation job must be queued")
    if job.idempotency_key is None:
        raise ValueError("decision evaluation job requires an idempotency key")

    payload = DecisionEvaluationJobPayload.model_validate(job.payload)
    validate_decision_evaluation_payload_intent(payload=payload, intent=intent)
    if job.created_at != payload.requested_at or job.run_after != payload.requested_at:
        raise ValueError("decision evaluation job lifecycle does not match its request timestamp")
    expected_key = build_decision_evaluation_idempotency_key(intent)
    if job.idempotency_key != expected_key:
        raise ValueError("decision evaluation job idempotency key is invalid")
    return payload


def validate_decision_evaluation_payload_intent(
    *,
    payload: DecisionEvaluationJobPayload,
    intent: DecisionEvaluationIntent,
) -> None:
    if (
        payload.evaluation_id != intent.evaluation_id
        or payload.intent_checksum != intent.intent_checksum
    ):
        raise ValueError("decision evaluation job does not match the persisted intent")
    if payload.requested_at < intent.requested_at:
        raise ValueError("decision evaluation job predates the persisted intent")


def validate_decision_evaluation_result(
    *,
    payload: DecisionEvaluationJobPayload,
    intent: DecisionEvaluationIntent,
    record: StrategyEvaluationRecord,
) -> None:
    if (
        record.evaluation_id != intent.evaluation_id
        or record.evaluation_id != payload.evaluation_id
        or record.compatibility_policy_version != payload.compatibility_policy_version
        or record.compatibility_policy_checksum != payload.compatibility_policy_checksum
        or record.outcome.evaluated_at != intent.requested_at
        or not record.offline_only
        or record.external_order_submission_allowed
    ):
        raise ValueError("decision evaluation result does not match its durable job intent")
