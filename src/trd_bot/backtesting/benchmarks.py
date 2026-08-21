import hashlib
import json
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
)
from trd_bot.research.datasets import DatasetSnapshot


class BenchmarkType(StrEnum):
    """Supported offline research benchmarks."""

    BUY_AND_HOLD = "buy_and_hold"


class ComparisonOutcome(StrEnum):
    """Result of comparing strategy return with benchmark return."""

    STRATEGY = "strategy"
    BENCHMARK = "benchmark"
    TIE = "tie"


class BenchmarkResult(BaseModel):
    """Complete result of one deterministic benchmark run."""

    model_config = ConfigDict(frozen=True)

    benchmark_type: BenchmarkType
    run_id: str = Field(pattern=r"^benchmark-[a-f0-9]{16}$")
    dataset_id: str = Field(min_length=1)
    config: BacktestConfig
    events: tuple[BacktestEvent, ...]
    performance_report: BacktestPerformanceReport

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if len(self.events) != 2:
            raise ValueError("buy-and-hold benchmark must contain exactly two events")
        if self.events[0].event_type != BacktestEventType.POSITION_OPENED:
            raise ValueError("benchmark must start with a position-opened event")
        if self.events[1].event_type != BacktestEventType.POSITION_CLOSED:
            raise ValueError("benchmark must end with a position-closed event")
        if self.performance_report.run_id != self.run_id:
            raise ValueError("benchmark performance report run does not match")
        if self.performance_report.dataset_id != self.dataset_id:
            raise ValueError("benchmark performance report dataset does not match")
        if self.performance_report.starting_balance != self.config.starting_balance:
            raise ValueError("benchmark performance report balance does not match config")
        return self


class BenchmarkComparison(BaseModel):
    """Risk-aware comparison between one strategy and one benchmark."""

    model_config = ConfigDict(frozen=True)

    strategy_run_id: str = Field(min_length=1)
    benchmark_run_id: str = Field(pattern=r"^benchmark-[a-f0-9]{16}$")
    dataset_id: str = Field(min_length=1)
    strategy_return: Decimal
    benchmark_return: Decimal
    return_delta: Decimal
    net_pnl_delta: Decimal
    max_drawdown_fraction_delta: Decimal
    strategy_has_lower_drawdown: bool
    outcome: ComparisonOutcome

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        if self.return_delta != self.strategy_return - self.benchmark_return:
            raise ValueError("return delta is inconsistent with compared returns")

        expected_outcome = ComparisonOutcome.TIE
        if self.return_delta > 0:
            expected_outcome = ComparisonOutcome.STRATEGY
        elif self.return_delta < 0:
            expected_outcome = ComparisonOutcome.BENCHMARK

        if self.outcome != expected_outcome:
            raise ValueError("comparison outcome is inconsistent with return delta")
        return self


def build_benchmark_run_id(
    *,
    dataset_id: str,
    benchmark_type: BenchmarkType,
    config: BacktestConfig,
) -> str:
    """Build a deterministic benchmark run identifier."""

    config_payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    identity = "::".join([dataset_id, benchmark_type.value, config_payload])
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"benchmark-{digest[:16]}"


class BuyAndHoldBenchmark:
    """Hold one simulated long position across the complete dataset."""

    def __init__(
        self,
        performance_analyzer: BacktestPerformanceAnalyzer | None = None,
    ) -> None:
        self._performance_analyzer = performance_analyzer or BacktestPerformanceAnalyzer()

    def run(
        self,
        *,
        dataset: DatasetSnapshot,
        config: BacktestConfig,
    ) -> BenchmarkResult:
        run_id = build_benchmark_run_id(
            dataset_id=dataset.dataset_id,
            benchmark_type=BenchmarkType.BUY_AND_HOLD,
            config=config,
        )

        first_candle = dataset.candles[0]
        final_candle = dataset.candles[-1]
        entry_price = first_candle.open_price * (Decimal("1") + config.slippage_rate)
        exit_price = final_candle.close_price * (Decimal("1") - config.slippage_rate)
        allocation = config.starting_balance * config.allocation_fraction
        quantity = allocation / entry_price

        events = (
            BacktestEvent(
                event_id=build_backtest_event_id(
                    run_id=run_id,
                    sequence_number=1,
                    event_type=BacktestEventType.POSITION_OPENED,
                    timestamp=first_candle.open_time,
                ),
                sequence_number=1,
                event_type=BacktestEventType.POSITION_OPENED,
                timestamp=first_candle.open_time,
                pair=dataset.pair,
                side=PositionSide.LONG,
                price=entry_price,
                quantity=quantity,
                signal_id=self._build_signal_id(run_id),
                exit_reason=None,
            ),
            BacktestEvent(
                event_id=build_backtest_event_id(
                    run_id=run_id,
                    sequence_number=2,
                    event_type=BacktestEventType.POSITION_CLOSED,
                    timestamp=final_candle.close_time,
                ),
                sequence_number=2,
                event_type=BacktestEventType.POSITION_CLOSED,
                timestamp=final_candle.close_time,
                pair=dataset.pair,
                side=PositionSide.LONG,
                price=exit_price,
                quantity=quantity,
                signal_id=None,
                exit_reason=ExitReason.END_OF_DATA,
            ),
        )

        performance_report = self._performance_analyzer.analyze(
            run_id=run_id,
            dataset_id=dataset.dataset_id,
            events=events,
            config=config,
        )

        return BenchmarkResult(
            benchmark_type=BenchmarkType.BUY_AND_HOLD,
            run_id=run_id,
            dataset_id=dataset.dataset_id,
            config=config,
            events=events,
            performance_report=performance_report,
        )

    @staticmethod
    def _build_signal_id(run_id: str) -> str:
        digest = hashlib.sha256(f"{run_id}::entry".encode()).hexdigest()
        return f"signal-{digest[:16]}"


class PerformanceComparator:
    """Compare one strategy report with a benchmark result."""

    def compare(
        self,
        *,
        strategy: BacktestPerformanceReport,
        benchmark: BenchmarkResult,
    ) -> BenchmarkComparison:
        benchmark_report = benchmark.performance_report

        if strategy.dataset_id != benchmark.dataset_id:
            raise ValueError("strategy and benchmark must use the same dataset")
        if strategy.starting_balance != benchmark_report.starting_balance:
            raise ValueError("strategy and benchmark must use the same starting balance")

        return_delta = strategy.total_return - benchmark_report.total_return
        outcome = ComparisonOutcome.TIE
        if return_delta > 0:
            outcome = ComparisonOutcome.STRATEGY
        elif return_delta < 0:
            outcome = ComparisonOutcome.BENCHMARK

        return BenchmarkComparison(
            strategy_run_id=strategy.run_id,
            benchmark_run_id=benchmark.run_id,
            dataset_id=strategy.dataset_id,
            strategy_return=strategy.total_return,
            benchmark_return=benchmark_report.total_return,
            return_delta=return_delta,
            net_pnl_delta=strategy.net_pnl - benchmark_report.net_pnl,
            max_drawdown_fraction_delta=(
                strategy.max_drawdown_fraction - benchmark_report.max_drawdown_fraction
            ),
            strategy_has_lower_drawdown=(
                strategy.max_drawdown_fraction < benchmark_report.max_drawdown_fraction
            ),
            outcome=outcome,
        )
