"""Read-only analytics derived from an immutable research experiment."""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from trd_bot.backtesting.models import PositionSide
from trd_bot.backtesting.performance import (
    BacktestPerformanceReport,
    ClosedBacktestTrade,
    EquityPoint,
)
from trd_bot.research.experiments import ResearchExperiment

ZERO = Decimal("0")


class AnalyticsModel(BaseModel):
    """Strict immutable base model for the public analytics contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ResearchMetricDefinition(AnalyticsModel):
    """Human-readable definition of one metric exposed by the report."""

    key: Literal[
        "total_return",
        "excess_return",
        "max_drawdown_fraction",
        "win_rate",
        "profit_factor",
        "period_return_contribution",
    ]
    unit: Literal["fraction", "currency", "count", "ratio"]
    preference: Literal["higher_is_better", "lower_is_better", "context_only"]
    definition: str
    formula: str


class ExperimentTradeDistribution(AnalyticsModel):
    """Fee-aware distribution of closed strategy trades."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    flat_trades: int
    long_trades: int
    short_trades: int
    win_rate: Decimal | None
    gross_profit: Decimal
    gross_loss: Decimal
    total_fees: Decimal
    net_pnl: Decimal
    profit_factor: Decimal | None
    average_net_pnl: Decimal | None
    median_net_pnl: Decimal | None
    best_net_pnl: Decimal | None
    worst_net_pnl: Decimal | None


class ExperimentPeriodReturn(AnalyticsModel):
    """Realized contribution from trades closed in one UTC calendar month."""

    period: str
    started_at: datetime
    ended_at: datetime
    opening_balance: Decimal
    ending_balance: Decimal
    net_pnl: Decimal
    return_contribution: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    flat_trades: int


class HistoricalDrawdownEpisode(AnalyticsModel):
    """One continuous realized-equity drawdown episode."""

    episode_number: int
    started_at: datetime
    trough_at: datetime
    recovered_at: datetime | None
    peak_balance: Decimal
    trough_balance: Decimal
    max_drawdown: Decimal
    max_drawdown_fraction: Decimal
    trades_underwater: int
    status: Literal["recovered", "unrecovered"]


class ExperimentAnalyticsReport(AnalyticsModel):
    """Dashboard-ready analytics for one stored historical experiment."""

    experiment_id: str
    dataset_id: str
    analytics_version: Literal["research-analytics-v1"] = "research-analytics-v1"
    period_granularity: Literal["utc_calendar_month"] = "utc_calendar_month"
    period_start: datetime
    period_end: datetime
    starting_balance: Decimal
    ending_balance: Decimal
    strategy_total_return: Decimal
    benchmark_total_return: Decimal
    excess_return: Decimal
    strategy_max_drawdown_fraction: Decimal
    benchmark_max_drawdown_fraction: Decimal
    trade_distribution: ExperimentTradeDistribution
    returns_by_period: tuple[ExperimentPeriodReturn, ...]
    drawdown_episodes: tuple[HistoricalDrawdownEpisode, ...]
    metric_definitions: tuple[ResearchMetricDefinition, ...]
    interpretation: Literal["historical_research_only"] = "historical_research_only"


def _median(values: tuple[Decimal, ...]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)


def _trade_distribution(report: BacktestPerformanceReport) -> ExperimentTradeDistribution:
    net_values = tuple(trade.net_pnl for trade in report.trades)
    return ExperimentTradeDistribution(
        total_trades=report.total_trades,
        winning_trades=report.winning_trades,
        losing_trades=report.losing_trades,
        flat_trades=report.flat_trades,
        long_trades=sum(trade.side is PositionSide.LONG for trade in report.trades),
        short_trades=sum(trade.side is PositionSide.SHORT for trade in report.trades),
        win_rate=report.win_rate,
        gross_profit=report.gross_profit,
        gross_loss=report.gross_loss,
        total_fees=report.total_fees,
        net_pnl=report.net_pnl,
        profit_factor=report.profit_factor,
        average_net_pnl=(
            report.net_pnl / Decimal(report.total_trades) if report.total_trades else None
        ),
        median_net_pnl=_median(net_values),
        best_net_pnl=max(net_values, default=None),
        worst_net_pnl=min(net_values, default=None),
    )


def _period_key(value: datetime) -> tuple[int, int]:
    normalized = value.astimezone(UTC)
    return normalized.year, normalized.month


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=UTC)


def _next_month(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1, tzinfo=UTC)
    return datetime(value.year, value.month + 1, 1, tzinfo=UTC)


def _period_returns(
    *,
    report: BacktestPerformanceReport,
    period_start: datetime,
    period_end: datetime,
) -> tuple[ExperimentPeriodReturn, ...]:
    trades_by_period: dict[tuple[int, int], list[ClosedBacktestTrade]] = defaultdict(list)
    for trade in report.trades:
        trades_by_period[_period_key(trade.exit_time)].append(trade)

    current = _month_start(period_start.year, period_start.month)
    final = _month_start(period_end.year, period_end.month)
    opening_balance = report.starting_balance
    periods: list[ExperimentPeriodReturn] = []

    while current <= final:
        trades = tuple(trades_by_period.get((current.year, current.month), ()))
        net_pnl = sum((trade.net_pnl for trade in trades), start=ZERO)
        ending_balance = opening_balance + net_pnl
        periods.append(
            ExperimentPeriodReturn(
                period=f"{current.year:04d}-{current.month:02d}",
                started_at=max(current, period_start),
                ended_at=min(_next_month(current), period_end),
                opening_balance=opening_balance,
                ending_balance=ending_balance,
                net_pnl=net_pnl,
                return_contribution=net_pnl / report.starting_balance,
                total_trades=len(trades),
                winning_trades=sum(trade.net_pnl > 0 for trade in trades),
                losing_trades=sum(trade.net_pnl < 0 for trade in trades),
                flat_trades=sum(trade.net_pnl == 0 for trade in trades),
            )
        )
        opening_balance = ending_balance
        current = _next_month(current)

    return tuple(periods)


def _drawdown_episodes(points: tuple[EquityPoint, ...]) -> tuple[HistoricalDrawdownEpisode, ...]:
    episodes: list[HistoricalDrawdownEpisode] = []
    started_at: datetime | None = None
    peak_balance = ZERO
    trough: EquityPoint | None = None
    trades_underwater = 0

    for point in points:
        if point.drawdown > 0:
            if started_at is None:
                started_at = point.timestamp
                peak_balance = point.peak_balance
                trough = point
                trades_underwater = 0
            trades_underwater += 1
            if trough is None or point.drawdown > trough.drawdown:
                trough = point
            continue

        if started_at is not None and trough is not None:
            episodes.append(
                HistoricalDrawdownEpisode(
                    episode_number=len(episodes) + 1,
                    started_at=started_at,
                    trough_at=trough.timestamp,
                    recovered_at=point.timestamp,
                    peak_balance=peak_balance,
                    trough_balance=trough.balance,
                    max_drawdown=trough.drawdown,
                    max_drawdown_fraction=trough.drawdown_fraction,
                    trades_underwater=trades_underwater,
                    status="recovered",
                )
            )
            started_at = None
            trough = None
            trades_underwater = 0

    if started_at is not None and trough is not None:
        episodes.append(
            HistoricalDrawdownEpisode(
                episode_number=len(episodes) + 1,
                started_at=started_at,
                trough_at=trough.timestamp,
                recovered_at=None,
                peak_balance=peak_balance,
                trough_balance=trough.balance,
                max_drawdown=trough.drawdown,
                max_drawdown_fraction=trough.drawdown_fraction,
                trades_underwater=trades_underwater,
                status="unrecovered",
            )
        )

    return tuple(episodes)


METRIC_DEFINITIONS = (
    ResearchMetricDefinition(
        key="total_return",
        unit="fraction",
        preference="higher_is_better",
        definition="Realized strategy net profit relative to starting capital.",
        formula="strategy_net_pnl / starting_balance",
    ),
    ResearchMetricDefinition(
        key="excess_return",
        unit="fraction",
        preference="higher_is_better",
        definition="Strategy return minus the buy-and-hold benchmark return.",
        formula="strategy_total_return - benchmark_total_return",
    ),
    ResearchMetricDefinition(
        key="max_drawdown_fraction",
        unit="fraction",
        preference="lower_is_better",
        definition="Largest peak-to-trough decline in realized equity.",
        formula="max((peak_balance - balance) / peak_balance)",
    ),
    ResearchMetricDefinition(
        key="win_rate",
        unit="fraction",
        preference="context_only",
        definition="Share of closed trades with positive net profit.",
        formula="winning_trades / total_trades",
    ),
    ResearchMetricDefinition(
        key="profit_factor",
        unit="ratio",
        preference="higher_is_better",
        definition="Gross profitable net PnL divided by gross losing net PnL.",
        formula="gross_profit / gross_loss",
    ),
    ResearchMetricDefinition(
        key="period_return_contribution",
        unit="fraction",
        preference="context_only",
        definition="Monthly realized net profit relative to initial capital.",
        formula="period_net_pnl / starting_balance",
    ),
)


class ExperimentAnalyticsBuilder:
    """Build the versioned analytics contract without mutating stored research."""

    def build(self, experiment: ResearchExperiment) -> ExperimentAnalyticsReport:
        strategy = experiment.result.performance_report
        benchmark = experiment.result.benchmark_result.performance_report
        all_trades = strategy.trades + benchmark.trades
        period_start = min(
            (trade.entry_time for trade in all_trades),
            default=experiment.created_at,
        )
        period_end = max(
            (trade.exit_time for trade in all_trades),
            default=experiment.created_at,
        )

        return ExperimentAnalyticsReport(
            experiment_id=experiment.experiment_id,
            dataset_id=experiment.dataset_id,
            period_start=period_start,
            period_end=period_end,
            starting_balance=strategy.starting_balance,
            ending_balance=strategy.ending_balance,
            strategy_total_return=strategy.total_return,
            benchmark_total_return=benchmark.total_return,
            excess_return=experiment.result.benchmark_comparison.return_delta,
            strategy_max_drawdown_fraction=strategy.max_drawdown_fraction,
            benchmark_max_drawdown_fraction=benchmark.max_drawdown_fraction,
            trade_distribution=_trade_distribution(strategy),
            returns_by_period=_period_returns(
                report=strategy,
                period_start=period_start,
                period_end=period_end,
            ),
            drawdown_episodes=_drawdown_episodes(strategy.equity_curve),
            metric_definitions=METRIC_DEFINITIONS,
        )
