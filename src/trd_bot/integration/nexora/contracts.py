from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTRACT_VERSION: Final = "nexora-trd-integration-v1"
CAPABILITIES_SCHEMA_VERSION: Final = "nexora-integration-capabilities-v1"
EVENT_ENVELOPE_VERSION: Final = "trd-integration-event-envelope-v1"
EXPORT_MANIFEST_VERSION: Final = "nexora-export-manifest-v1"
SOURCE_REFERENCE_VERSION: Final = "nexora-source-reference-v1"
COMMANDS: Final = (
    "decision_review.accept.v1",
    "decision_review.reject.v1",
    "decision_review.defer.v1",
)
type IntegrationErrorCode = Literal[
    "INVALID_REQUEST",
    "UNAUTHORIZED",
    "FORBIDDEN",
    "SOURCE_UNAVAILABLE",
    "CURSOR_EXPIRED",
    "CURSOR_CONFLICT",
    "IDEMPOTENCY_CONFLICT",
    "CHECKSUM_MISMATCH",
]


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CapabilitiesResponse(ContractModel):
    schema_version: Literal["nexora-integration-capabilities-v1"]
    provider: Literal["trd_bot"]
    provider_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    contract_versions: tuple[str, ...]
    event_envelopes: tuple[str, ...]
    export_manifests: tuple[str, ...]
    source_references: tuple[str, ...]
    commands: tuple[str, ...]
    generated_at: datetime

    _generated_at_is_utc = field_validator("generated_at")(_require_utc)


class IntegrationErrorDetail(ContractModel):
    code: IntegrationErrorCode
    message: str = Field(min_length=1, max_length=500)
    retryable: bool
    details: dict[str, Any]


class IntegrationErrorEnvelope(ContractModel):
    schema_version: Literal["nexora-integration-error-v1"]
    correlation_id: UUID
    occurred_at: datetime
    error: IntegrationErrorDetail

    _occurred_at_is_utc = field_validator("occurred_at")(_require_utc)
