from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.test_candidate_journal import build_closed_lifecycle
from trd_bot.api.dependencies import (
    get_candidate_journal_repository,
    get_simulated_portfolio_repository,
)
from trd_bot.main import app
from trd_bot.paper import PortfolioTimelineEvent, SimulatedPortfolio, SimulatedPosition
from trd_bot.research.candidate_journal import CandidateJournalBuilder, CandidateJournalEntry


class StubPortfolioRepository:
    def __init__(self, portfolio: SimulatedPortfolio) -> None:
        self.portfolio = portfolio

    def get(self, portfolio_id: str) -> SimulatedPortfolio | None:
        return self.portfolio if portfolio_id == self.portfolio.portfolio_id else None

    def get_position(self, position_id: str) -> SimulatedPosition | None:
        return next(
            (item for item in self.portfolio.positions if item.position_id == position_id),
            None,
        )

    def list_timeline(
        self, *, portfolio_id: str, limit: int, offset: int
    ) -> tuple[PortfolioTimelineEvent, ...]:
        return self.portfolio.timeline[offset : offset + limit]


class StubJournalRepository:
    def __init__(self, journal: CandidateJournalEntry) -> None:
        self.journal = journal

    def list_by_portfolio(self, portfolio_id: str) -> tuple[CandidateJournalEntry, ...]:
        return (self.journal,) if portfolio_id == self.journal.portfolio_id else ()


client = TestClient(app)


@pytest.fixture
def position_resources() -> Iterator[tuple[SimulatedPortfolio, SimulatedPosition]]:
    journal = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    portfolio = journal.lifecycle.portfolio
    position = next(item for item in portfolio.positions if item.position_id == journal.position_id)
    portfolios = StubPortfolioRepository(portfolio)
    journals = StubJournalRepository(journal)
    app.dependency_overrides[get_simulated_portfolio_repository] = lambda: portfolios
    app.dependency_overrides[get_candidate_journal_repository] = lambda: journals
    try:
        yield portfolio, position
    finally:
        app.dependency_overrides.pop(get_simulated_portfolio_repository, None)
        app.dependency_overrides.pop(get_candidate_journal_repository, None)


def test_position_detail_api_serializes_complete_lineage(
    position_resources: tuple[SimulatedPortfolio, SimulatedPosition],
) -> None:
    portfolio, position = position_resources

    response = client.get(
        f"/api/v1/research/portfolios/{portfolio.portfolio_id}"
        f"/positions/{position.position_id}/detail"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["position_detail_version"] == "position-detail-v1"
    assert payload["position"]["position_id"] == position.position_id
    assert payload["lineage_status"] == "complete"
    assert payload["candidate"]["candidate_id"] is not None
    assert payload["nodes"][-1]["outcome"] == "target"
    assert payload["events"][-1]["event_type"] == "position_closed"


def test_position_detail_api_rejects_cross_portfolio_and_write_methods(
    position_resources: tuple[SimulatedPortfolio, SimulatedPosition],
) -> None:
    portfolio, position = position_resources
    path = (
        f"/api/v1/research/portfolios/{portfolio.portfolio_id}"
        f"/positions/{position.position_id}/detail"
    )

    assert (
        client.get(path.replace(portfolio.portfolio_id, "portfolio-0000000000000000")).status_code
        == 404
    )
    assert client.post(path, json={}).status_code == 405
