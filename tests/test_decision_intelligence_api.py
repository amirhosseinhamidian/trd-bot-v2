from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.test_decision_risk_gate import seed_accepted_ranking
from trd_bot.api.dependencies import get_decision_intelligence_store
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyDecisionIntelligenceStore,
    SqlAlchemyDecisionPortfolioIntelligence,
    SqlAlchemyDecisionRiskGate,
    create_database_engine,
    create_session_factory,
)
from trd_bot.main import create_app


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'decision-api.db'}")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


@pytest.fixture
def decision_api(factory: sessionmaker[Session]) -> Iterator[TestClient]:
    evaluation_id = seed_accepted_ranking(factory)
    with factory.begin() as session:
        SqlAlchemyDecisionRiskGate(session).evaluate(evaluation_id)
        SqlAlchemyDecisionPortfolioIntelligence(session).evaluate(evaluation_id)

    application = create_app()

    def override_store() -> Iterator[SqlAlchemyDecisionIntelligenceStore]:
        with factory() as session:
            yield SqlAlchemyDecisionIntelligenceStore(session)

    application.dependency_overrides[get_decision_intelligence_store] = override_store
    with TestClient(application) as client:
        yield client


def test_list_exposes_small_offline_summary(decision_api: TestClient) -> None:
    response = decision_api.get(
        "/api/v1/decision-intelligence/evaluations",
        params={"limit": 20, "offset": 0},
    )

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 1
    assert page["count"] == 1
    summary = page["items"][0]
    assert summary["latest_stage"] == "portfolio_simulation"
    assert summary["completed_stage_count"] == 4
    assert summary["signal_count"] > 0
    assert summary["top_candidate_id"].startswith("decision-candidate-")
    assert summary["risk_decision"] == "approved"
    assert summary["portfolio_recommendation"] == "accept"
    assert summary["offline_only"] is True
    assert summary["external_order_submission_allowed"] is False


def test_latest_filters_exact_persisted_lineage(decision_api: TestClient) -> None:
    latest = decision_api.get("/api/v1/decision-intelligence/evaluations/latest")
    assert latest.status_code == 200
    detail = latest.json()
    signal_id = detail["strategy_evaluation"]["signals"][0]["signal_id"]
    candidate_id = detail["candidate_ranking"]["entries"][0]["candidate"]["candidate_id"]
    strategy = detail["intent"]["strategy"]

    for params in (
        {
            "strategy_name": strategy["strategy_name"],
            "strategy_version": strategy["strategy_version"],
        },
        {"signal_id": signal_id},
        {"candidate_id": candidate_id},
        {"stage": "risk_gate"},
        {"mode": detail["intent"]["mode"]},
    ):
        response = decision_api.get(
            "/api/v1/decision-intelligence/evaluations/latest",
            params=params,
        )
        assert response.status_code == 200
        assert response.json()["summary"]["evaluation_id"] == detail["summary"]["evaluation_id"]


def test_detail_keeps_all_stage_evidence_together(decision_api: TestClient) -> None:
    latest = decision_api.get("/api/v1/decision-intelligence/evaluations/latest").json()
    evaluation_id = latest["summary"]["evaluation_id"]

    response = decision_api.get(f"/api/v1/decision-intelligence/evaluations/{evaluation_id}")

    assert response.status_code == 200
    detail = response.json()
    assert [item["stage"] for item in detail["outcomes"]] == [
        "strategy_evaluation",
        "candidate_ranking",
        "risk_gate",
        "portfolio_simulation",
    ]
    assert detail["intent"]["evaluation_id"] == evaluation_id
    assert detail["strategy_evaluation"]["evaluation_id"] == evaluation_id
    assert detail["candidate_ranking"]["evaluation_id"] == evaluation_id
    assert detail["risk_gate"]["evaluation_id"] == evaluation_id
    assert detail["portfolio_intelligence"]["evaluation_id"] == evaluation_id


def test_read_api_rejects_invalid_or_missing_scope(decision_api: TestClient) -> None:
    invalid = decision_api.get(
        "/api/v1/decision-intelligence/evaluations/latest",
        params={"strategy_version": "1.0.0"},
    )
    missing = decision_api.get(
        "/api/v1/decision-intelligence/evaluations/decision-evaluation-0000000000000000"
    )
    mutation = decision_api.post("/api/v1/decision-intelligence/evaluations")

    assert invalid.status_code == 422
    assert missing.status_code == 404
    assert mutation.status_code == 405
