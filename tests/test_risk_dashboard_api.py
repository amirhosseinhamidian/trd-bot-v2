from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_candidate_journal import build_closed_lifecycle
from tests.test_risk_dashboard import build_rejected_journal
from trd_bot.api.dependencies import (
    get_candidate_journal_repository,
    get_simulated_portfolio_repository,
)
from trd_bot.api.routes.risk import router
from trd_bot.paper import SimulatedPortfolio
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
)


class InMemoryCandidateJournalRepository:
    def __init__(self, entries: tuple[CandidateJournalEntry, ...]) -> None:
        self._entries = entries

    def count(self) -> int:
        return len(self._entries)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[CandidateJournalEntry, ...]:
        return self._entries[offset : offset + limit]


class InMemoryPortfolioRepository:
    def __init__(self, portfolios: tuple[SimulatedPortfolio, ...]) -> None:
        self._portfolios = portfolios

    def get(self, portfolio_id: str) -> SimulatedPortfolio | None:
        return next(
            (portfolio for portfolio in self._portfolios if portfolio.portfolio_id == portfolio_id),
            None,
        )

    def count(self) -> int:
        return len(self._portfolios)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[SimulatedPortfolio, ...]:
        return self._portfolios[offset : offset + limit]


def build_client() -> tuple[TestClient, CandidateJournalEntry]:
    closed = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    rejected = build_rejected_journal()
    journal_repository = InMemoryCandidateJournalRepository((closed, rejected))
    portfolio_repository = InMemoryPortfolioRepository((closed.lifecycle.portfolio,))

    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_candidate_journal_repository] = lambda: journal_repository
    application.dependency_overrides[get_simulated_portfolio_repository] = lambda: (
        portfolio_repository
    )

    return TestClient(application), closed


def test_risk_dashboard_endpoint_returns_reconciled_read_only_projection() -> None:
    client, _ = build_client()

    response = client.get("/research/risk")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dashboard_version"] == "risk-dashboard-v1"
    assert payload["decisions"] == {
        "evaluated_count": 3,
        "approved_count": 2,
        "rejected_count": 1,
        "approval_rate": "0.666667",
    }
    assert (
        sum(reason["rejected_decisions"] for reason in payload["rejection_reasons"])
        == payload["decisions"]["rejected_count"]
    )
    assert len(payload["decision_events"]) == payload["decisions"]["evaluated_count"]

    method_response = client.post("/research/risk")
    assert method_response.status_code == 405


def test_risk_dashboard_endpoint_applies_inclusive_time_and_portfolio_filters() -> None:
    client, closed = build_client()

    response = client.get(
        "/research/risk",
        params={
            "from_time": "2026-08-26T13:00:00Z",
            "to_time": "2026-08-26T14:00:00Z",
            "portfolio_id": closed.portfolio_id,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["from_time"] == "2026-08-26T13:00:00Z"
    assert payload["to_time"] == "2026-08-26T14:00:00Z"
    assert payload["portfolio_id"] == closed.portfolio_id
    assert payload["decisions"]["evaluated_count"] == 1
    assert payload["decisions"]["approval_rate"] == "0.000000"


def test_risk_dashboard_endpoint_rejects_invalid_ranges_and_unknown_portfolios() -> None:
    client, _ = build_client()

    invalid_range = client.get(
        "/research/risk",
        params={
            "from_time": "2026-08-27T00:00:00Z",
            "to_time": "2026-08-26T00:00:00Z",
        },
    )
    unknown_portfolio = client.get(
        "/research/risk",
        params={"portfolio_id": "portfolio-0000000000000000"},
    )

    assert invalid_range.status_code == 422
    assert unknown_portfolio.status_code == 404
    assert unknown_portfolio.json() == {"detail": "simulated portfolio not found"}
