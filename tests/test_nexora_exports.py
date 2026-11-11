from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.core.config import get_settings
from trd_bot.db import (
    DatabaseBase,
    NexoraExportJobRow,
    SqlAlchemyNexoraExportStore,
    create_database_engine,
)
from trd_bot.db.models import BackgroundJobRow
from trd_bot.db.nexora_exports import render_export_artifacts
from trd_bot.db.session import get_database_session
from trd_bot.integration.nexora.exports import ExportManifest, ExportRequest
from trd_bot.main import create_app

SERVICE_TOKEN = "nexora-test-token-0123456789-abcdef"
EXPORT_PATH = "/api/v1/integration/nexora/exports"
NOW = datetime(2026, 11, 11, 8, tzinfo=UTC)


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'exports.db'}")
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
    *, idempotency_key: str = "nexora-export-idempotency-0001", token: str = SERVICE_TOKEN
) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
        "X-Correlation-ID": str(uuid4()),
    }


def payload(*, profile: str = "private") -> dict[str, Any]:
    return {
        "schema_version": "nexora-export-request-v1",
        "mode": "full",
        "formats": ["json", "jsonl", "csv", "parquet", "zip_bundle"],
        "profile": profile,
        "scope": ["market_context", "alert"],
        "filters": {"base_currency": "USDT", "portfolio_mode": "paper"},
    }


def test_export_request_rejects_duplicates_and_secret_smuggling() -> None:
    with pytest.raises(ValidationError, match="unique"):
        ExportRequest.model_validate({**payload(), "formats": ["json", "json"]})
    with pytest.raises(ValidationError, match="credentials or secrets"):
        ExportRequest.model_validate(
            {**payload(), "filters": {"nested": {"api_token": "do-not-store"}}}
        )
    with pytest.raises(ValidationError, match="credentials or secrets"):
        ExportRequest.model_validate({**payload(), "filters": {"query": "Bearer do-not-store"}})


def test_all_export_formats_are_deterministic() -> None:
    request = ExportRequest.model_validate(payload(profile="ai_safe"))
    first = render_export_artifacts(request, ())
    second = render_export_artifacts(request, ())
    assert first == second
    assert {path.rsplit(".", 1)[-1] for path, *_ in first} == {
        "json",
        "jsonl",
        "csv",
        "parquet",
        "zip",
    }


def test_api_accepts_idempotently_and_rejects_conflicting_reuse(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    request_headers = headers()
    first = client.post(EXPORT_PATH, json=payload(), headers=request_headers)
    replay = client.post(EXPORT_PATH, json=payload(), headers=request_headers)
    conflict = client.post(
        EXPORT_PATH,
        json={**payload(), "profile": "ai_safe"},
        headers=request_headers,
    )

    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json()
    assert first.json()["status"] == "accepted"
    assert first.headers["cache-control"] == "private, no-store"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NexoraExportJobRow)) == 1
        assert session.scalar(select(func.count()).select_from(BackgroundJobRow)) == 1


def test_manifest_is_unavailable_until_atomic_completion_and_checksums_match(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    response = client.post(EXPORT_PATH, json=payload(), headers=headers())
    assert response.status_code == 202
    export_id = response.json()["export_id"]

    pending = client.get(f"{EXPORT_PATH}/{export_id}/manifest", headers=headers())
    assert pending.status_code == 409
    assert pending.json()["error"] == {
        "code": "SOURCE_UNAVAILABLE",
        "message": "export manifest is not complete",
        "retryable": True,
        "details": {},
    }

    with factory() as session:
        store = SqlAlchemyNexoraExportStore(session)
        manifest = store.run(export_id, generated_at=NOW)
        session.commit()
        artifacts = store.list_artifacts(export_id)

    assert manifest.completion_status == "complete"
    assert manifest.timezone == "UTC"
    assert manifest.currency_unit_context.quantity_units_explicit is True
    assert len(manifest.files) == len(artifacts) == 5
    by_path = {artifact.path: artifact for artifact in artifacts}
    for file in manifest.files:
        artifact = by_path[file.path]
        assert file.size_bytes == len(artifact.content)
        assert file.sha256 == hashlib.sha256(artifact.content).hexdigest()
    completed = client.get(f"{EXPORT_PATH}/{export_id}", headers=headers())
    published = client.get(f"{EXPORT_PATH}/{export_id}/manifest", headers=headers())
    assert completed.status_code == published.status_code == 200
    assert completed.json()["status"] == "complete"
    assert ExportManifest.model_validate(published.json()) == manifest


def test_ai_safe_profile_redacts_sensitive_payload_fields(
    factory: sessionmaker[Session], client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trd_bot.db import nexora_exports as export_module
    from trd_bot.integration.nexora.snapshots import SnapshotRecord

    item = SnapshotRecord(
        resource_type="market_context",
        resource_id="context-1",
        resource_schema_version="trd-bot-market-context-v1",
        observed_at=NOW,
        sort_key="1",
        payload={
            "account_id": "private-account",
            "service_token": "secret-value",
            "safe_value": "preserved",
        },
    ).to_item(source_version="0.3.0")

    def collect(*args: object, **kwargs: object) -> tuple[object, ...]:
        del args, kwargs
        return (item,)

    monkeypatch.setattr(export_module, "_collect_items", collect)
    request_headers = headers(idempotency_key="nexora-export-ai-safe-0001")
    response = client.post(
        EXPORT_PATH,
        json={**payload(profile="ai_safe"), "formats": ["json"]},
        headers=request_headers,
    )
    export_id = response.json()["export_id"]
    with factory() as session:
        store = SqlAlchemyNexoraExportStore(session)
        manifest = store.run(export_id, generated_at=NOW)
        session.commit()
        artifact = store.list_artifacts(export_id)[0]
    document = json.loads(artifact.content)
    assert document[0]["payload"] == {
        "account_id": "[REDACTED]",
        "service_token": "[REDACTED]",
        "safe_value": "preserved",
    }
    assert manifest.redaction_profile == "ai-safe-v1"
    assert manifest.lineage_references == (item.source_reference,)


def test_export_boundary_requires_authentication(client: TestClient) -> None:
    response = client.post(EXPORT_PATH, json=payload(), headers=headers(token="wrong-token"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_secret_filter_is_sanitized_and_never_persisted(
    factory: sessionmaker[Session], client: TestClient
) -> None:
    secret = "github_pat_0123456789abcdefghijklmnop"
    response = client.post(
        EXPORT_PATH,
        json={**payload(), "filters": {"service_token": secret}},
        headers=headers(idempotency_key="nexora-export-secret-guard-0001"),
    )
    assert response.status_code == 422
    assert secret not in response.text
    assert "service_token" not in response.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NexoraExportJobRow)) == 0
