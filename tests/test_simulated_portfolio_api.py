from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_simulated_portfolio_repository,
)
from trd_bot.backtesting import PositionSide
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.main import app
from trd_bot.paper import (
    PortfolioTimelineEvent,
    SimulatedPortfolio,
    SimulatedPortfolioLedger,
    SimulatedPosition,
    SimulationMode,
)
from trd_bot.research import DatasetBuilder, DatasetSnapshot, InMemoryDatasetRepository

CREATED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
client = TestClient(app)


class InMemorySimulatedPortfolioRepository:
    def __init__(self) -> None:
        self._portfolios: dict[str, SimulatedPortfolio] = {}

    def save(self, portfolio: SimulatedPortfolio) -> SimulatedPortfolio:
        self._portfolios[portfolio.portfolio_id] = portfolio
        return portfolio

    def get(self, portfolio_id: str) -> SimulatedPortfolio | None:
        return self._portfolios.get(portfolio_id)

    def get_position(self, position_id: str) -> SimulatedPosition | None:
        for portfolio in self._portfolios.values():
            for position in portfolio.positions:
                if position.position_id == position_id:
                    return position
        return None

    def count(self) -> int:
        return len(self._portfolios)

    def count_positions(self, portfolio_id: str) -> int:
        portfolio = self.get(portfolio_id)
        return len(portfolio.positions) if portfolio is not None else 0

    def count_timeline(self, portfolio_id: str) -> int:
        portfolio = self.get(portfolio_id)
        return len(portfolio.timeline) if portfolio is not None else 0

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[SimulatedPortfolio, ...]:
        portfolios = tuple(
            sorted(
                self._portfolios.values(),
                key=lambda item: (item.created_at, item.portfolio_id),
                reverse=True,
            )
        )
        return portfolios[offset : offset + limit]

    def list_positions(
        self,
        *,
        portfolio_id: str,
        limit: int,
        offset: int,
    ) -> tuple[SimulatedPosition, ...]:
        portfolio = self.get(portfolio_id)
        if portfolio is None:
            return ()
        return portfolio.positions[offset : offset + limit]

    def list_timeline(
        self,
        *,
        portfolio_id: str,
        limit: int,
        offset: int,
    ) -> tuple[PortfolioTimelineEvent, ...]:
        portfolio = self.get(portfolio_id)
        if portfolio is None:
            return ()
        return portfolio.timeline[offset : offset + limit]


@pytest.fixture
def repositories() -> Iterator[
    tuple[
        InMemoryDatasetRepository,
        InMemorySimulatedPortfolioRepository,
    ]
]:
    datasets = InMemoryDatasetRepository()
    portfolios = InMemorySimulatedPortfolioRepository()

    def override_datasets() -> InMemoryDatasetRepository:
        return datasets

    def override_portfolios() -> InMemorySimulatedPortfolioRepository:
        return portfolios

    app.dependency_overrides[get_dataset_repository] = override_datasets
    app.dependency_overrides[get_simulated_portfolio_repository] = override_portfolios

    try:
        yield datasets, portfolios
    finally:
        app.dependency_overrides.pop(get_dataset_repository, None)
        app.dependency_overrides.pop(get_simulated_portfolio_repository, None)


def create_dataset() -> DatasetSnapshot:
    candles = []
    for index, price_text in enumerate(("100", "105", "110")):
        open_time = CREATED_AT + timedelta(hours=index)
        price = Decimal(price_text)
        candles.append(
            OHLCVCandle(
                source="historical-test",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                received_at=open_time + timedelta(hours=1, minutes=1),
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )
    return DatasetBuilder().build(
        name="Portfolio API historical dataset",
        candles=candles,
        created_at=CREATED_AT,
    )


def create_completed_portfolio(
    *,
    dataset_id: str,
    created_at: datetime = CREATED_AT,
) -> SimulatedPortfolio:
    ledger = SimulatedPortfolioLedger()
    created = ledger.create(
        mode=SimulationMode.SHADOW,
        dataset_id=dataset_id,
        starting_cash=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        created_at=created_at,
    )
    opened = ledger.open_position(
        created,
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("2"),
        occurred_at=created_at + timedelta(hours=1),
    )
    marked = ledger.mark_to_market(
        opened,
        position_id=opened.positions[0].position_id,
        price=Decimal("110"),
        occurred_at=created_at + timedelta(hours=2),
    )
    closed = ledger.close_position(
        marked,
        position_id=marked.positions[0].position_id,
        price=Decimal("110"),
        occurred_at=created_at + timedelta(hours=3),
    )
    return ledger.complete(
        closed,
        occurred_at=created_at + timedelta(hours=4),
    )


@pytest.mark.parametrize("mode", ["paper", "shadow"])
def test_api_creates_portfolio_for_existing_historical_dataset(
    repositories: tuple[
        InMemoryDatasetRepository,
        InMemorySimulatedPortfolioRepository,
    ],
    mode: str,
) -> None:
    datasets, portfolios = repositories
    dataset = datasets.save(create_dataset())

    response = client.post(
        "/api/v1/research/portfolios",
        json={
            "dataset_id": dataset.dataset_id,
            "mode": mode,
            "starting_cash": "1000",
            "fee_rate": "0.001",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["dataset_id"] == dataset.dataset_id
    assert data["mode"] == mode
    assert data["status"] == "active"
    assert data["positions"] == []
    assert len(data["timeline"]) == 1
    assert portfolios.count() == 1


def test_api_rejects_unknown_dataset_without_creating_portfolio(
    repositories: tuple[
        InMemoryDatasetRepository,
        InMemorySimulatedPortfolioRepository,
    ],
) -> None:
    _, portfolios = repositories

    response = client.post(
        "/api/v1/research/portfolios",
        json={"dataset_id": "dataset-0000000000000000"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "dataset not found"
    assert portfolios.count() == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"dataset_id": "dataset-valid", "mode": "live"},
        {"dataset_id": "dataset-valid", "starting_cash": "0"},
        {"dataset_id": "dataset-valid", "fee_rate": "1"},
    ],
)
def test_api_rejects_invalid_portfolio_configuration(
    repositories: tuple[
        InMemoryDatasetRepository,
        InMemorySimulatedPortfolioRepository,
    ],
    payload: dict[str, str],
) -> None:
    response = client.post("/api/v1/research/portfolios", json=payload)
    assert response.status_code == 422


def test_api_lists_lightweight_portfolio_summaries(
    repositories: tuple[
        InMemoryDatasetRepository,
        InMemorySimulatedPortfolioRepository,
    ],
) -> None:
    datasets, portfolios = repositories
    dataset = datasets.save(create_dataset())
    first = SimulatedPortfolioLedger().create(
        mode=SimulationMode.PAPER,
        dataset_id=dataset.dataset_id,
        starting_cash=Decimal("1000"),
        created_at=CREATED_AT,
    )
    second = create_completed_portfolio(
        dataset_id=dataset.dataset_id,
        created_at=CREATED_AT + timedelta(days=1),
    )
    portfolios.save(first)
    portfolios.save(second)

    response = client.get(
        "/api/v1/research/portfolios",
        params={"limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["count"] == 1
    assert data["has_next"] is True
    assert data["items"][0]["portfolio_id"] == second.portfolio_id
    assert data["items"][0]["position_count"] == 1
    assert data["items"][0]["event_count"] == 5
    assert "positions" not in data["items"][0]
    assert "timeline" not in data["items"][0]


def test_api_returns_portfolio_position_and_timeline_resources(
    repositories: tuple[
        InMemoryDatasetRepository,
        InMemorySimulatedPortfolioRepository,
    ],
) -> None:
    datasets, portfolios = repositories
    dataset = datasets.save(create_dataset())
    portfolio = portfolios.save(create_completed_portfolio(dataset_id=dataset.dataset_id))
    position = portfolio.positions[0]

    detail_response = client.get(f"/api/v1/research/portfolios/{portfolio.portfolio_id}")
    positions_response = client.get(
        f"/api/v1/research/portfolios/{portfolio.portfolio_id}/positions"
    )
    position_response = client.get(
        f"/api/v1/research/portfolios/{portfolio.portfolio_id}/positions/{position.position_id}"
    )
    timeline_response = client.get(
        f"/api/v1/research/portfolios/{portfolio.portfolio_id}/timeline",
        params={"limit": 2, "offset": 1},
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["portfolio_id"] == portfolio.portfolio_id
    assert positions_response.status_code == 200
    assert positions_response.json()["total"] == 1
    assert positions_response.json()["items"][0]["position_id"] == position.position_id
    assert position_response.status_code == 200
    assert position_response.json()["position_id"] == position.position_id
    assert timeline_response.status_code == 200
    assert timeline_response.json()["total"] == 5
    assert timeline_response.json()["count"] == 2
    assert timeline_response.json()["items"][0]["sequence_number"] == 2


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "/positions",
        "/timeline",
    ],
)
def test_api_returns_404_for_unknown_portfolio(
    repositories: tuple[
        InMemoryDatasetRepository,
        InMemorySimulatedPortfolioRepository,
    ],
    suffix: str,
) -> None:
    response = client.get(f"/api/v1/research/portfolios/portfolio-0000000000000000{suffix}")
    assert response.status_code == 404
    assert response.json()["detail"] == "simulated portfolio not found"


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ],
)
def test_api_rejects_invalid_portfolio_pagination(
    repositories: tuple[
        InMemoryDatasetRepository,
        InMemorySimulatedPortfolioRepository,
    ],
    params: dict[str, int],
) -> None:
    response = client.get("/api/v1/research/portfolios", params=params)
    assert response.status_code == 422
