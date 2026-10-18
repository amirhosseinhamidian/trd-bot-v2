from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_alert_inbox import CURRENT_AT, EVALUATED_AT, seed_alert
from trd_bot.alerts import AlertSimulationMode, AlertSimulationRecord, AlertSimulationStatus
from trd_bot.api import dependencies
from trd_bot.api.routes import alerts as alert_routes
from trd_bot.db import (
    AlertSimulationConflictError,
    AlertSimulationRow,
    DatabaseBase,
    SqlAlchemyAlertSimulationRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.main import app


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'simulations.db'}")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def test_offline_simulation_is_immutable_idempotent_and_order_proof(
    factory: sessionmaker[Session],
) -> None:
    alert_id = seed_alert(factory)

    with factory() as session:
        repository = SqlAlchemyAlertSimulationRepository(session)
        first = repository.start(
            alert_id=alert_id,
            mode=AlertSimulationMode.PAPER,
            horizon_seconds=3600,
            started_by="operator:first",
            started_at=CURRENT_AT,
        )
        repeated = repository.start(
            alert_id=alert_id,
            mode=AlertSimulationMode.PAPER,
            horizon_seconds=3600,
            started_by="operator:retry",
            started_at=CURRENT_AT + timedelta(seconds=1),
        )

        assert first is not None and repeated is not None
        first_view, first_created = first
        repeated_view, repeated_created = repeated
        assert first_created is True
        assert repeated_created is False
        assert repeated_view.simulation == first_view.simulation
        assert first_view.status is AlertSimulationStatus.OBSERVING
        assert first_view.simulation.offline_only is True
        assert first_view.simulation.external_order_submission_allowed is False
        assert first_view.simulation.expected_trend.value == "trending_up"
        assert session.scalar(select(func.count()).select_from(AlertSimulationRow)) == 1

        with pytest.raises(ValidationError):
            AlertSimulationRecord.model_validate(
                {
                    **first_view.simulation.model_dump(),
                    "external_order_submission_allowed": True,
                }
            )


def test_summary_and_status_are_time_derived_without_mutating_record(
    factory: sessionmaker[Session],
) -> None:
    alert_id = seed_alert(factory)
    with factory() as session:
        repository = SqlAlchemyAlertSimulationRepository(session)
        paper = repository.start(
            alert_id=alert_id,
            mode=AlertSimulationMode.PAPER,
            horizon_seconds=900,
            started_by="operator:test",
            started_at=CURRENT_AT,
        )
        shadow = repository.start(
            alert_id=alert_id,
            mode=AlertSimulationMode.SHADOW,
            horizon_seconds=3600,
            started_by="operator:test",
            started_at=CURRENT_AT,
        )
        assert paper is not None and shadow is not None

        evaluated_at = CURRENT_AT + timedelta(minutes=20)
        items, total = repository.list_page(
            limit=10,
            offset=0,
            evaluated_at=evaluated_at,
        )
        summary = repository.summary(evaluated_at=evaluated_at)

        assert total == 2
        assert {item.status for item in items} == {
            AlertSimulationStatus.OBSERVING,
            AlertSimulationStatus.AWAITING_OUTCOME,
        }
        assert summary.model_dump(exclude={"schema_version", "evaluated_at"}) == {
            "total": 2,
            "paper": 1,
            "shadow": 1,
            "observing": 1,
            "awaiting_outcome": 1,
        }


def test_expired_alert_fails_closed_before_simulation(
    factory: sessionmaker[Session],
) -> None:
    alert_id = seed_alert(factory)
    with factory() as session:
        repository = SqlAlchemyAlertSimulationRepository(session)
        with pytest.raises(AlertSimulationConflictError) as conflict:
            repository.start(
                alert_id=alert_id,
                mode=AlertSimulationMode.SHADOW,
                horizon_seconds=3600,
                started_by="operator:test",
                started_at=EVALUATED_AT + timedelta(minutes=31),
            )
        assert conflict.value.code == "alert_expired"
        assert session.scalar(select(func.count()).select_from(AlertSimulationRow)) == 0


@pytest.fixture
def simulation_api(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, str]]:
    alert_id = seed_alert(factory)
    session = factory()
    repository = SqlAlchemyAlertSimulationRepository(session)
    app.dependency_overrides[dependencies.get_alert_simulation_repository] = lambda: repository
    monkeypatch.setattr(alert_routes, "_now", lambda: CURRENT_AT)
    try:
        yield TestClient(app), alert_id
    finally:
        app.dependency_overrides.pop(dependencies.get_alert_simulation_repository, None)
        session.close()


def test_alert_simulation_api_starts_lists_and_summarizes_offline_observation(
    simulation_api: tuple[TestClient, str],
) -> None:
    client, alert_id = simulation_api
    started = client.post(
        f"/api/v1/alerts/{alert_id}/simulations",
        json={
            "acted_by": "operator:alert-center",
            "mode": "shadow",
            "horizon_seconds": 14_400,
        },
    )
    repeated = client.post(
        f"/api/v1/alerts/{alert_id}/simulations",
        json={
            "acted_by": "operator:retry",
            "mode": "shadow",
            "horizon_seconds": 14_400,
        },
    )
    catalog = client.get("/api/v1/alerts/simulations", params={"alert_id": alert_id})
    summary = client.get("/api/v1/alerts/simulations/summary")
    simulation_id = started.json()["view"]["simulation"]["simulation_id"]
    detail = client.get(f"/api/v1/alerts/simulations/{simulation_id}")

    assert started.status_code == 200
    assert started.json()["created"] is True
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 1
    assert summary.status_code == 200
    assert summary.json()["shadow"] == 1
    assert detail.status_code == 200
    assert detail.json()["simulation"]["external_order_submission_allowed"] is False
    assert (
        client.get("/api/v1/alerts/simulations/alert-simulation-0000000000000000").status_code
        == 404
    )


def test_alert_simulation_api_sanitizes_and_rejects_invalid_requests(
    simulation_api: tuple[TestClient, str],
) -> None:
    client, alert_id = simulation_api
    invalid_actor = client.post(
        f"/api/v1/alerts/{alert_id}/simulations",
        json={"acted_by": "<script>", "mode": "paper", "horizon_seconds": 3600},
    )
    invalid_horizon = client.post(
        f"/api/v1/alerts/{alert_id}/simulations",
        json={"acted_by": "operator:test", "mode": "paper", "horizon_seconds": 1},
    )
    missing = client.post(
        "/api/v1/alerts/alert-0000000000000000/simulations",
        json={"acted_by": "operator:test", "mode": "paper", "horizon_seconds": 3600},
    )

    assert invalid_actor.status_code == 422
    assert invalid_horizon.status_code == 422
    assert missing.status_code == 404
    assert "input" not in str(invalid_actor.json())
