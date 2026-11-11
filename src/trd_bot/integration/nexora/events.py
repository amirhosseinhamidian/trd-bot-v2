from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final, Literal
from uuid import UUID, uuid5

from pydantic import Field, JsonValue, model_validator

from trd_bot.integration.nexora.contracts import ContractModel
from trd_bot.integration.nexora.snapshots import SourceReference, build_source_checksum

EVENT_ENVELOPE_SCHEMA_VERSION: Final = "trd-integration-event-envelope-v1"
EVENT_PAGE_SCHEMA_VERSION: Final = "trd-integration-event-page-v1"
DEFAULT_EVENT_PAGE_LIMIT: Final = 100
MAXIMUM_EVENT_PAGE_LIMIT: Final = 500
DEFAULT_EVENT_CURSOR_TTL: Final = timedelta(hours=1)
EVENT_CORRELATION_NAMESPACE: Final = UUID("8b25c26b-d915-4b5d-b828-2d746ce9803b")


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


class ProviderEventType(StrEnum):
    MARKET_CONTEXT_ASSESSED = "market_context.assessed.v1"
    DECISION_EVALUATION_COMPLETED = "decision.evaluation.completed.v1"
    CANDIDATE_STATE_CHANGED = "candidate.state.changed.v1"
    RISK_GATE_COMPLETED = "risk_gate.completed.v1"
    PORTFOLIO_INTELLIGENCE_COMPLETED = "portfolio_intelligence.completed.v1"
    ALERT_PUBLISHED = "alert.published.v1"
    ALERT_LIFECYCLE_CHANGED = "alert.lifecycle.changed.v1"
    SIMULATION_POSITION_OPENED = "simulation.position.opened.v1"
    SIMULATION_POSITION_UPDATED = "simulation.position.updated.v1"
    SIMULATION_POSITION_CLOSED = "simulation.position.closed.v1"
    OUTCOME_RECORDED = "outcome.recorded.v1"


class ProviderAggregateReference(ContractModel):
    type: str = Field(min_length=1, max_length=80)
    id: str = Field(min_length=1, max_length=160)
    version: int = Field(ge=1)


class ProviderEventEnvelope(ContractModel):
    """Frozen wire envelope consumed by the Nexora v0.1 adapter."""

    schema_version: Literal["trd-integration-event-envelope-v1"]
    event_id: str = Field(pattern=r"^evt_[A-Za-z0-9_-]{16,64}$")
    event_type: ProviderEventType
    occurred_at: datetime
    emitted_at: datetime
    source: SourceReference
    aggregate: ProviderAggregateReference
    correlation_id: UUID
    causation_id: UUID | None
    idempotency_key: str = Field(min_length=16, max_length=160)
    payload_schema: str = Field(min_length=1, max_length=160)
    payload: dict[str, JsonValue]
    payload_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_provider_envelope(self) -> ProviderEventEnvelope:
        _require_utc(self.occurred_at, field="occurred_at")
        _require_utc(self.emitted_at, field="emitted_at")
        if self.emitted_at < self.occurred_at:
            raise ValueError("emitted_at cannot precede occurred_at")
        if self.payload_checksum != event_checksum(self.payload):
            raise ValueError("payload checksum mismatch")
        return self


class ProviderEventPage(ContractModel):
    schema_version: Literal["trd-integration-event-page-v1"]
    events: tuple[ProviderEventEnvelope, ...]
    next_cursor: str | None
    has_more: bool

    @model_validator(mode="after")
    def validate_provider_page(self) -> ProviderEventPage:
        if self.has_more and self.next_cursor is None:
            raise ValueError("a continuing event page requires next_cursor")
        return self


def to_provider_event(
    event: IntegrationEventEnvelope, *, source_version: str
) -> ProviderEventEnvelope:
    """Project durable internal evidence onto the immutable cross-repository wire contract."""

    source = SourceReference(
        schema_version="nexora-source-reference-v1",
        source_product="trd_bot",
        source_version=source_version,
        resource_type=event.aggregate_type,
        resource_id=event.aggregate_id,
        resource_schema_version=event.payload_schema_version,
        observed_at=event.occurred_at,
        checksum=build_source_checksum(
            resource_type=event.aggregate_type,
            resource_id=event.aggregate_id,
            resource_schema_version=event.payload_schema_version,
            observed_at=event.occurred_at,
            payload=event.payload,
        ),
    )
    return ProviderEventEnvelope(
        schema_version=EVENT_ENVELOPE_SCHEMA_VERSION,
        event_id=event.event_id,
        event_type=ProviderEventType(event.event_type),
        occurred_at=event.occurred_at,
        emitted_at=event.published_at,
        source=source,
        aggregate=ProviderAggregateReference(
            type=event.aggregate_type,
            id=event.aggregate_id,
            version=event.aggregate_version,
        ),
        correlation_id=uuid5(EVENT_CORRELATION_NAMESPACE, event.event_id),
        causation_id=None,
        idempotency_key=event.idempotency_key,
        payload_schema=event.payload_schema_version,
        payload=event.payload,
        payload_checksum=event_checksum(event.payload),
    )


def to_provider_event_page(page: IntegrationEventPage, *, source_version: str) -> ProviderEventPage:
    return ProviderEventPage(
        schema_version=EVENT_PAGE_SCHEMA_VERSION,
        events=tuple(to_provider_event(item, source_version=source_version) for item in page.items),
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


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
