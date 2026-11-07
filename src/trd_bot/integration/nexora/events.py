from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Final, Literal

from pydantic import Field, JsonValue, model_validator

from trd_bot.integration.nexora.contracts import ContractModel

EVENT_ENVELOPE_SCHEMA_VERSION: Final = "trd-integration-event-envelope-v1"
EVENT_PAGE_SCHEMA_VERSION: Final = "trd-integration-event-page-v1"
DEFAULT_EVENT_PAGE_LIMIT: Final = 100
MAXIMUM_EVENT_PAGE_LIMIT: Final = 500
DEFAULT_EVENT_CURSOR_TTL: Final = timedelta(hours=1)


class EventFeedError(ValueError):
    """Base error for invalid or inconsistent event feed operations."""


class EventCursorNotFoundError(EventFeedError):
    pass


class EventCursorExpiredError(EventFeedError):
    pass


class EventCursorConflictError(EventFeedError):
    pass


class EventIdempotencyConflictError(EventFeedError):
    pass


class EventAggregateGapError(EventFeedError):
    pass


def _require_utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise EventFeedError(f"{field} must be timezone-aware UTC")
    return value


def canonical_event_json(value: dict[str, JsonValue]) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    )


def event_checksum(value: dict[str, JsonValue]) -> str:
    return f"sha256:{hashlib.sha256(canonical_event_json(value).encode()).hexdigest()}"


def build_event_id(*, event_type: str, idempotency_key: str) -> str:
    identity = f"{event_type}\x00{idempotency_key}".encode()
    return f"evt_{hashlib.sha256(identity).hexdigest()}"


class IntegrationEventEnvelope(ContractModel):
    schema_version: Literal["trd-integration-event-envelope-v1"]
    event_id: str = Field(pattern=r"^evt_[0-9a-f]{64}$")
    event_type: str = Field(min_length=1, max_length=120)
    aggregate_type: str = Field(min_length=1, max_length=80)
    aggregate_id: str = Field(min_length=1, max_length=160)
    aggregate_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=200)
    payload_schema_version: str = Field(min_length=1, max_length=120)
    occurred_at: datetime
    published_at: datetime
    payload: dict[str, JsonValue]
    offline_only: Literal[True]
    external_order_submission_allowed: Literal[False]
    event_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_envelope(self) -> IntegrationEventEnvelope:
        _require_utc(self.occurred_at, field="occurred_at")
        _require_utc(self.published_at, field="published_at")
        if self.published_at < self.occurred_at:
            raise ValueError("published_at cannot precede occurred_at")
        expected_id = build_event_id(
            event_type=self.event_type, idempotency_key=self.idempotency_key
        )
        if self.event_id != expected_id:
            raise ValueError("event_id does not match its deterministic identity")
        evidence = self.model_dump(mode="json", exclude={"event_checksum"})
        if self.event_checksum != event_checksum(evidence):
            raise ValueError("event checksum does not match the envelope")
        return self


class IntegrationEventPage(ContractModel):
    schema_version: Literal["trd-integration-event-page-v1"]
    delivery_semantics: Literal["at_least_once"]
    items: tuple[IntegrationEventEnvelope, ...]
    next_cursor: str = Field(pattern=r"^evc_[0-9a-f]{64}$")
    has_more: bool


def build_event_envelope(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int,
    idempotency_key: str,
    payload_schema_version: str,
    occurred_at: datetime,
    published_at: datetime,
    payload: dict[str, JsonValue],
) -> IntegrationEventEnvelope:
    _require_utc(occurred_at, field="occurred_at")
    _require_utc(published_at, field="published_at")
    event_id = build_event_id(event_type=event_type, idempotency_key=idempotency_key)
    evidence: dict[str, JsonValue] = {
        "aggregate_id": aggregate_id,
        "aggregate_type": aggregate_type,
        "aggregate_version": aggregate_version,
        "event_id": event_id,
        "event_type": event_type,
        "external_order_submission_allowed": False,
        "idempotency_key": idempotency_key,
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
        "offline_only": True,
        "payload": payload,
        "payload_schema_version": payload_schema_version,
        "published_at": published_at.isoformat().replace("+00:00", "Z"),
        "schema_version": EVENT_ENVELOPE_SCHEMA_VERSION,
    }
    return IntegrationEventEnvelope.model_validate(
        {**evidence, "event_checksum": event_checksum(evidence)}
    )
