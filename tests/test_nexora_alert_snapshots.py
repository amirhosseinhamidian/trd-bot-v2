from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import JsonValue
from sqlalchemy.orm import Session, sessionmaker

from tests.test_alert_inbox import CURRENT_AT, seed_alert
from trd_bot.alerts import AlertSimulationMode
from trd_bot.core.config import get_settings
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyAlertInboxRepository,
    SqlAlchemyAlertOutcomeRepository,
    SqlAlchemyAlertSimulationRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.session import get_database_session
from trd_bot.integration.nexora.alert_snapshots import (
    ALERT,
    ALERT_OUTCOME,
    ALERT_SNAPSHOT_RESOURCE_TYPES,
    AlertSnapshotResourceReader,
)
from trd_bot.integration.nexora.snapshots import SnapshotPage, build_source_checksum
from trd_bot.main import create_app
from trd_bot.market_context import MarketTrendRegime

SERVICE_TOKEN = "nexora-test-token-0123456789-abcdef"
SNAPSHOT_ROOT = "/api/v1/integration/nexora/snapshots"


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'snapshots.db'}")
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


def seed_resources(factory: sessionmaker[Session]) -> tuple[str, str, str]:
    first_alert = seed_alert(factory)
    second_alert = seed_alert(factory, version=2)
    with factory() as session:
        simulation = SqlAlchemyAlertSimulationRepository(session).start(
            alert_id=first_alert,
            mode=AlertSimulationMode.PAPER,
            horizon_seconds=900,
            started_by="operator:test",
            started_at=CURRENT_AT,
        )
        assert simulation is not None
        simulation_id = simulation[0].simulation.simulation_id
        observed_at = CURRENT_AT + timedelta(minutes=16)
        outcome = SqlAlchemyAlertOutcomeRepository(session).record(
            simulation_id=simulation_id,
            reference_price=Decimal("100"),
            end_price=Decimal("101"),
            high_price=Decimal("102"),
            low_price=Decimal("99"),
            observed_trend=MarketTrendRegime.TRENDING_UP,
            observed_at=observed_at,
            recorded_at=observed_at,
            recorded_by="operator:test",
        )
        assert outcome is not None
        return first_alert, second_alert, outcome[0].outcome_id


def test_reader_exposes_only_immutable_alert_resources(
    factory: sessionmaker[Session],
) -> None:
    first_alert, _, outcome_id = seed_resources(factory)
    with factory() as session:
        reader = AlertSnapshotResourceReader(session)
        for resource_type in ALERT_SNAPSHOT_RESOURCE_TYPES:
            boundary = reader.capture_boundary(
                resource_type=resource_type,
                captured_at=CURRENT_AT + timedelta(days=1),
            )
            records = reader.list_records(
                resource_type=resource_type,
                boundary_key=boundary,
                after_sort_key=None,
                limit=10,
            )
            assert records
            assert all(record.resource_type == resource_type for record in records)
            assert all(record.payload["offline_only"] is True for record in records)
            assert all(
                record.payload["external_order_submission_allowed"] is False for record in records
            )
        alert = reader.list_records(
            resource_type=ALERT,
            boundary_key=reader.capture_boundary(
                resource_type=ALERT,
                captured_at=CURRENT_AT + timedelta(days=1),
            ),
            after_sort_key=None,
            limit=10,
        )[0]
        assert alert.resource_id == first_alert
        assert outcome_id
        forbidden = {"acknowledged_at", "acknowledged_by", "snoozed_until", "snoozed_by"}
        assert forbidden.isdisjoint(alert.payload)
        record = cast(dict[str, JsonValue], alert.payload["record"])
        assert forbidden.isdisjoint(record)


def test_alert_reader_has_deterministic_same_timestamp_paging(
    factory: sessionmaker[Session],
) -> None:
    seed_resources(factory)
    with factory() as session:
        reader = AlertSnapshotResourceReader(session)
        boundary = reader.capture_boundary(
            resource_type=ALERT,
            captured_at=CURRENT_AT + timedelta(days=1),
        )
        first = reader.list_records(
            resource_type=ALERT,
            boundary_key=boundary,
            after_sort_key=None,
            limit=1,
        )
        second = reader.list_records(
            resource_type=ALERT,
            boundary_key=boundary,
            after_sort_key=first[0].sort_key,
            limit=1,
        )
        assert len(first) == len(second) == 1
        assert first[0].sort_key < second[0].sort_key
        assert first[0].resource_id != second[0].resource_id


def test_authenticated_alert_endpoints_page_with_source_checksums(
    factory: sessionmaker[Session],
    client: TestClient,
) -> None:
    seed_resources(factory)
    first = client.get(f"{SNAPSHOT_ROOT}/{ALERT}?limit=1", headers=headers())
    assert first.status_code == 200
    assert first.headers["cache-control"] == "private, no-store"
    page = SnapshotPage.model_validate(first.json())
    assert page.has_more is True
    assert page.next_cursor is not None
    item = page.items[0]
    assert item.source_reference.checksum == build_source_checksum(
        resource_type=item.source_reference.resource_type,
        resource_id=item.source_reference.resource_id,
        resource_schema_version=item.source_reference.resource_schema_version,
        observed_at=item.source_reference.observed_at,
        payload=item.payload,
    )
    repeated = client.get(
        f"{SNAPSHOT_ROOT}/{ALERT}",
        params={"cursor": page.next_cursor},
        headers=headers(),
    )
    assert repeated.status_code == 200
    outcome = client.get(f"{SNAPSHOT_ROOT}/{ALERT_OUTCOME}", headers=headers())
    outcome_page = SnapshotPage.model_validate(outcome.json())
    assert outcome.status_code == 200
    assert outcome_page.items[0].payload["reference_price"] == "100.0000000000"


def test_alert_snapshot_authentication_and_unknown_resource_fail_closed(
    factory: sessionmaker[Session],
    client: TestClient,
) -> None:
    seed_resources(factory)
    denied = client.get(f"{SNAPSHOT_ROOT}/{ALERT}", headers=headers(token="wrong-token"))
    unavailable = client.get(f"{SNAPSHOT_ROOT}/event", headers=headers())
    assert denied.status_code == 401
    assert unavailable.status_code == 400


def test_mutable_inbox_actions_do_not_change_alert_snapshot(
    factory: sessionmaker[Session],
) -> None:
    alert_id, _, _ = seed_resources(factory)
    with factory() as session:
        reader = AlertSnapshotResourceReader(session)
        boundary = reader.capture_boundary(
            resource_type=ALERT,
            captured_at=CURRENT_AT + timedelta(days=1),
        )
        before = reader.list_records(
            resource_type=ALERT,
            boundary_key=boundary,
            after_sort_key=None,
            limit=10,
        )
        SqlAlchemyAlertInboxRepository(session).acknowledge(
            alert_id,
            acted_by="operator:test",
            occurred_at=CURRENT_AT + timedelta(minutes=1),
        )
        after = reader.list_records(
            resource_type=ALERT,
            boundary_key=boundary,
            after_sort_key=None,
            limit=10,
        )
        assert before == after
