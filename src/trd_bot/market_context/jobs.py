import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import TradingPair
from trd_bot.jobs import BackgroundJob, BackgroundJobBuilder, BackgroundJobKind, BackgroundJobStatus
from trd_bot.market_context.contracts import MarketContextAlignmentPolicy, MarketRegimeAssessment
from trd_bot.market_context.features import market_context_feature_set_v1
from trd_bot.market_context.regimes import market_regime_policy_v1


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-context job timestamps must include timezone information")
    return value.astimezone(UTC)


class MarketContextEvaluationJobPayload(BaseModel):
    """Version-one immutable intent consumed by a market-context worker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-evaluation-job-v1"] = "market-context-evaluation-job-v1"
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    as_of: datetime
    requested_at: datetime
    alignment_policy_version: Literal["market-context-alignment-policy-v1"] = (
        "market-context-alignment-policy-v1"
    )
    feature_set_version: Literal["market-context-features-v1"] = "market-context-features-v1"
    feature_set_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    algorithm_version: Literal["market-regime-v1"] = "market-regime-v1"
    algorithm_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("market-context job source cannot be empty")
        return normalized

    @field_validator("as_of", "requested_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_canonical_intent(self) -> Self:
        policy = MarketContextAlignmentPolicy()
        duration_seconds = int(policy.anchor_timeframe.duration.total_seconds())
        if int(self.as_of.timestamp()) % duration_seconds != 0:
            raise ValueError("market-context job as-of time must be an anchor boundary")
        if self.requested_at < self.as_of:
            raise ValueError("market-context job cannot be requested before its as-of time")

        feature_set = market_context_feature_set_v1()
        regime_policy = market_regime_policy_v1()
        if self.feature_set_checksum != feature_set.definition_checksum:
            raise ValueError("market-context job feature-set checksum is not canonical")
        if self.algorithm_checksum != regime_policy.definition_checksum:
            raise ValueError("market-context job algorithm checksum is not canonical")
        return self

    @classmethod
    def build(
        cls,
        *,
        source: str,
        pair: TradingPair,
        as_of: datetime,
        requested_at: datetime,
    ) -> Self:
        feature_set = market_context_feature_set_v1()
        regime_policy = market_regime_policy_v1()
        return cls(
            source=source,
            pair=pair,
            as_of=as_of,
            requested_at=requested_at,
            feature_set_checksum=feature_set.definition_checksum,
            algorithm_checksum=regime_policy.definition_checksum,
        )


@dataclass(frozen=True)
class MarketContextEvaluationEnqueueResult:
    job: BackgroundJob
    created: bool


class MarketContextEvaluationError(RuntimeError):
    """Sanitized evaluation failure with a stable worker-facing policy."""

    def __init__(self, *, code: str, message: str, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class MarketContextInputsNotReadyError(MarketContextEvaluationError):
    def __init__(self) -> None:
        super().__init__(
            code="market_context_inputs_not_ready",
            message="Finalized market-context inputs are not ready for this boundary.",
            retryable=True,
        )


class MarketContextEvaluationCancelled(RuntimeError):
    """Internal signal used to roll back a cooperatively cancelled evaluation."""


def build_market_context_evaluation_idempotency_key(
    payload: MarketContextEvaluationJobPayload,
) -> str:
    """Hash logical intent while excluding the first request timestamp."""

    intent = payload.model_dump(mode="json", exclude={"requested_at"})
    encoded = json.dumps(
        intent,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"market-context-evaluation:{hashlib.sha256(encoded).hexdigest()}"


def build_market_context_evaluation_job(
    *,
    source: str,
    pair: TradingPair,
    as_of: datetime,
    requested_at: datetime,
    builder: BackgroundJobBuilder | None = None,
) -> BackgroundJob:
    payload = MarketContextEvaluationJobPayload.build(
        source=source,
        pair=pair,
        as_of=as_of,
        requested_at=requested_at,
    )
    return (builder or BackgroundJobBuilder()).build(
        kind=BackgroundJobKind.MARKET_CONTEXT_EVALUATION,
        payload=payload.model_dump(mode="json"),
        idempotency_key=build_market_context_evaluation_idempotency_key(payload),
        now=payload.requested_at,
    )


def validate_market_context_evaluation_enqueue(
    job: BackgroundJob,
) -> MarketContextEvaluationJobPayload:
    if job.kind is not BackgroundJobKind.MARKET_CONTEXT_EVALUATION:
        raise ValueError("market-context evaluation requires its allowlisted job kind")
    if job.status is not BackgroundJobStatus.QUEUED:
        raise ValueError("market-context evaluation job must be queued")
    if job.idempotency_key is None:
        raise ValueError("market-context evaluation job requires an idempotency key")

    payload = MarketContextEvaluationJobPayload.model_validate(job.payload)
    if job.created_at != payload.requested_at or job.run_after != payload.requested_at:
        raise ValueError("market-context job lifecycle does not match its request timestamp")
    if job.idempotency_key != build_market_context_evaluation_idempotency_key(payload):
        raise ValueError("market-context evaluation idempotency key is invalid")
    return payload


def validate_market_context_evaluation_result(
    *,
    payload: MarketContextEvaluationJobPayload,
    assessment: MarketRegimeAssessment,
) -> None:
    if (
        assessment.source != payload.source
        or assessment.pair != payload.pair
        or assessment.as_of != payload.as_of
        or assessment.feature_set_version != payload.feature_set_version
        or assessment.feature_set_checksum != payload.feature_set_checksum
        or assessment.algorithm_version != payload.algorithm_version
    ):
        raise ValueError("market-context assessment does not match its job intent")
