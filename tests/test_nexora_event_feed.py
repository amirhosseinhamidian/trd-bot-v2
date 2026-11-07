from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.core.config import get_settings
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyNexoraEventStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.session import get_database_session
from trd_bot.integration.nexora.events import (
    EventAggregateGapError,
    EventIdempotencyConflictError,
    IntegrationEventEnvelope,
    IntegrationEventPage,
)
from trd_bot.main import create_app

SERVICE_TOKEN = "nexora-test-token-0123456789-abcdef"
EVENTS_ROOT = "/api/v1/integration/nexora/events"
NOW = datetime(2026, 11, 7, 9, tzinfo=UTC)


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'events.db'}")
    DatabaseBase.metadata.create_all(engine)
    resolved = create_session_factory(engine)
    yield resolved
    engine.dispose()


@pytest.fixture
def client(
    factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    token_file = tmp_path / "nexora-service-token"
    token_file.write_text(SERVICE_TOKEN, encoding="ascii")
    token_file.chmod(0o600)
    monkeypatch.setenv("TRD_BOT_NEXORA_SERVICE_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("TRD_BOT_ENVIRONMENT", "development")
    monkeypatch.setenv("TRD_BOT_APP_VERSION", "0.3.0")
    get_settings.cache_clear()

    def session_override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_database_session] = session_override
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        yield test_client
    get_settings.cache_clear()


def headers(*, token: str = SERVICE_TOKEN) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": str(uuid4()),
    }


def append_event(
    store: SqlAlchemyNexoraEventStore,
    *,
    version: int,
) -> IntegrationEventEnvelope:
    event, _ = store.append(
        event_type="decision.evaluated.v1",
        aggregate_type="decision_evaluation",
        aggregate_id="decision-evaluation-1",
        aggregate_version=version,
        idempotency_key=f"decision-evaluation-1-v{version}",
        payload_schema_version="trd-bot-decision-evaluated-event-v1",
        occurred_at=NOW + timedelta(minutes=version),
        published_at=NOW + timedelta(minutes=version, seconds=1),
        payload={
            "decision": "approved" if version == 1 else "revalidated",
            "offline_only": True,
            "external_order_submission_allowed": False,
        },
    )
    return event


def seed_events(factory: sessionmaker[Session]) -> tuple[IntegrationEventEnvelope, ...]:
    with factory.begin() as session:
        store = SqlAlchemyNexoraEventStore(session)
        return append_event(store, version=1), append_event(store, version=2)


def test_event_journal_is_idempotent_contiguous_and_checksumming(
    factory: sessionmaker[Session],
) -> None:
    with factory.begin() as session:
        store = SqlAlchemyNexoraEventStore(session)
        first = append_event(store, version=1)
        assert append_event(store, version=1) == first
        assert first.event_checksum.startswith("sha256:")
        assert first.offline_only is True
        assert first.external_order_submission_allowed is False
        with pytest.raises(EventAggregateGapError, match="expected 2"):
            append_event(store, version=3)
        with pytest.raises(EventIdempotencyConflictError):
            store.append(
                event_type="decision.evaluated.v1",
                aggregate_type="decision_evaluation",
                aggregate_id="decision-evaluation-1",
                aggregate_version=2,
                idempotency_key="decision-evaluation-1-v1",
                payload_schema_version="trd-bot-decision-evaluated-event-v1",
                occurred_at=NOW + timedelta(minutes=2),
                published_at=NOW + timedelta(minutes=2, seconds=1),
                payload={"decision": "different"},
            )


def test_event_checksum_rejects_tampering(factory: sessionmaker[Session]) -> None:
    original = seed_events(factory)[0]
    changed = original.model_dump()
    changed["payload"] = {"decision": "tampered"}
    with pytest.raises(ValidationError, match="checksum"):
        IntegrationEventEnvelope.model_validate(changed)


def test_authenticated_feed_replays_at_least_once_and_lookup_matches(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    first_event, second_event = seed_events(factory)
    first = client.get(EVENTS_ROOT, params={"limit": 1}, headers=headers())
    assert first.status_code == 200
    assert first.headers["cache-control"] == "private, no-store"
    first_page = IntegrationEventPage.model_validate(first.json())
    assert first_page.delivery_semantics == "at_least_once"
    assert first_page.items == (first_event,)
    assert first_page.has_more is True
    continuation = client.get(
        EVENTS_ROOT, params={"cursor": first_page.next_cursor}, headers=headers()
    )
    replay = client.get(EVENTS_ROOT, params={"cursor": first_page.next_cursor}, headers=headers())
    continuation_page = IntegrationEventPage.model_validate(continuation.json())
    replay_page = IntegrationEventPage.model_validate(replay.json())
    assert continuation.status_code == replay.status_code == 200
    assert continuation_page.items == replay_page.items == (second_event,)
    assert continuation_page.has_more is replay_page.has_more is False
    lookup = client.get(f"{EVENTS_ROOT}/{second_event.event_id}", headers=headers())
    assert lookup.status_code == 200
    assert IntegrationEventEnvelope.model_validate(lookup.json()) == second_event


def test_event_feed_fails_closed_for_auth_cursor_conflict_and_lookup(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    seed_events(factory)
    denied = client.get(EVENTS_ROOT, headers=headers(token="wrong-token"))
    first = IntegrationEventPage.model_validate(
        client.get(EVENTS_ROOT, params={"limit": 1}, headers=headers()).json()
    )
    conflict = client.get(
        EVENTS_ROOT,
        params={"cursor": first.next_cursor, "limit": 2},
        headers=headers(),
    )
    unknown = client.get(EVENTS_ROOT, params={"cursor": "evc_" + "0" * 64}, headers=headers())
    malformed = client.get(f"{EVENTS_ROOT}/bad-id", headers=headers())
    missing = client.get(f"{EVENTS_ROOT}/evt_{'f' * 64}", headers=headers())
    assert denied.status_code == 401
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CURSOR_CONFLICT"
    assert unknown.status_code == 400
    assert malformed.status_code == 400
    assert missing.status_code == 404


def test_expired_event_cursor_requires_full_snapshot_resync(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    seed_events(factory)
    with factory.begin() as session:
        expired = SqlAlchemyNexoraEventStore(session, cursor_ttl=timedelta(seconds=1)).page(
            now=NOW, limit=1
        )
    response = client.get(EVENTS_ROOT, params={"cursor": expired.next_cursor}, headers=headers())
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"
    assert "full snapshot resync" in response.json()["error"]["message"]
