import pytest
from fastapi.testclient import TestClient

from trd_bot.core.config import get_settings
from trd_bot.main import app

client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/api/v1/health")
    settings = get_settings()

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == settings.app_name
    assert data["version"] == settings.app_version
    assert data["environment"] == settings.environment
    assert "timestamp" in data


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)
def test_cors_allows_configured_frontend_origins(origin: str) -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200

    assert response.headers["access-control-allow-origin"] == origin

    assert "GET" in response.headers["access-control-allow-methods"]


def test_cors_allows_frontend_post_content_type_without_credentials() -> None:
    response = client.options(
        "/api/v1/research/datasets",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers


def test_cors_rejects_unknown_origin_preflight() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://unknown.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_does_not_allow_unknown_origin() -> None:
    response = client.get(
        "/api/v1/health",
        headers={
            "Origin": ("https://unknown.example.test"),
        },
    )

    assert response.status_code == 200

    assert "access-control-allow-origin" not in response.headers
