from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.backtesting import PositionSide
from trd_bot.domain.market_data import TradingPair
from trd_bot.paper import (
    PortfolioEventType,
    PortfolioStatus,
    PositionStatus,
    SimulatedPortfolio,
    SimulatedPortfolioLedger,
    SimulationMode,
)

CREATED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")


def create_portfolio(
    *,
    mode: SimulationMode = SimulationMode.PAPER,
    fee_rate: Decimal = Decimal("0"),
) -> SimulatedPortfolio:
    return SimulatedPortfolioLedger().create(
        mode=mode,
        dataset_id="dataset-historical",
        starting_cash=Decimal("1000"),
        fee_rate=fee_rate,
        created_at=CREATED_AT,
    )


@pytest.mark.parametrize("mode", [SimulationMode.PAPER, SimulationMode.SHADOW])
def test_creates_offline_portfolio_modes(mode: SimulationMode) -> None:
    portfolio = create_portfolio(mode=mode)
    assert portfolio.mode is mode
    assert portfolio.status is PortfolioStatus.ACTIVE
    assert portfolio.cash == Decimal("1000.00000000")
    assert portfolio.equity == Decimal("1000.00000000")
    assert portfolio.positions == ()
    assert portfolio.timeline[0].event_type is PortfolioEventType.PORTFOLIO_CREATED


def test_long_position_lifecycle_tracks_cash_equity_fees_and_pnl() -> None:
    ledger = SimulatedPortfolioLedger()
    portfolio = create_portfolio(fee_rate=Decimal("0.001"))
    opened = ledger.open_position(
        portfolio,
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("2"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    position = opened.positions[0]
    assert position.status is PositionStatus.OPEN
    assert position.reserved_notional == Decimal("200.00000000")
    assert position.entry_fee == Decimal("0.20000000")
    assert opened.cash == Decimal("799.80000000")
    assert opened.equity == Decimal("999.80000000")

    marked = ledger.mark_to_market(
        opened,
        position_id=position.position_id,
        price=Decimal("110"),
        occurred_at=CREATED_AT + timedelta(hours=2),
    )
    assert marked.unrealized_pnl == Decimal("20.00000000")
    assert marked.equity == Decimal("1019.80000000")

    closed = ledger.close_position(
        marked,
        position_id=position.position_id,
        price=Decimal("110"),
        occurred_at=CREATED_AT + timedelta(hours=3),
    )
    closed_position = closed.positions[0]
    assert closed_position.status is PositionStatus.CLOSED
    assert closed_position.gross_realized_pnl == Decimal("20.00000000")
    assert closed_position.exit_fee == Decimal("0.22000000")
    assert closed_position.realized_pnl == Decimal("19.58000000")
    assert closed.cash == Decimal("1019.58000000")
    assert closed.equity == Decimal("1019.58000000")
    assert closed.realized_pnl == Decimal("19.58000000")
    assert closed.unrealized_pnl == Decimal("0")
    assert closed.fees_paid == Decimal("0.42000000")
    assert [event.event_type for event in closed.timeline] == [
        PortfolioEventType.PORTFOLIO_CREATED,
        PortfolioEventType.POSITION_OPENED,
        PortfolioEventType.POSITION_MARKED,
        PortfolioEventType.POSITION_CLOSED,
    ]
    assert [event.sequence_number for event in closed.timeline] == [1, 2, 3, 4]


def test_short_position_uses_inverse_price_change_for_pnl() -> None:
    ledger = SimulatedPortfolioLedger()
    opened = ledger.open_position(
        create_portfolio(),
        pair=PAIR,
        side=PositionSide.SHORT,
        price=Decimal("100"),
        quantity=Decimal("2"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    position_id = opened.positions[0].position_id
    marked = ledger.mark_to_market(
        opened,
        position_id=position_id,
        price=Decimal("90"),
        occurred_at=CREATED_AT + timedelta(hours=2),
    )
    assert marked.unrealized_pnl == Decimal("20.00000000")
    assert marked.equity == Decimal("1020.00000000")
    closed = ledger.close_position(
        marked,
        position_id=position_id,
        price=Decimal("80"),
        occurred_at=CREATED_AT + timedelta(hours=3),
    )
    assert closed.realized_pnl == Decimal("40.00000000")
    assert closed.cash == Decimal("1040.00000000")


def test_rejects_a_second_simultaneous_position() -> None:
    ledger = SimulatedPortfolioLedger()
    opened = ledger.open_position(
        create_portfolio(),
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="another position is open"):
        ledger.open_position(
            opened,
            pair=PAIR,
            side=PositionSide.SHORT,
            price=Decimal("100"),
            quantity=Decimal("1"),
            occurred_at=CREATED_AT + timedelta(hours=2),
        )


def test_rejects_insufficient_simulated_cash() -> None:
    with pytest.raises(ValueError, match="insufficient simulated cash"):
        SimulatedPortfolioLedger().open_position(
            create_portfolio(fee_rate=Decimal("0.001")),
            pair=PAIR,
            side=PositionSide.LONG,
            price=Decimal("1000"),
            quantity=Decimal("1"),
            occurred_at=CREATED_AT + timedelta(hours=1),
        )


def test_rejects_non_chronological_transitions() -> None:
    portfolio = create_portfolio()
    with pytest.raises(ValueError, match="must move forward"):
        SimulatedPortfolioLedger().open_position(
            portfolio,
            pair=PAIR,
            side=PositionSide.LONG,
            price=Decimal("100"),
            quantity=Decimal("1"),
            occurred_at=CREATED_AT,
        )


def test_rejects_unknown_open_position() -> None:
    ledger = SimulatedPortfolioLedger()
    opened = ledger.open_position(
        create_portfolio(),
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="was not found"):
        ledger.mark_to_market(
            opened,
            position_id="position-0000000000000000",
            price=Decimal("101"),
            occurred_at=CREATED_AT + timedelta(hours=2),
        )


def test_complete_requires_no_open_position_and_is_terminal() -> None:
    ledger = SimulatedPortfolioLedger()
    opened = ledger.open_position(
        create_portfolio(),
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="with an open position"):
        ledger.complete(opened, occurred_at=CREATED_AT + timedelta(hours=2))

    closed = ledger.close_position(
        opened,
        position_id=opened.positions[0].position_id,
        price=Decimal("105"),
        occurred_at=CREATED_AT + timedelta(hours=2),
    )
    completed = ledger.complete(closed, occurred_at=CREATED_AT + timedelta(hours=3))
    assert completed.status is PortfolioStatus.COMPLETED
    assert completed.timeline[-1].event_type is PortfolioEventType.PORTFOLIO_COMPLETED
    with pytest.raises(ValueError, match="already completed"):
        ledger.complete(completed, occurred_at=CREATED_AT + timedelta(hours=4))
