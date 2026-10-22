from datetime import timedelta
from decimal import Decimal

import pytest

from tests.test_candidate_journal import build_closed_lifecycle
from tests.test_paper_portfolio import CREATED_AT, PAIR, create_portfolio
from trd_bot.backtesting import PositionSide
from trd_bot.domain.market_data import TradingPair
from trd_bot.paper import SimulatedPortfolio, SimulatedPortfolioLedger
from trd_bot.research.candidate_journal import CandidateJournalBuilder
from trd_bot.research.portfolio_analytics import PortfolioAnalyticsBuilder
from trd_bot.research.position_monitoring import CandidateExitReason


def golden_portfolio() -> SimulatedPortfolio:
    ledger = SimulatedPortfolioLedger()
    opened = ledger.open_position(
        create_portfolio(fee_rate=Decimal("0.001")),
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("2"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    closed = ledger.close_position(
        opened,
        position_id=opened.positions[0].position_id,
        price=Decimal("110"),
        occurred_at=CREATED_AT + timedelta(hours=3),
    )
    second = ledger.open_position(
        closed,
        pair=TradingPair(base_asset="ETH", quote_asset="USDT"),
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=CREATED_AT + timedelta(hours=4),
    )
    return ledger.mark_to_market(
        second,
        position_id=second.positions[-1].position_id,
        price=Decimal("90"),
        occurred_at=CREATED_AT + timedelta(hours=5),
    )


def test_golden_open_closed_fees_and_equity_reconcile_without_mutation() -> None:
    portfolio = golden_portfolio()
    before = portfolio.model_dump_json()
    report = PortfolioAnalyticsBuilder().build(portfolio)
    assert report.closed_net_pnl == Decimal("19.58")
    assert report.open_gross_unrealized_pnl == Decimal("-10")
    assert report.open_entry_fees == Decimal("0.1")
    assert report.open_net_pnl == Decimal("-10.1")
    assert report.net_pnl == Decimal("9.48")
    assert report.ending_equity == Decimal("1009.48")
    assert report.fees_paid == Decimal("0.52")
    assert report.return_fraction == Decimal("0.00948")
    assert report.average_hold_seconds == 7200
    assert report.duration_seconds == 18000
    assert report.open_exposure == 90
    assert report.win_rate == 1
    assert report.expectancy == Decimal("19.58")
    assert report.profit_factor is None
    assert report.profit_factor_status == "no_losses"
    assert report.closed_count == report.open_count == 1
    assert sum(p.net_realized_pnl for p in report.trades_by_pair) == report.closed_net_pnl
    assert sum(p.fees_paid for p in report.trades_by_pair) == report.fees_paid
    assert sum(item.count for item in report.exit_mix) == report.closed_count
    assert report.exit_mix[0].reason == "unknown"
    assert [p.equity for p in report.equity_points] == [e.equity for e in portfolio.timeline]
    assert report.equity_points[-1].equity == report.ending_equity
    assert report.equity_points[-1].return_fraction == report.return_fraction
    assert PortfolioAnalyticsBuilder().build(portfolio) == report
    assert portfolio.model_dump_json() == before


def test_empty_portfolio_has_undefined_trade_statistics_and_flat_equity() -> None:
    report = PortfolioAnalyticsBuilder().build(create_portfolio())
    assert report.win_rate is None
    assert report.profit_factor is None
    assert report.profit_factor_status == "no_closed_trades"
    assert report.expectancy is None
    assert report.average_hold_seconds is None
    assert report.return_fraction == report.max_drawdown_fraction == 0
    assert report.max_drawdown_duration_seconds == 0
    assert report.closed_count == report.open_count == 0
    assert report.trades_by_pair == ()
    assert report.exit_mix == ()
    assert len(report.equity_points) == 1


def test_mixed_closed_trades_have_profit_factor_and_closed_only_expectancy() -> None:
    ledger = SimulatedPortfolioLedger()
    portfolio = create_portfolio()
    for hour, exit_price in [(1, "120"), (3, "90"), (5, "100")]:
        portfolio = ledger.open_position(
            portfolio,
            pair=PAIR,
            side=PositionSide.LONG,
            price=Decimal("100"),
            quantity=Decimal("1"),
            occurred_at=CREATED_AT + timedelta(hours=hour),
        )
        portfolio = ledger.close_position(
            portfolio,
            position_id=portfolio.positions[-1].position_id,
            price=Decimal(exit_price),
            occurred_at=CREATED_AT + timedelta(hours=hour + 1),
        )
    report = PortfolioAnalyticsBuilder().build(portfolio)
    assert report.winning_count == report.losing_count == report.breakeven_count == 1
    assert report.profit_factor == 2
    assert report.win_rate == Decimal("0.33333333")
    assert report.expectancy == Decimal("3.33333333")
    assert report.average_hold_seconds == 3600


def test_fee_turns_gross_winner_into_net_loser() -> None:
    ledger = SimulatedPortfolioLedger()
    opened = ledger.open_position(
        create_portfolio(fee_rate=Decimal("0.01")),
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    closed = ledger.close_position(
        opened,
        position_id=opened.positions[0].position_id,
        price=Decimal("101"),
        occurred_at=CREATED_AT + timedelta(hours=2),
    )
    report = PortfolioAnalyticsBuilder().build(closed)
    assert report.closed_net_pnl == Decimal("-1.01")
    assert report.win_rate == report.profit_factor == 0
    assert report.profit_factor_status == "available"
    assert report.losing_count == 1


@pytest.mark.parametrize("side", [PositionSide.LONG, PositionSide.SHORT])
def test_breakeven_count_and_no_loss_profit_factor(side: PositionSide) -> None:
    ledger = SimulatedPortfolioLedger()
    opened = ledger.open_position(
        create_portfolio(),
        pair=PAIR,
        side=side,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    closed = ledger.close_position(
        opened,
        position_id=opened.positions[0].position_id,
        price=Decimal("100"),
        occurred_at=CREATED_AT + timedelta(hours=2),
    )
    report = PortfolioAnalyticsBuilder().build(closed)
    assert report.breakeven_count == 1
    assert report.win_rate == report.expectancy == 0
    assert report.profit_factor is None


def test_drawdown_duration_includes_recovered_and_unrecovered_episodes() -> None:
    ledger = SimulatedPortfolioLedger()
    portfolio = ledger.open_position(
        create_portfolio(),
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("2"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    for hour, price in [(2, "90"), (3, "110"), (4, "90"), (7, "85")]:
        portfolio = ledger.mark_to_market(
            portfolio,
            position_id=portfolio.positions[0].position_id,
            price=Decimal(price),
            occurred_at=CREATED_AT + timedelta(hours=hour),
        )
    report = PortfolioAnalyticsBuilder().build(portfolio)
    assert report.equity_points[3].drawdown_duration_seconds == 7200
    assert report.equity_points[3].drawdown_fraction == 0
    assert report.max_drawdown_fraction == Decimal(50) / Decimal(1020)
    assert report.current_drawdown_duration_seconds == 14400
    assert report.max_drawdown_duration_seconds == 14400
    assert report.average_hold_seconds is None


def test_nonpositive_equity_does_not_produce_exposure_percentage() -> None:
    ledger = SimulatedPortfolioLedger()
    portfolio = ledger.open_position(
        create_portfolio(),
        pair=PAIR,
        side=PositionSide.SHORT,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=CREATED_AT + timedelta(hours=1),
    )
    portfolio = ledger.mark_to_market(
        portfolio,
        position_id=portfolio.positions[0].position_id,
        price=Decimal("1200"),
        occurred_at=CREATED_AT + timedelta(hours=2),
    )
    report = PortfolioAnalyticsBuilder().build(portfolio)
    assert report.ending_equity == -100
    assert report.open_exposure == 1200
    assert report.exposure_fraction is None
    assert report.max_drawdown_fraction == Decimal("1.1")


def test_exit_evidence_is_scoped_deduplicated_and_conflicts_are_unknown() -> None:
    journal = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    portfolio = journal.lifecycle.portfolio
    builder = PortfolioAnalyticsBuilder()
    report = builder.build(portfolio, journals=(journal, journal))
    assert report.exit_mix[0].reason == "target"
    assert report.exit_mix[0].count == 1
    conflict = journal.model_copy(update={"exit_reason": CandidateExitReason.INVALIDATION})
    assert builder.build(portfolio, journals=(journal, conflict)).exit_mix[0].reason == "unknown"
    foreign = journal.model_copy(update={"portfolio_id": "portfolio-0000000000000000"})
    assert builder.build(portfolio, journals=(foreign,)).exit_mix[0].reason == "unknown"
