from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trd_bot.core.config import get_settings
from trd_bot.main import create_app

SERVICE_TOKEN = "nexora-test-token-0123456789-abcdef"
CAPABILITIES_PATH = "/api/v1/integration/nexora/capabilities"


@pytest.fixture
def service_token_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    token_file = tmp_path / "nexora-service-token"
    token_file.write_text(SERVICE_TOKEN, encoding="ascii")
    token_file.chmod(0o600)
    monkeypatch.setenv("TRD_BOT_NEXORA_SERVICE_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("TRD_BOT_ENVIRONMENT", "development")
    monkeypatch.setenv("TRD_BOT_APP_VERSION", "0.3.0")
    get_settings.cache_clear()
    yield token_file
    get_settings.cache_clear()


def request_headers(*, token: str = SERVICE_TOKEN) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": str(uuid4()),
    }


def test_capabilities_are_authenticated_versioned_and_exact(
    service_token_file: Path,
) -> None:
    del service_token_file
    headers = request_headers()
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.get(CAPABILITIES_PATH, headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].split(";", 1)[0] == "application/json"
    assert response.headers["x-contract-version"] == "nexora-trd-integration-v1"
    assert response.headers["x-correlation-id"] == headers["X-Correlation-ID"]
    assert response.headers["x-trd-bot-version"] == "0.3.0"
    assert response.headers["cache-control"] == "private, max-age=300"
    payload = response.json()
    assert payload == {
        "schema_version": "nexora-integration-capabilities-v1",
        "provider": "trd_bot",
        "provider_version": "0.3.0",
        "contract_versions": ["nexora-trd-integration-v1"],
        "event_envelopes": ["trd-integration-event-envelope-v1"],
        "export_manifests": ["nexora-export-manifest-v1"],
        "source_references": ["nexora-source-reference-v1"],
        "commands": [
            "decision_review.accept.v1",
            "decision_review.reject.v1",
            "decision_review.defer.v1",
        ],
        "generated_at": payload["generated_at"],
    }
    assert payload["generated_at"].endswith("Z")


@pytest.mark.parametrize("authorization", [None, "Basic ignored", "Bearer ", "Bearer wrong-token"])
def test_missing_or_invalid_service_token_returns_sanitized_401(
    service_token_file: Path,
    authorization: str | None,
) -> None:
    headers = request_headers()
    if authorization is None:
        headers.pop("Authorization")
    else:
        headers["Authorization"] = authorization

    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.get(CAPABILITIES_PATH, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["x-correlation-id"] == headers["X-Correlation-ID"]
    assert response.json()["error"] == {
        "code": "UNAUTHORIZED",
        "message": "service authentication failed",
        "retryable": False,
        "details": {},
    }
    serialized = response.text
    assert SERVICE_TOKEN not in serialized
    assert str(service_token_file) not in serialized
    assert "wrong-token" not in serialized


@pytest.mark.parametrize("correlation_id", [None, "not-a-uuid", "A" * 37])
def test_missing_or_invalid_correlation_id_is_rejected(
    service_token_file: Path,
    correlation_id: str | None,
) -> None:
    del service_token_file
    headers = request_headers()
    if correlation_id is None:
        headers.pop("X-Correlation-ID")
    else:
        headers["X-Correlation-ID"] = correlation_id

    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.get(CAPABILITIES_PATH, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert response.headers["x-correlation-id"] != correlation_id


def test_request_must_accept_json(service_token_file: Path) -> None:
    del service_token_file
    headers = request_headers()
    headers["Accept"] = "text/plain"
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.get(CAPABILITIES_PATH, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_http_is_limited_to_loopback_in_development(service_token_file: Path) -> None:
    del service_token_file
    with TestClient(create_app(), base_url="http://integration.internal") as client:
        response = client.get(CAPABILITIES_PATH, headers=request_headers())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_production_requires_https(
    service_token_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del service_token_file
    monkeypatch.setenv("TRD_BOT_ENVIRONMENT", "production")
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app, base_url="http://127.0.0.1") as client:
        insecure = client.get(CAPABILITIES_PATH, headers=request_headers())
    with TestClient(app, base_url="https://trd-bot.internal") as client:
        secure = client.get(CAPABILITIES_PATH, headers=request_headers())

    assert insecure.status_code == 403
    assert secure.status_code == 200


@pytest.mark.parametrize("unsafe_kind", ["relative", "short", "permissions", "symlink"])
def test_unsafe_service_token_configuration_fails_closed(
    service_token_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_kind: str,
) -> None:
    configured_path = service_token_file
    if unsafe_kind == "relative":
        configured_path = Path("relative-service-token")
    elif unsafe_kind == "short":
        service_token_file.write_text("too-short", encoding="ascii")
    elif unsafe_kind == "permissions":
        service_token_file.chmod(0o644)
    else:
        link = service_token_file.parent / "service-token-link"
        link.symlink_to(service_token_file)
        configured_path = link

    monkeypatch.setenv("TRD_BOT_NEXORA_SERVICE_TOKEN_FILE", str(configured_path))
    get_settings.cache_clear()
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.get(CAPABILITIES_PATH, headers=request_headers())

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "SOURCE_UNAVAILABLE",
        "message": "service authentication is unavailable",
        "retryable": False,
        "details": {},
    }
    assert SERVICE_TOKEN not in response.text
    assert str(configured_path) not in response.text


def test_service_token_is_not_browser_cors_allowed(service_token_file: Path) -> None:
    del service_token_file
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.options(
            CAPABILITIES_PATH,
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization,X-Correlation-ID",
            },
        )

    assert response.status_code == 400
    assert "authorization" not in response.headers.get("access-control-allow-headers", "").lower()


def test_v031_stage_does_not_claim_provider_compatibility(service_token_file: Path) -> None:
    del service_token_file
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        openapi = client.get("/openapi.json").json()

    integration_paths = {
        path for path in openapi["paths"] if path.startswith("/api/v1/integration/nexora")
    }
    assert integration_paths == {
        CAPABILITIES_PATH,
        "/api/v1/integration/nexora/commands/decision-reviews",
        "/api/v1/integration/nexora/events",
        "/api/v1/integration/nexora/events/{event_id}",
        "/api/v1/integration/nexora/snapshots/{resource_type}",
    }
    assert openapi["info"]["version"] == "0.3.0"
