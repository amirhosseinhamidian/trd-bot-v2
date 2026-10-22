from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_candidate_journal import build_closed_lifecycle
from tests.test_candidate_journal_repository import build_repository
from tests.test_paper_portfolio import create_portfolio
from tests.test_portfolio_analytics import golden_portfolio
from tests.test_simulated_portfolio_api import InMemorySimulatedPortfolioRepository
from trd_bot.api.dependencies import (
    get_candidate_journal_repository,
    get_simulated_portfolio_repository,
)
from trd_bot.api.routes.portfolios import router
from trd_bot.db import SqlAlchemyCandidateJournalRepository
from trd_bot.research.candidate_journal import CandidateJournalBuilder, CandidateJournalEntry


class JournalRepository:
    def list_by_portfolio(self, portfolio_id: str) -> tuple[CandidateJournalEntry, ...]:
        return ()


def test_endpoint_is_read_only_and_serializes_fee_aware_decimal_metrics() -> None:
    portfolio = golden_portfolio()
    repository = InMemorySimulatedPortfolioRepository()
    repository.save(portfolio)
    before = portfolio.model_dump_json()
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_simulated_portfolio_repository] = lambda: repository
    application.dependency_overrides[get_candidate_journal_repository] = JournalRepository
    with TestClient(application) as client:
        path = f"/research/portfolios/{portfolio.portfolio_id}/analytics"
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["analytics_version"] == "portfolio-analytics-v1"
        assert Decimal(data["ending_equity"]) == Decimal("1009.48")
        assert data["profit_factor"] is None
        assert data["equity_points"][-1]["equity"] == data["ending_equity"]
        assert client.post(path).status_code == 405
        assert client.get("/research/portfolios/missing/analytics").status_code == 404
        empty = create_portfolio()
        repository.save(empty)
        empty_response = client.get(f"/research/portfolios/{empty.portfolio_id}/analytics")
        assert empty_response.status_code == 200
        assert empty_response.json()["win_rate"] is None
        assert empty_response.json()["profit_factor_status"] == "no_closed_trades"
    assert repository.get(portfolio.portfolio_id) == portfolio
    assert portfolio.model_dump_json() == before


def test_repository_selects_only_requested_portfolio_journals() -> None:
    engine, factory = build_repository()
    journal = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    try:
        with factory() as session:
            repository = SqlAlchemyCandidateJournalRepository(session)
            repository.save(journal)
            assert repository.list_by_portfolio(journal.portfolio_id) == (journal,)
            assert repository.list_by_portfolio("portfolio-0000000000000000") == ()
            assert repository.count() == 1
    finally:
        engine.dispose()
