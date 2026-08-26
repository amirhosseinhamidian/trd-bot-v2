from typing import TYPE_CHECKING

from trd_bot.backtesting.benchmarks import (
    BenchmarkComparison,
    BenchmarkResult,
    BenchmarkType,
    BuyAndHoldBenchmark,
    ComparisonOutcome,
    PerformanceComparator,
    build_benchmark_run_id,
)
from trd_bot.backtesting.models import (
    BacktestConfig,
    BacktestEvent,
    BacktestEventType,
    ExitReason,
    PositionSide,
    build_backtest_event_id,
)
from trd_bot.backtesting.performance import (
    BacktestPerformanceAnalyzer,
    BacktestPerformanceReport,
    ClosedBacktestTrade,
    EquityPoint,
)

if TYPE_CHECKING:
    from trd_bot.backtesting.engine import BacktestEngine


def __getattr__(name: str) -> object:
    """Lazily expose dependencies that cross into the research package."""

    if name == "BacktestEngine":
        from trd_bot.backtesting.engine import BacktestEngine

        return BacktestEngine

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestEvent",
    "BacktestEventType",
    "BacktestPerformanceAnalyzer",
    "BacktestPerformanceReport",
    "BenchmarkComparison",
    "BenchmarkResult",
    "BenchmarkType",
    "BuyAndHoldBenchmark",
    "ClosedBacktestTrade",
    "ComparisonOutcome",
    "EquityPoint",
    "ExitReason",
    "PerformanceComparator",
    "PositionSide",
    "build_backtest_event_id",
    "build_benchmark_run_id",
]
