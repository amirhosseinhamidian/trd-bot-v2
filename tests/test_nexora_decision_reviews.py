from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_nexora_decision_snapshots import seed_resources
from trd_bot.core.config import get_settings
from trd_bot.db import DatabaseBase, NexoraDecisionReviewRow, create_database_engine
from trd_bot.db.session import get_database_session
from trd_bot.integration.nexora.decision_reviews import CommandReceipt, DecisionReviewCommand
from trd_bot.integration.nexora.snapshots import SnapshotPage
from trd_bot.main import create_app

SERVICE_TOKEN = "nexora-test-token-0123456789-abcdef"
SNAPSHOT_ROOT = "/api/v1/integration/nexora/snapshots/decision_evaluation"
COMMAND_PATH = "/api/v1/integration/nexora/commands/decision-reviews"
REVIEWED_AT = datetime(2026, 11, 7, 12, tzinfo=UTC)


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'reviews.db'}")
    DatabaseBase.metadata.create_all(engine)
    resolved = sessionmaker(bind=engine, expire_on_commit=False)
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


def headers(
    *,
    idempotency_key: str = "nexora-review-decision-evaluation-1",
    token: str = SERVICE_TOKEN,
) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
        "X-Correlation-ID": str(uuid4()),
    }


def command_payload(
    client: TestClient, *, command_type: str = "decision_review.accept.v1"
) -> dict[str, Any]:
    snapshot = client.get(SNAPSHOT_ROOT, params={"limit": 1}, headers=headers())
    assert snapshot.status_code == 200
    item = SnapshotPage.model_validate(snapshot.json()).items[0]
    return {
        "schema_version": "nexora-decision-review-command-v1",
        "command_type": command_type,
        "decision_id": item.source_reference.resource_id,
        "portfolio_mode": "paper",
        "reviewed_at": REVIEWED_AT.isoformat().replace("+00:00", "Z"),
        "reason": "Owner review feedback for offline Paper research",
        "evidence": item.source_reference.model_dump(mode="json"),
    }


@pytest.mark.parametrize(
    ("command_type", "action"),
    (
        ("decision_review.accept.v1", "accept"),
        ("decision_review.reject.v1", "reject"),
        ("decision_review.defer.v1", "defer"),
    ),
)
def test_command_contract_maps_the_frozen_actions(command_type: str, action: str) -> None:
    command = DecisionReviewCommand.model_validate(
        {
            "schema_version": "nexora-decision-review-command-v1",
            "command_type": command_type,
            "decision_id": "decision-evaluation-1",
            "portfolio_mode": "shadow",
            "reviewed_at": "2026-11-07T12:05:00Z",
            "reason": "Owner feedback",
            "evidence": {
                "schema_version": "nexora-source-reference-v1",
                "source_product": "trd_bot",
                "source_version": "0.3.0",
                "resource_type": "decision_evaluation",
                "resource_id": "decision-evaluation-1",
                "resource_schema_version": "trd-bot-decision-evaluation-v1",
                "observed_at": "2026-11-07T12:00:00Z",
                "checksum": "sha256:" + "a" * 64,
            },
        }
    )
    assert command.action == action


def test_command_is_durable_and_exact_retry_returns_duplicate(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    seed_resources(factory)
    payload = command_payload(client)
    idempotency_key = "nexora-review-exact-retry-0001"
    first_headers = headers(idempotency_key=idempotency_key)
    second_headers = headers(idempotency_key=idempotency_key)
    first = client.post(COMMAND_PATH, json=payload, headers=first_headers)
    duplicate = client.post(COMMAND_PATH, json=payload, headers=second_headers)

    assert first.status_code == duplicate.status_code == 202
    assert first.headers["cache-control"] == "private, no-store"
    accepted = CommandReceipt.model_validate(first.json())
    replayed = CommandReceipt.model_validate(duplicate.json())
    assert accepted.status == "accepted"
    assert replayed.status == "duplicate"
    assert replayed.command_id == accepted.command_id
    assert replayed.accepted_at == accepted.accepted_at
    assert str(replayed.correlation_id) == second_headers["X-Correlation-ID"]
    with factory() as session:
        row = session.scalar(select(NexoraDecisionReviewRow))
        assert row is not None
        assert row.action == "accept"
        assert row.offline_only is True
        assert row.execution_authorization is False
        assert row.creates_live_order is False
        assert row.posts_portfolio_transaction is False
        assert session.scalar(select(func.count()).select_from(NexoraDecisionReviewRow)) == 1


def test_same_idempotency_key_with_different_payload_returns_409(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    seed_resources(factory)
    payload = command_payload(client)
    request_headers = headers(idempotency_key="nexora-review-conflict-0001")
    assert client.post(COMMAND_PATH, json=payload, headers=request_headers).status_code == 202
    conflicting = {**payload, "reason": "A materially different owner review"}
    response = client.post(COMMAND_PATH, json=conflicting, headers=request_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NexoraDecisionReviewRow)) == 1


@pytest.mark.parametrize("mutation", ("checksum", "portfolio_mode", "decision_id"))
def test_source_evidence_guard_rejects_mismatch_without_journal_write(
    mutation: str,
    factory: sessionmaker[Session],
    client: TestClient,
) -> None:
    seed_resources(factory)
    payload = command_payload(client)
    if mutation == "checksum":
        payload["evidence"] = {**payload["evidence"], "checksum": "sha256:" + "f" * 64}
    elif mutation == "portfolio_mode":
        payload["portfolio_mode"] = "shadow"
    else:
        payload["decision_id"] = "another-decision"
        payload["evidence"] = {**payload["evidence"], "resource_id": "another-decision"}
    response = client.post(
        COMMAND_PATH,
        json=payload,
        headers=headers(idempotency_key=f"nexora-review-source-guard-{mutation}"),
    )
    assert response.status_code == 412
    assert response.json()["error"]["code"] == "CHECKSUM_MISMATCH"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NexoraDecisionReviewRow)) == 0


def test_command_boundary_requires_authentication_and_idempotency(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    seed_resources(factory)
    payload = command_payload(client)
    denied = client.post(COMMAND_PATH, json=payload, headers=headers(token="wrong-token"))
    missing_headers = headers()
    missing_headers.pop("Idempotency-Key")
    missing = client.post(COMMAND_PATH, json=payload, headers=missing_headers)
    assert denied.status_code == 401
    assert missing.status_code == 422
