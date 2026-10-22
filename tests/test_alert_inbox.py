from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_alert_persistence import (
    AS_OF,
    alert_draft,
    alert_rule,
    ready_assessment,
    seed_assessment,
    source_reference,
)
from trd_bot.alerts import (
    AlertActionConflictError,
    AlertEvaluationRecord,
    AlertInboxStatus,
    AlertSeverity,
)
from trd_bot.api import dependencies
from trd_bot.api.routes import alerts as alert_routes
from trd_bot.db import (
    AlertActionRow,
    AlertInboxStateRow,
    DatabaseBase,
    SqlAlchemyAlertInboxRepository,
    SqlAlchemyAlertStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.main import app

EVALUATED_AT = AS_OF + timedelta(minutes=20)
CURRENT_AT = AS_OF + timedelta(minutes=25)


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'alerts.db'}")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def seed_alert(factory: sessionmaker[Session], *, version: int = 1) -> str:
    assessment = ready_assessment()
    rule = alert_rule(version=version)
    source = source_reference(assessment, evaluated_at=EVALUATED_AT)
    draft = alert_draft(rule, source)
    with factory.begin() as session:
        if version == 1:
            seed_assessment(session, assessment)
        store = SqlAlchemyAlertStore(session)
        for rule_version in range(1, version + 1):
            store.stage_rule_definition(alert_rule(version=rule_version))
        store.stage_evaluation(AlertEvaluationRecord.published(draft), draft=draft)
    return draft.alert_id


def test_published_alert_gets_active_inbox_state_and_filterable_summary(
    factory: sessionmaker[Session],
) -> None:
    alert_id = seed_alert(factory)

    with factory() as session:
        repository = SqlAlchemyAlertInboxRepository(session)
        items, total = repository.list_page(
            limit=20,
            offset=0,
            evaluated_at=CURRENT_AT,
            status=AlertInboxStatus.ACTIVE,
            severity=AlertSeverity.WARNING,
        )
        summary = repository.summary(evaluated_at=CURRENT_AT)

        assert total == 1
        assert items[0].alert.alert_id == alert_id
        assert items[0].status is AlertInboxStatus.ACTIVE
        assert items[0].can_acknowledge is True
        assert items[0].can_snooze is True
        assert summary.model_dump(exclude={"evaluated_at", "schema_version"}) == {
            "total": 1,
            "active": 1,
            "snoozed": 0,
            "acknowledged": 0,
            "expired": 0,
        }
        assert session.scalar(select(func.count()).select_from(AlertInboxStateRow)) == 1


def test_snooze_and_acknowledge_are_durable_audited_and_idempotent(
    factory: sessionmaker[Session],
) -> None:
    alert_id = seed_alert(factory)

    with factory() as session:
        repository = SqlAlchemyAlertInboxRepository(session)
        snoozed, created = repository.snooze(
            alert_id,
            acted_by="operator:alert-center",
            occurred_at=CURRENT_AT,
            duration_seconds=600,
        )
        assert created is True
        assert snoozed is not None
        assert snoozed.status is AlertInboxStatus.SNOOZED
        assert snoozed.seconds_until_unsnooze == 600

        active = repository.get(
            alert_id,
            evaluated_at=CURRENT_AT + timedelta(minutes=11),
        )
        assert active is not None
        assert active.status is AlertInboxStatus.ACTIVE

        acknowledged, created = repository.acknowledge(
            alert_id,
            acted_by="operator:alert-center",
            occurred_at=CURRENT_AT + timedelta(minutes=12),
        )
        assert created is True
        assert acknowledged is not None
        assert acknowledged.status is AlertInboxStatus.ACKNOWLEDGED
        assert acknowledged.state.snoozed_until is None

        repeated, created = repository.acknowledge(
            alert_id,
            acted_by="operator:other",
            occurred_at=CURRENT_AT + timedelta(minutes=13),
        )
        assert created is False
        assert repeated == repository.get(
            alert_id,
            evaluated_at=CURRENT_AT + timedelta(minutes=13),
        )
        actions = repository.list_actions(alert_id)
        assert [action.kind.value for action in actions] == ["snoozed", "acknowledged"]
        assert session.scalar(select(func.count()).select_from(AlertActionRow)) == 2


def test_expired_or_acknowledged_alert_rejects_invalid_actions(
    factory: sessionmaker[Session],
) -> None:
    alert_id = seed_alert(factory)

    with factory() as session:
        repository = SqlAlchemyAlertInboxRepository(session)
        expired_at = EVALUATED_AT + timedelta(minutes=31)
        with pytest.raises(AlertActionConflictError) as expired:
            repository.snooze(
                alert_id,
                acted_by="operator:alert-center",
                occurred_at=expired_at,
                duration_seconds=600,
            )
        assert expired.value.code == "alert_expired"

    second_id = seed_alert(factory, version=2)
    with factory() as session:
        repository = SqlAlchemyAlertInboxRepository(session)
        repository.acknowledge(
            second_id,
            acted_by="operator:alert-center",
            occurred_at=CURRENT_AT,
        )
        with pytest.raises(AlertActionConflictError) as acknowledged:
            repository.snooze(
                second_id,
                acted_by="operator:alert-center",
                occurred_at=CURRENT_AT + timedelta(minutes=1),
                duration_seconds=600,
            )
        assert acknowledged.value.code == "alert_acknowledged"


@pytest.fixture
def alert_api(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, str]]:
    alert_id = seed_alert(factory)
    session = factory()
    repository = SqlAlchemyAlertInboxRepository(session)
    app.dependency_overrides[dependencies.get_alert_inbox_repository] = lambda: repository
    monkeypatch.setattr(alert_routes, "_now", lambda: CURRENT_AT)
    try:
        yield TestClient(app), alert_id
    finally:
        app.dependency_overrides.pop(dependencies.get_alert_inbox_repository, None)
        session.close()


def test_alert_center_api_lists_filters_and_mutates_lifecycle(
    alert_api: tuple[TestClient, str],
) -> None:
    client, alert_id = alert_api

    catalog = client.get("/api/v1/alerts", params={"status": "active", "severity": "warning"})
    summary = client.get("/api/v1/alerts/summary")
    detail = client.get(f"/api/v1/alerts/{alert_id}")
    snoozed = client.post(
        f"/api/v1/alerts/{alert_id}/snooze",
        json={"acted_by": "operator:alert-center", "duration_seconds": 900},
    )
    acknowledged = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acted_by": "operator:alert-center"},
    )

    assert catalog.status_code == 200
    assert catalog.json()["total"] == 1
    assert summary.status_code == 200
    assert summary.json()["active"] == 1
    assert detail.status_code == 200
    assert detail.json()["status"] == "active"
    assert snoozed.status_code == 200
    assert snoozed.json()["status"] == "snoozed"
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert client.get("/api/v1/alerts/alert-0000000000000000").status_code == 404


def test_alert_center_api_sanitizes_validation_errors(
    alert_api: tuple[TestClient, str],
) -> None:
    client, alert_id = alert_api

    invalid_actor = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={"acted_by": "<script>"},
    )
    invalid_duration = client.post(
        f"/api/v1/alerts/{alert_id}/snooze",
        json={"acted_by": "operator:test", "duration_seconds": 1},
    )

    assert invalid_actor.status_code == 422
    assert invalid_duration.status_code == 422
    assert "input" not in str(invalid_actor.json())
