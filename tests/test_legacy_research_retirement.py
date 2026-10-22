from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.legacy_research import (
    EXPERIMENT_EXECUTION_ENDPOINT,
    LEGACY_SYNCHRONOUS_RESEARCH_ROUTES,
    WALK_FORWARD_EXECUTION_ENDPOINT,
    enforce_legacy_research_route_retirement,
)
from trd_bot.main import app

client = TestClient(app)
FRONTEND_SOURCE = Path(__file__).resolve().parents[1] / "frontend" / "src"


@pytest.fixture(autouse=True)
def use_production_retirement_gate() -> Iterator[None]:
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.pop(enforce_legacy_research_route_retirement, None)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


@pytest.mark.parametrize(
    ("path", "replacement_endpoint"),
    [
        (
            "/api/v1/research/ema-crossover",
            EXPERIMENT_EXECUTION_ENDPOINT,
        ),
        (
            "/api/v1/research/experiments/ema-crossover",
            EXPERIMENT_EXECUTION_ENDPOINT,
        ),
        (
            "/api/v1/research/experiments/ema-crossover/from-dataset",
            EXPERIMENT_EXECUTION_ENDPOINT,
        ),
        (
            "/api/v1/research/walk-forward/ema-crossover",
            WALK_FORWARD_EXECUTION_ENDPOINT,
        ),
        (
            "/api/v1/research/walk-forward/runs/ema-crossover",
            WALK_FORWARD_EXECUTION_ENDPOINT,
        ),
        (
            "/api/v1/research/walk-forward/runs/ema-crossover/from-dataset",
            WALK_FORWARD_EXECUTION_ENDPOINT,
        ),
    ],
)
def test_legacy_synchronous_route_returns_migration_tombstone(
    path: str,
    replacement_endpoint: str,
) -> None:
    response = client.post(path, json={})

    assert response.status_code == 410
    assert response.json()["detail"] == {
        "code": "legacy_synchronous_research_route_retired",
        "message": (
            "Synchronous research execution is retired. Submit a durable background job "
            "and poll its execution resource instead."
        ),
        "replacement_endpoint": replacement_endpoint,
        "migration_steps": list(LEGACY_SYNCHRONOUS_RESEARCH_ROUTES[path].migration_steps),
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["deprecation"] == "@1791676800"
    assert response.headers["sunset"] == "Sun, 11 Oct 2026 00:00:00 GMT"
    assert response.headers["link"] == (f'<{replacement_endpoint}>; rel="successor-version"')


def test_openapi_marks_every_synchronous_route_deprecated_with_gone_response() -> None:
    paths = app.openapi()["paths"]

    for path in LEGACY_SYNCHRONOUS_RESEARCH_ROUTES:
        operation = paths[path]["post"]
        assert operation["deprecated"] is True
        assert "410" in operation["responses"]


def test_frontend_does_not_call_retired_synchronous_routes() -> None:
    source_files = (
        *FRONTEND_SOURCE.rglob("*.ts"),
        *FRONTEND_SOURCE.rglob("*.tsx"),
    )
    violations = {
        str(path.relative_to(FRONTEND_SOURCE)): retired_path
        for path in source_files
        for retired_path in LEGACY_SYNCHRONOUS_RESEARCH_ROUTES
        if retired_path in path.read_text(encoding="utf-8")
    }

    assert violations == {}
