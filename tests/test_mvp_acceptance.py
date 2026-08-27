from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.test_candidate_journal import build_closed_lifecycle
from trd_bot.api.dependencies import (
    get_candidate_projection_repository,
    get_simulated_portfolio_repository,
)
from trd_bot.api.routes.candidates import router as candidates_router
from trd_bot.api.routes.portfolios import router as portfolios_router
from trd_bot.db import DatabaseBase, create_database_engine, create_session_factory
from trd_bot.db.candidate_lifecycle_persistence import (
    SqlAlchemyCandidateLifecycleRecorder,
)
from trd_bot.db.candidate_projection_repositories import (
    SqlAlchemyCandidateProjectionRepository,
)
from trd_bot.db.simulated_portfolio_repositories import (
    SqlAlchemySimulatedPortfolioRepository,
)
from trd_bot.research.position_monitoring import CandidateExitReason


def build_storage(database_path: Path) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    DatabaseBase.metadata.create_all(engine)
    return engine, create_session_factory(engine)


def build_read_client(factory: sessionmaker[Session]) -> TestClient:
    application = FastAPI()
    application.include_router(candidates_router)
    application.include_router(portfolios_router)

    def candidate_repository_override() -> Iterator[SqlAlchemyCandidateProjectionRepository]:
        with factory() as session:
            yield SqlAlchemyCandidateProjectionRepository(session)

    def portfolio_repository_override() -> Iterator[SqlAlchemySimulatedPortfolioRepository]:
        with factory() as session:
            yield SqlAlchemySimulatedPortfolioRepository(session)

    application.dependency_overrides[get_candidate_projection_repository] = (
        candidate_repository_override
    )
    application.dependency_overrides[get_simulated_portfolio_repository] = (
        portfolio_repository_override
    )

    return TestClient(application)


def test_mvp_closed_candidate_lifecycle_is_persisted_and_readable_end_to_end(
    tmp_path: Path,
) -> None:
    engine, factory = build_storage(tmp_path / "mvp-acceptance.sqlite3")
    lifecycle = build_closed_lifecycle()

    assert lifecycle.monitoring is not None
    selected_candidate_id = lifecycle.replay.selected_candidate_id
    assert selected_candidate_id is not None
    position_id = lifecycle.monitoring.position_id

    try:
        with factory() as session:
            journal = SqlAlchemyCandidateLifecycleRecorder(session).record(lifecycle)

        client = build_read_client(factory)

        candidate_response = client.get(f"/research/candidates/{selected_candidate_id}")
        assert candidate_response.status_code == 200
        candidate_payload = candidate_response.json()
        assert candidate_payload["candidate"]["candidate_id"] == selected_candidate_id
        assert candidate_payload["candidate"]["dataset_id"] == lifecycle.dataset_id
        assert candidate_payload["latest"]["selected"] is True
        assert candidate_payload["latest"]["replay_status"] == "opened"
        assert candidate_payload["latest"]["risk_decision"] == "approved"
        assert candidate_payload["latest"]["position_id"] == position_id
        assert candidate_payload["latest"]["exit_reason"] == CandidateExitReason.TARGET.value

        lineage_response = client.get(f"/research/candidates/{selected_candidate_id}/lineage")
        assert lineage_response.status_code == 200
        lineage_payload = lineage_response.json()
        assert lineage_payload["total"] == 1
        assert lineage_payload["items"][0]["journal_id"] == journal.journal_id

        portfolio_response = client.get(f"/research/portfolios/{lifecycle.portfolio.portfolio_id}")
        assert portfolio_response.status_code == 200
        portfolio_payload = portfolio_response.json()
        assert portfolio_payload["portfolio_id"] == lifecycle.portfolio.portfolio_id
        assert portfolio_payload["dataset_id"] == lifecycle.dataset_id

        positions_response = client.get(
            f"/research/portfolios/{lifecycle.portfolio.portfolio_id}/positions"
        )
        assert positions_response.status_code == 200
        positions_payload = positions_response.json()
        assert positions_payload["total"] == 1
        assert positions_payload["items"][0]["position_id"] == position_id
        assert positions_payload["items"][0]["status"] == "closed"

        timeline_response = client.get(
            f"/research/portfolios/{lifecycle.portfolio.portfolio_id}/timeline"
        )
        assert timeline_response.status_code == 200
        timeline_payload = timeline_response.json()
        assert timeline_payload["total"] >= 3
        assert any(
            item["event_type"] == "position_closed" and item["position_id"] == position_id
            for item in timeline_payload["items"]
        )
    finally:
        engine.dispose()
