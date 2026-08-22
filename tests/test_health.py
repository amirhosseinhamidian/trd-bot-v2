from fastapi.testclient import TestClient

from trd_bot.main import app

client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "TRD BOT v2"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"
    assert "timestamp" in data


def test_cors_allows_configured_frontend_origin() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    assert "GET" in response.headers["access-control-allow-methods"]


def test_cors_does_not_allow_unknown_origin() -> None:
    response = client.get(
        "/api/v1/health",
        headers={
            "Origin": ("https://unknown.example.test"),
        },
    )

    assert response.status_code == 200

    assert "access-control-allow-origin" not in response.headers
