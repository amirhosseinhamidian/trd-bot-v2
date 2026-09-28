"""Read-only, fee-aware analytics of a single persisted simulation snapshot."""

from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from trd_bot.domain.market_data import TradingPair
from trd_bot.paper import PositionStatus, SimulatedPortfolio, SimulatedPosition
from trd_bot.research.candidate_journal import CandidateJournalEntry

ZERO = Decimal("0")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator <= 0:
        return None
    return (numerator / denominator).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _seconds(start: datetime, end: datetime) -> Decimal:
    delta = end - start
    return Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / 1_000_000


class AnalyticsModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PortfolioEquityPoint(AnalyticsModel):
    event_id: str
    sequence_number: int
    timestamp: datetime
    equity: Decimal
    return_fraction: Decimal
    drawdown_fraction: Decimal
    drawdown_duration_seconds: Decimal


class PortfolioPairPerformance(AnalyticsModel):
    pair: TradingPair
    closed_count: int
    open_count: int
    net_realized_pnl: Decimal
    fees_paid: Decimal


class PortfolioExitCount(AnalyticsModel):
    reason: str
    count: int


class PortfolioAnalyticsReport(AnalyticsModel):
    analytics_version: Literal["portfolio-analytics-v1"] = "portfolio-analytics-v1"
    portfolio_id: str
    as_of: datetime
    starting_equity: Decimal
    ending_equity: Decimal
    net_pnl: Decimal
    return_fraction: Decimal
    fees_paid: Decimal
    closed_net_pnl: Decimal
    open_gross_unrealized_pnl: Decimal
    open_entry_fees: Decimal
    open_net_pnl: Decimal
    closed_count: int
    open_count: int
    winning_count: int
    losing_count: int
    breakeven_count: int
    win_rate: Decimal | None
    profit_factor: Decimal | None
    profit_factor_status: Literal["available", "no_closed_trades", "no_losses"]
    expectancy: Decimal | None
    average_hold_seconds: Decimal | None
    duration_seconds: Decimal
    max_drawdown_fraction: Decimal
    max_drawdown_duration_seconds: Decimal
    current_drawdown_duration_seconds: Decimal
    open_exposure: Decimal
    exposure_fraction: Decimal | None
    equity_points: tuple[PortfolioEquityPoint, ...]
    trades_by_pair: tuple[PortfolioPairPerformance, ...]
    exit_mix: tuple[PortfolioExitCount, ...]
    interpretation: Literal["historical_research_only"] = "historical_research_only"


def _equity_points(portfolio: SimulatedPortfolio) -> tuple[PortfolioEquityPoint, ...]:
    peak = portfolio.starting_cash
    peak_at = portfolio.created_at
    previous_at = portfolio.created_at
    points: list[PortfolioEquityPoint] = []
    for event in portfolio.timeline:
        if event.occurred_at < previous_at:
            raise ValueError("portfolio timeline timestamps must be nondecreasing")
        # At recovery, retain the completed episode duration on the recovery point.
        was_underwater = bool(points and points[-1].drawdown_fraction > 0)
        duration = (
            _seconds(peak_at, event.occurred_at) if event.equity < peak or was_underwater else ZERO
        )
        peak = max(peak, event.equity)
        drawdown = (peak - event.equity) / peak
        points.append(
            PortfolioEquityPoint(
                event_id=event.event_id,
                sequence_number=event.sequence_number,
                timestamp=event.occurred_at,
                equity=event.equity,
                return_fraction=(event.equity - portfolio.starting_cash) / portfolio.starting_cash,
                drawdown_fraction=drawdown,
                drawdown_duration_seconds=duration,
            )
        )
        if event.equity >= peak:
            peak_at = event.occurred_at
        previous_at = event.occurred_at
    return tuple(points)


def _exit_mix(
    portfolio: SimulatedPortfolio,
    closed: Sequence[SimulatedPosition],
    journals: Sequence[CandidateJournalEntry],
) -> tuple[PortfolioExitCount, ...]:
    reasons: dict[str, set[str]] = {}
    positions = {position.position_id: position for position in closed}
    for journal in journals:
        if journal.portfolio_id != portfolio.portfolio_id or journal.exit_reason is None:
            continue
        position = positions.get(journal.position_id or "")
        if position is None:
            continue
        # Accept only journal evidence describing exactly this persisted closed position.
        evidence = next(
            (
                item
                for item in journal.lifecycle.portfolio.positions
                if item.position_id == position.position_id
            ),
            None,
        )
        if evidence == position:
            reasons.setdefault(position.position_id, set()).add(journal.exit_reason.value)
    counts: Counter[str] = Counter()
    for position in closed:
        values = reasons.get(position.position_id, set())
        reason = next(iter(values)) if len(values) == 1 else "unknown"
        counts[reason] += 1
    return tuple(
        PortfolioExitCount(reason=reason, count=counts[reason]) for reason in sorted(counts)
    )


class PortfolioAnalyticsBuilder:
    def build(
        self,
        portfolio: SimulatedPortfolio,
        *,
        journals: Sequence[CandidateJournalEntry] = (),
    ) -> PortfolioAnalyticsReport:
        closed = tuple(p for p in portfolio.positions if p.status is PositionStatus.CLOSED)
        opened = tuple(p for p in portfolio.positions if p.status is PositionStatus.OPEN)
        wins = tuple(p for p in closed if p.realized_pnl > 0)
        losses = tuple(p for p in closed if p.realized_pnl < 0)
        positive = sum((p.realized_pnl for p in wins), ZERO)
        negative = -sum((p.realized_pnl for p in losses), ZERO)
        entry_fees = sum((p.entry_fee for p in opened), ZERO)
        open_net = portfolio.unrealized_pnl - entry_fees
        net_pnl = portfolio.equity - portfolio.starting_cash
        if net_pnl != portfolio.realized_pnl + open_net:
            raise ValueError("portfolio analytics PnL must reconcile with equity")
        holds = sum(
            (_seconds(p.opened_at, p.closed_at) for p in closed if p.closed_at is not None),
            ZERO,
        )
        points = _equity_points(portfolio)
        groups: dict[tuple[str, str, str], list[SimulatedPosition]] = {}
        for position in portfolio.positions:
            key = (
                position.pair.base_asset,
                position.pair.quote_asset,
                position.pair.market_type.value,
            )
            groups.setdefault(key, []).append(position)
        pairs = tuple(
            PortfolioPairPerformance(
                pair=group[0].pair,
                closed_count=sum(p.status is PositionStatus.CLOSED for p in group),
                open_count=sum(p.status is PositionStatus.OPEN for p in group),
                net_realized_pnl=sum((p.realized_pnl for p in group), ZERO),
                fees_paid=sum((p.entry_fee + p.exit_fee for p in group), ZERO),
            )
            for _, group in sorted(groups.items())
        )
        exposure = sum((p.quantity * p.current_price for p in opened), ZERO)
        return PortfolioAnalyticsReport(
            portfolio_id=portfolio.portfolio_id,
            as_of=portfolio.updated_at,
            starting_equity=portfolio.starting_cash,
            ending_equity=portfolio.equity,
            net_pnl=net_pnl,
            return_fraction=net_pnl / portfolio.starting_cash,
            fees_paid=portfolio.fees_paid,
            closed_net_pnl=portfolio.realized_pnl,
            open_gross_unrealized_pnl=portfolio.unrealized_pnl,
            open_entry_fees=entry_fees,
            open_net_pnl=open_net,
            closed_count=len(closed),
            open_count=len(opened),
            winning_count=len(wins),
            losing_count=len(losses),
            breakeven_count=len(closed) - len(wins) - len(losses),
            win_rate=_ratio(Decimal(len(wins)), Decimal(len(closed))),
            profit_factor=_ratio(positive, negative),
            profit_factor_status=(
                "no_closed_trades" if not closed else "no_losses" if not losses else "available"
            ),
            expectancy=_ratio(portfolio.realized_pnl, Decimal(len(closed))),
            average_hold_seconds=_ratio(holds, Decimal(len(closed))),
            duration_seconds=_seconds(portfolio.created_at, portfolio.updated_at),
            max_drawdown_fraction=max(point.drawdown_fraction for point in points),
            max_drawdown_duration_seconds=max(point.drawdown_duration_seconds for point in points),
            current_drawdown_duration_seconds=(
                points[-1].drawdown_duration_seconds if points[-1].drawdown_fraction > 0 else ZERO
            ),
            open_exposure=exposure,
            exposure_fraction=_ratio(exposure, portfolio.equity),
            equity_points=points,
            trades_by_pair=pairs,
            exit_mix=_exit_mix(portfolio, closed, journals),
        )
