from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_alert_inbox import CURRENT_AT, seed_alert
from trd_bot.alerts import AlertOutcomeRecord, AlertSimulationMode
from trd_bot.api import dependencies
from trd_bot.api.routes import alerts as alert_routes
from trd_bot.db import (
    AlertOutcomeConflictError,
    AlertOutcomeRow,
    DatabaseBase,
    SqlAlchemyAlertOutcomeRepository,
    SqlAlchemyAlertSimulationRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.main import app
from trd_bot.market_context import MarketTrendRegime


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'outcomes.db'}")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def start_simulation(
    factory: sessionmaker[Session],
    *,
    horizon_seconds: int = 900,
    alert_id: str | None = None,
) -> str:
    resolved_alert_id = alert_id or seed_alert(factory)
    with factory() as session:
        result = SqlAlchemyAlertSimulationRepository(session).start(
            alert_id=resolved_alert_id,
            mode=AlertSimulationMode.PAPER,
            horizon_seconds=horizon_seconds,
            started_by="operator:test",
            started_at=CURRENT_AT,
        )
        assert result is not None
        return result[0].simulation.simulation_id


def test_outcome_journal_calculates_performance_drift_and_lineage(
    factory: sessionmaker[Session],
) -> None:
    simulation_id = start_simulation(factory)
    observed_at = CURRENT_AT + timedelta(minutes=16)
    with factory() as session:
        result = SqlAlchemyAlertOutcomeRepository(session).record(
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

        assert result is not None
        outcome, created = result
        assert created is True
        assert outcome.classification.value == "confirmed"
        assert outcome.raw_return == Decimal("0.01000000")
        assert outcome.directional_return == Decimal("0.01000000")
        assert outcome.max_favorable_excursion == Decimal("0.02000000")
        assert outcome.max_adverse_excursion == Decimal("-0.01000000")
        assert outcome.false_positive is False
        assert outcome.drifted is False
        assert outcome.offline_only is True
        assert outcome.external_order_submission_allowed is False
        assert outcome.simulation_checksum

        with pytest.raises(ValidationError):
            AlertOutcomeRecord.model_validate(
                {**outcome.model_dump(), "external_order_submission_allowed": True}
            )


def test_outcome_is_idempotent_and_summary_counts_false_positive_and_pending(
    factory: sessionmaker[Session],
) -> None:
    alert_id = seed_alert(factory)
    simulation_id = start_simulation(factory, alert_id=alert_id)
    pending_id = start_simulation(factory, horizon_seconds=3600, alert_id=alert_id)
    assert pending_id != simulation_id
    observed_at = CURRENT_AT + timedelta(hours=2)
    with factory() as session:
        repository = SqlAlchemyAlertOutcomeRepository(session)
        first = repository.record(
            simulation_id=simulation_id,
            reference_price=Decimal("100"),
            end_price=Decimal("99"),
            high_price=Decimal("100"),
            low_price=Decimal("98"),
            observed_trend=MarketTrendRegime.TRENDING_DOWN,
            observed_at=observed_at,
            recorded_at=observed_at,
            recorded_by="operator:first",
        )
        repeated = repository.record(
            simulation_id=simulation_id,
            reference_price=Decimal("1"),
            end_price=Decimal("1"),
            high_price=Decimal("1"),
            low_price=Decimal("1"),
            observed_trend=MarketTrendRegime.RANGING,
            observed_at=observed_at,
            recorded_at=observed_at,
            recorded_by="operator:retry",
        )
        summary = repository.summary(evaluated_at=observed_at)

        assert first is not None and repeated is not None
        assert first[1] is True
        assert repeated[1] is False
        assert repeated[0] == first[0]
        assert first[0].classification.value == "false_positive"
        assert first[0].drifted is True
        assert summary.completed == 1
        assert summary.awaiting_outcome == 1
        assert summary.false_positive == 1
        assert summary.false_positive_rate == Decimal("1")
        assert summary.drift_rate == Decimal("1")
        assert session.scalar(select(func.count()).select_from(AlertOutcomeRow)) == 1


def test_outcome_fails_closed_before_horizon_and_on_invalid_prices(
    factory: sessionmaker[Session],
) -> None:
    simulation_id = start_simulation(factory)
    with factory() as session:
        repository = SqlAlchemyAlertOutcomeRepository(session)
        with pytest.raises(AlertOutcomeConflictError) as conflict:
            repository.record(
                simulation_id=simulation_id,
                reference_price=Decimal("100"),
                end_price=Decimal("101"),
                high_price=Decimal("102"),
                low_price=Decimal("99"),
                observed_trend=MarketTrendRegime.TRENDING_UP,
                observed_at=CURRENT_AT + timedelta(minutes=14),
                recorded_at=CURRENT_AT + timedelta(minutes=14),
                recorded_by="operator:test",
            )
        assert conflict.value.code == "simulation_horizon_incomplete"

        with pytest.raises(ValueError, match="high price"):
            repository.record(
                simulation_id=simulation_id,
                reference_price=Decimal("100"),
                end_price=Decimal("101"),
                high_price=Decimal("99"),
                low_price=Decimal("98"),
                observed_trend=MarketTrendRegime.TRENDING_UP,
                observed_at=CURRENT_AT + timedelta(minutes=16),
                recorded_at=CURRENT_AT + timedelta(minutes=16),
                recorded_by="operator:test",
            )


@pytest.fixture
def outcome_api(
    factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, str]]:
    simulation_id = start_simulation(factory)
    session = factory()
    repository = SqlAlchemyAlertOutcomeRepository(session)
    app.dependency_overrides[dependencies.get_alert_outcome_repository] = lambda: repository
    monkeypatch.setattr(alert_routes, "_now", lambda: CURRENT_AT + timedelta(minutes=16))
    try:
        yield TestClient(app), simulation_id
    finally:
        app.dependency_overrides.pop(dependencies.get_alert_outcome_repository, None)
        session.close()


def test_alert_outcome_api_records_lists_summarizes_and_gets(
    outcome_api: tuple[TestClient, str],
) -> None:
    client, simulation_id = outcome_api
    payload = {
        "acted_by": "operator:alert-center",
        "reference_price": "100",
        "end_price": "101",
        "high_price": "102",
        "low_price": "99",
        "observed_trend": "trending_up",
    }
    recorded = client.post(f"/api/v1/alerts/simulations/{simulation_id}/outcome", json=payload)
    repeated = client.post(f"/api/v1/alerts/simulations/{simulation_id}/outcome", json=payload)
    catalog = client.get("/api/v1/alerts/outcomes", params={"simulation_id": simulation_id})
    summary = client.get("/api/v1/alerts/outcomes/summary")
    outcome_id = recorded.json()["outcome"]["outcome_id"]
    detail = client.get(f"/api/v1/alerts/outcomes/{outcome_id}")

    assert recorded.status_code == 200
    assert recorded.json()["created"] is True
    assert recorded.json()["outcome"]["classification"] == "confirmed"
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False
    assert catalog.status_code == 200 and catalog.json()["total"] == 1
    assert summary.status_code == 200 and summary.json()["completed"] == 1
    assert detail.status_code == 200
    assert detail.json()["external_order_submission_allowed"] is False
    assert client.get("/api/v1/alerts/outcomes/alert-outcome-0000000000000000").status_code == 404


def test_alert_outcome_api_rejects_invalid_or_early_input(
    outcome_api: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, simulation_id = outcome_api
    invalid = client.post(
        f"/api/v1/alerts/simulations/{simulation_id}/outcome",
        json={
            "acted_by": "<script>",
            "reference_price": "100",
            "end_price": "101",
            "high_price": "99",
            "low_price": "98",
            "observed_trend": "trending_up",
        },
    )
    monkeypatch.setattr(alert_routes, "_now", lambda: CURRENT_AT + timedelta(minutes=14))
    early = client.post(
        f"/api/v1/alerts/simulations/{simulation_id}/outcome",
        json={
            "acted_by": "operator:test",
            "reference_price": "100",
            "end_price": "101",
            "high_price": "102",
            "low_price": "99",
            "observed_trend": "trending_up",
        },
    )

    assert invalid.status_code == 422
    assert early.status_code == 409
    assert early.json()["detail"]["code"] == "simulation_horizon_incomplete"
