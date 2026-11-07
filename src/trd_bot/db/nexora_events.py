from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import JsonValue
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trd_bot.db.models import NexoraEventCursorRow, NexoraIntegrationEventRow
from trd_bot.integration.nexora.events import (
    DEFAULT_EVENT_CURSOR_TTL,
    DEFAULT_EVENT_PAGE_LIMIT,
    MAXIMUM_EVENT_PAGE_LIMIT,
    EventAggregateGapError,
    EventCursorConflictError,
    EventCursorExpiredError,
    EventCursorNotFoundError,
    EventIdempotencyConflictError,
    IntegrationEventEnvelope,
    IntegrationEventPage,
    build_event_envelope,
)
from trd_bot.integration.nexora.snapshots import normalize_database_timestamp


def _cursor_token() -> str:
    return f"evc_{uuid4().hex}{uuid4().hex}"


def _envelope_from_row(row: NexoraIntegrationEventRow) -> IntegrationEventEnvelope:
    return IntegrationEventEnvelope.model_validate_json(row.payload_json)


class SqlAlchemyNexoraEventStore:
    """Append and replay versioned integration events with at-least-once delivery."""

    def __init__(
        self, session: Session, *, cursor_ttl: timedelta = DEFAULT_EVENT_CURSOR_TTL
    ) -> None:
        if cursor_ttl <= timedelta(0):
            raise ValueError("event cursor TTL must be positive")
        self._session = session
        self._cursor_ttl = cursor_ttl

    def append(
        self,
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
    ) -> tuple[IntegrationEventEnvelope, bool]:
        candidate = build_event_envelope(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            idempotency_key=idempotency_key,
            payload_schema_version=payload_schema_version,
            occurred_at=occurred_at,
            published_at=published_at,
            payload=payload,
        )
        existing = self._session.scalar(
            select(NexoraIntegrationEventRow).where(
                NexoraIntegrationEventRow.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            envelope = _envelope_from_row(existing)
            if envelope != candidate:
                raise EventIdempotencyConflictError(
                    "event idempotency key already belongs to different evidence"
                )
            return envelope, False
        latest_version = self._session.scalar(
            select(func.max(NexoraIntegrationEventRow.aggregate_version)).where(
                NexoraIntegrationEventRow.aggregate_type == aggregate_type,
                NexoraIntegrationEventRow.aggregate_id == aggregate_id,
            )
        )
        expected_version = 1 if latest_version is None else latest_version + 1
        if aggregate_version != expected_version:
            raise EventAggregateGapError(
                f"aggregate version must be contiguous; expected {expected_version}"
            )
        self._session.add(
            NexoraIntegrationEventRow(
                event_id=candidate.event_id,
                schema_version=candidate.schema_version,
                event_type=candidate.event_type,
                aggregate_type=candidate.aggregate_type,
                aggregate_id=candidate.aggregate_id,
                aggregate_version=candidate.aggregate_version,
                idempotency_key=candidate.idempotency_key,
                payload_schema_version=candidate.payload_schema_version,
                occurred_at=candidate.occurred_at,
                published_at=candidate.published_at,
                event_checksum=candidate.event_checksum,
                offline_only=True,
                external_order_submission_allowed=False,
                payload_json=candidate.model_dump_json(),
            )
        )
        self._session.flush()
        return candidate, True

    def get(self, event_id: str) -> IntegrationEventEnvelope | None:
        row = self._session.scalar(
            select(NexoraIntegrationEventRow).where(NexoraIntegrationEventRow.event_id == event_id)
        )
        return None if row is None else _envelope_from_row(row)

    def page(
        self, *, now: datetime, cursor: str | None = None, limit: int | None = None
    ) -> IntegrationEventPage:
        normalized_now = normalize_database_timestamp(now)
        if cursor is None:
            resolved_limit = DEFAULT_EVENT_PAGE_LIMIT if limit is None else limit
            after_sequence = 0
        else:
            checkpoint = self._session.get(NexoraEventCursorRow, cursor)
            if checkpoint is None:
                raise EventCursorNotFoundError("event cursor is unknown")
            if normalize_database_timestamp(checkpoint.expires_at) <= normalized_now:
                raise EventCursorExpiredError("event cursor has expired")
            if limit is not None and limit != checkpoint.page_limit:
                raise EventCursorConflictError("event cursor is bound to another page limit")
            resolved_limit = checkpoint.page_limit
            after_sequence = checkpoint.after_sequence
        if resolved_limit < 1 or resolved_limit > MAXIMUM_EVENT_PAGE_LIMIT:
            raise EventCursorConflictError("event page limit is outside the supported range")
        rows: Sequence[NexoraIntegrationEventRow] = self._session.scalars(
            select(NexoraIntegrationEventRow)
            .where(NexoraIntegrationEventRow.global_sequence > after_sequence)
            .order_by(NexoraIntegrationEventRow.global_sequence.asc())
            .limit(resolved_limit + 1)
        ).all()
        visible = rows[:resolved_limit]
        next_sequence = visible[-1].global_sequence if visible else after_sequence
        next_cursor = NexoraEventCursorRow(
            cursor=_cursor_token(),
            after_sequence=next_sequence,
            page_limit=resolved_limit,
            created_at=normalized_now,
            expires_at=normalized_now + self._cursor_ttl,
        )
        self._session.add(next_cursor)
        self._session.flush()
        return IntegrationEventPage(
            schema_version="trd-integration-event-page-v1",
            delivery_semantics="at_least_once",
            items=tuple(_envelope_from_row(row) for row in visible),
            next_cursor=next_cursor.cursor,
            has_more=len(rows) > resolved_limit,
        )
