from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Final, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from trd_bot.integration.nexora.contracts import ContractModel
from trd_bot.integration.nexora.snapshots import SourceReference

DECISION_REVIEW_COMMAND_SCHEMA_VERSION: Final = "nexora-decision-review-command-v1"
COMMAND_RECEIPT_SCHEMA_VERSION: Final = "nexora-command-receipt-v1"
DECISION_EVALUATION_RESOURCE: Final = "decision_evaluation"
type DecisionReviewCommandType = Literal[
    "decision_review.accept.v1",
    "decision_review.reject.v1",
    "decision_review.defer.v1",
]
type DecisionReviewAction = Literal["accept", "reject", "defer"]
ACTION_BY_COMMAND_TYPE: Final[dict[DecisionReviewCommandType, DecisionReviewAction]] = {
    "decision_review.accept.v1": "accept",
    "decision_review.reject.v1": "reject",
    "decision_review.defer.v1": "defer",
}


def _require_utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be timezone-aware UTC")
    return value


class DecisionReviewCommand(ContractModel):
    schema_version: Literal["nexora-decision-review-command-v1"]
    command_type: DecisionReviewCommandType
    decision_id: str = Field(min_length=1, max_length=100)
    portfolio_mode: Literal["paper", "shadow"]
    reviewed_at: datetime
    reason: str = Field(min_length=1, max_length=1000)
    evidence: SourceReference

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("reason must be non-empty canonical text")
        return value

    @model_validator(mode="after")
    def validate_source_identity(self) -> DecisionReviewCommand:
        _require_utc(self.reviewed_at, field="reviewed_at")
        if self.evidence.resource_type != DECISION_EVALUATION_RESOURCE:
            raise ValueError("decision review evidence must reference a decision evaluation")
        if self.decision_id != self.evidence.resource_id:
            raise ValueError("decision_id must match the source evidence resource_id")
        if self.reviewed_at < self.evidence.observed_at:
            raise ValueError("reviewed_at cannot precede the source evidence")
        return self

    @property
    def action(self) -> DecisionReviewAction:
        return ACTION_BY_COMMAND_TYPE[self.command_type]

    @property
    def request_checksum(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class CommandReceipt(ContractModel):
    schema_version: Literal["nexora-command-receipt-v1"]
    command_id: str = Field(pattern=r"^cmd_review_[0-9a-f]{32}$")
    command_type: DecisionReviewCommandType
    status: Literal["accepted", "duplicate"]
    idempotency_key: str = Field(min_length=16, max_length=160)
    correlation_id: UUID
    accepted_at: datetime

    @field_validator("accepted_at")
    @classmethod
    def validate_accepted_at(cls, value: datetime) -> datetime:
        return _require_utc(value, field="accepted_at")


def decision_review_command_id(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"cmd_review_{digest[:32]}"
