from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.backtesting import PositionSide
from trd_bot.db.base import DatabaseBase
from trd_bot.db.models import SimulatedPortfolioRow
from trd_bot.db.simulated_portfolio_repositories import (
    SqlAlchemySimulatedPortfolioRepository,
)
from trd_bot.domain.market_data import TradingPair
from trd_bot.paper import (
    PortfolioStatus,
    SimulatedPortfolio,
    SimulatedPortfolioLedger,
    SimulationMode,
)

CREATED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    database_session = session_factory()

    try:
        yield database_session
    finally:
        database_session.close()
        engine.dispose()


def create_portfolio(
    *,
    dataset_id: str = "dataset-historical",
    mode: SimulationMode = SimulationMode.PAPER,
    created_at: datetime = CREATED_AT,
) -> SimulatedPortfolio:
    return SimulatedPortfolioLedger().create(
        mode=mode,
        dataset_id=dataset_id,
        starting_cash=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        created_at=created_at,
    )


def build_completed_portfolio() -> SimulatedPortfolio:
    ledger = SimulatedPortfolioLedger()
    portfolio = create_portfolio(mode=SimulationMode.SHADOW)
    opened = ledger.open_position(
        portfolio,
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("2"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    marked = ledger.mark_to_market(
        opened,
        position_id=opened.positions[0].position_id,
        price=Decimal("110"),
        occurred_at=CREATED_AT + timedelta(hours=2),
    )
    closed = ledger.close_position(
        marked,
        position_id=marked.positions[0].position_id,
        price=Decimal("110"),
        occurred_at=CREATED_AT + timedelta(hours=3),
    )
    return ledger.complete(
        closed,
        occurred_at=CREATED_AT + timedelta(hours=4),
    )


def test_repository_saves_and_reads_complete_aggregate(session: Session) -> None:
    repository = SqlAlchemySimulatedPortfolioRepository(session)
    portfolio = build_completed_portfolio()

    stored = repository.save(portfolio)
    loaded = repository.get(portfolio.portfolio_id)

    assert stored == portfolio
    assert loaded == portfolio
    assert repository.count() == 1
    assert (
        repository.list_positions(
            portfolio_id=portfolio.portfolio_id,
            limit=10,
            offset=0,
        )
        == portfolio.positions
    )
    assert (
        repository.list_timeline(
            portfolio_id=portfolio.portfolio_id,
            limit=10,
            offset=0,
        )
        == portfolio.timeline
    )
    assert repository.get_position(portfolio.positions[0].position_id) == portfolio.positions[0]

    row = session.get(SimulatedPortfolioRow, portfolio.portfolio_id)
    assert row is not None
    assert row.mode == SimulationMode.SHADOW.value
    assert row.status == PortfolioStatus.COMPLETED.value
    assert row.realized_pnl == portfolio.realized_pnl


def test_repository_replaces_children_when_aggregate_progresses(session: Session) -> None:
    repository = SqlAlchemySimulatedPortfolioRepository(session)
    ledger = SimulatedPortfolioLedger()
    created = create_portfolio()
    repository.save(created)

    opened = ledger.open_position(
        created,
        pair=PAIR,
        side=PositionSide.SHORT,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    repository.save(opened)

    marked = ledger.mark_to_market(
        opened,
        position_id=opened.positions[0].position_id,
        price=Decimal("90"),
        occurred_at=CREATED_AT + timedelta(hours=2),
    )
    repository.save(marked)

    closed = ledger.close_position(
        marked,
        position_id=marked.positions[0].position_id,
        price=Decimal("80"),
        occurred_at=CREATED_AT + timedelta(hours=3),
    )
    repository.save(closed)
    repository.save(closed)

    assert repository.count() == 1
    assert repository.get(closed.portfolio_id) == closed
    assert (
        repository.list_positions(
            portfolio_id=closed.portfolio_id,
            limit=10,
            offset=0,
        )
        == closed.positions
    )
    assert (
        repository.list_timeline(
            portfolio_id=closed.portfolio_id,
            limit=10,
            offset=0,
        )
        == closed.timeline
    )


def test_repository_lists_newest_portfolios_first(session: Session) -> None:
    repository = SqlAlchemySimulatedPortfolioRepository(session)
    first = create_portfolio(dataset_id="dataset-first")
    second = create_portfolio(
        dataset_id="dataset-second",
        created_at=CREATED_AT + timedelta(minutes=1),
    )
    repository.save(first)
    repository.save(second)

    page = repository.list_page(limit=1, offset=0)

    assert page == (second,)


def test_repository_returns_none_or_empty_for_missing_records(session: Session) -> None:
    repository = SqlAlchemySimulatedPortfolioRepository(session)

    assert repository.get("portfolio-0000000000000000") is None
    assert repository.get_position("position-0000000000000000") is None
    assert (
        repository.list_positions(
            portfolio_id="portfolio-0000000000000000",
            limit=10,
            offset=0,
        )
        == ()
    )
    assert (
        repository.list_timeline(
            portfolio_id="portfolio-0000000000000000",
            limit=10,
            offset=0,
        )
        == ()
    )


@pytest.mark.parametrize(
    ("limit", "offset", "message"),
    [
        (0, 0, "limit must be greater than zero"),
        (10, -1, "offset cannot be negative"),
    ],
)
def test_repository_validates_pagination(
    session: Session,
    limit: int,
    offset: int,
    message: str,
) -> None:
    repository = SqlAlchemySimulatedPortfolioRepository(session)

    with pytest.raises(ValueError, match=message):
        repository.list_page(limit=limit, offset=offset)
    with pytest.raises(ValueError, match=message):
        repository.list_positions(
            portfolio_id="portfolio-0000000000000000",
            limit=limit,
            offset=offset,
        )
    with pytest.raises(ValueError, match=message):
        repository.list_timeline(
            portfolio_id="portfolio-0000000000000000",
            limit=limit,
            offset=offset,
        )
