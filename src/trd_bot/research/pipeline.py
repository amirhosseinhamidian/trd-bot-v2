from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.backtesting.benchmarks import (
    BenchmarkComparison,
    BenchmarkResult,
    BuyAndHoldBenchmark,
    PerformanceComparator,
)
from trd_bot.backtesting.models import BacktestConfig, BacktestEvent
from trd_bot.backtesting.performance import (
    BacktestPerformanceAnalyzer,
    BacktestPerformanceReport,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.evaluation import (
    SignalEvaluationReport,
    SignalEvaluator,
)
from trd_bot.research.reporting import (
    StrategyEvaluationSummary,
    StrategyReportBuilder,
)
from trd_bot.strategies.base import BaseStrategy
from trd_bot.strategies.signals import StrategySignal

if TYPE_CHECKING:
    from trd_bot.backtesting.engine import BacktestEngine


DEFAULT_RESEARCH_BACKTEST_CONFIG = BacktestConfig(
    starting_balance=Decimal("10000"),
    allocation_fraction=Decimal("0.10"),
    fee_rate=Decimal("0.001"),
    slippage_rate=Decimal("0.0005"),
)


def build_research_backtest_run_id(
    *,
    dataset_id: str,
    strategy_name: str,
    strategy_version: str,
    config: BacktestConfig,
    signal_ids: Sequence[str] = (),
) -> str:
    """Build a deterministic ID for one research backtest configuration."""

    config_payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )

    identity = "::".join(
        [
            dataset_id,
            strategy_name,
            strategy_version,
            config_payload,
            "::".join(signal_ids),
        ]
    )

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    return f"backtest-{digest[:16]}"


class ResearchPipelineResult(BaseModel):
    """Complete result of one research pipeline run."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str
    strategy_name: str
    strategy_version: str

    generated_signals: int = Field(ge=0)

    signals: tuple[StrategySignal, ...]
    evaluation_report: SignalEvaluationReport
    summary: StrategyEvaluationSummary

    backtest_run_id: str = Field(pattern=r"^backtest-[a-f0-9]{16}$")
    backtest_config: BacktestConfig
    backtest_events: tuple[BacktestEvent, ...]
    performance_report: BacktestPerformanceReport
    benchmark_result: BenchmarkResult
    benchmark_comparison: BenchmarkComparison

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.generated_signals != len(self.signals):
            raise ValueError("generated signal count does not match signals")

        if self.evaluation_report.dataset_id != self.dataset_id:
            raise ValueError("evaluation report dataset does not match")

        if self.summary.dataset_id != self.dataset_id:
            raise ValueError("summary dataset does not match")

        if self.evaluation_report.total_signals != self.generated_signals:
            raise ValueError("evaluation signal count does not match")

        if self.performance_report.run_id != self.backtest_run_id:
            raise ValueError("performance report run does not match")

        if self.performance_report.dataset_id != self.dataset_id:
            raise ValueError("performance report dataset does not match")

        if self.performance_report.starting_balance != self.backtest_config.starting_balance:
            raise ValueError("performance report balance does not match backtest config")

        if self.benchmark_result.dataset_id != self.dataset_id:
            raise ValueError("benchmark dataset does not match pipeline dataset")

        if self.benchmark_result.config != self.backtest_config:
            raise ValueError("benchmark config does not match backtest config")

        if self.benchmark_comparison.dataset_id != self.dataset_id:
            raise ValueError("benchmark comparison dataset does not match")

        if self.benchmark_comparison.strategy_run_id != self.backtest_run_id:
            raise ValueError("benchmark comparison strategy run does not match")

        if self.benchmark_comparison.benchmark_run_id != self.benchmark_result.run_id:
            raise ValueError("benchmark comparison benchmark run does not match")

        if self.benchmark_comparison.strategy_return != self.performance_report.total_return:
            raise ValueError("benchmark comparison strategy return does not match")

        benchmark_return = self.benchmark_result.performance_report.total_return
        if self.benchmark_comparison.benchmark_return != benchmark_return:
            raise ValueError("benchmark comparison benchmark return does not match")

        return self


class ResearchPipeline:
    """Run a complete offline strategy research workflow."""

    def __init__(
        self,
        *,
        signal_evaluator: SignalEvaluator | None = None,
        report_builder: StrategyReportBuilder | None = None,
        backtest_engine: BacktestEngine | None = None,
        performance_analyzer: BacktestPerformanceAnalyzer | None = None,
        benchmark_runner: BuyAndHoldBenchmark | None = None,
        performance_comparator: PerformanceComparator | None = None,
    ) -> None:
        if backtest_engine is None:
            from trd_bot.backtesting.engine import BacktestEngine

            backtest_engine = BacktestEngine()

        self._signal_evaluator = signal_evaluator or SignalEvaluator()
        self._report_builder = report_builder or StrategyReportBuilder()
        self._backtest_engine = backtest_engine
        self._performance_analyzer = performance_analyzer or BacktestPerformanceAnalyzer()
        self._benchmark_runner = benchmark_runner or BuyAndHoldBenchmark()
        self._performance_comparator = performance_comparator or PerformanceComparator()

    def run(
        self,
        *,
        dataset: DatasetSnapshot,
        strategy: BaseStrategy,
        horizon_candles: int = 1,
        backtest_config: BacktestConfig | None = None,
    ) -> ResearchPipelineResult:
        signals = strategy.generate(dataset)

        return self.run_with_signals(
            dataset=dataset,
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            signals=signals,
            horizon_candles=horizon_candles,
            backtest_config=backtest_config,
        )

    def run_with_signals(
        self,
        *,
        dataset: DatasetSnapshot,
        strategy_name: str,
        strategy_version: str,
        signals: Sequence[StrategySignal],
        horizon_candles: int = 1,
        backtest_config: BacktestConfig | None = None,
    ) -> ResearchPipelineResult:
        """Run the research workflow with chronological precomputed signals."""

        effective_backtest_config = backtest_config or DEFAULT_RESEARCH_BACKTEST_CONFIG
        ordered_signals = tuple(signals)
        self._validate_precomputed_signals(
            signals=ordered_signals,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
        )

        evaluation_report = self._signal_evaluator.evaluate(
            dataset=dataset,
            signals=ordered_signals,
            horizon_candles=horizon_candles,
        )

        summary = self._report_builder.build(evaluation_report)

        backtest_run_id = build_research_backtest_run_id(
            dataset_id=dataset.dataset_id,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            config=effective_backtest_config,
            signal_ids=tuple(signal.signal_id for signal in ordered_signals),
        )

        backtest_events = self._backtest_engine.run(
            run_id=backtest_run_id,
            dataset=dataset,
            signals=ordered_signals,
            config=effective_backtest_config,
        )

        performance_report = self._performance_analyzer.analyze(
            run_id=backtest_run_id,
            dataset_id=dataset.dataset_id,
            events=backtest_events,
            config=effective_backtest_config,
        )

        benchmark_result = self._benchmark_runner.run(
            dataset=dataset,
            config=effective_backtest_config,
        )

        benchmark_comparison = self._performance_comparator.compare(
            strategy=performance_report,
            benchmark=benchmark_result,
        )

        return ResearchPipelineResult(
            dataset_id=dataset.dataset_id,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            generated_signals=len(ordered_signals),
            signals=ordered_signals,
            evaluation_report=evaluation_report,
            summary=summary,
            backtest_run_id=backtest_run_id,
            backtest_config=effective_backtest_config,
            backtest_events=backtest_events,
            performance_report=performance_report,
            benchmark_result=benchmark_result,
            benchmark_comparison=benchmark_comparison,
        )

    @staticmethod
    def _validate_precomputed_signals(
        *,
        signals: tuple[StrategySignal, ...],
        strategy_name: str,
        strategy_version: str,
    ) -> None:
        if not strategy_name.strip():
            raise ValueError("strategy name cannot be empty")
        if not strategy_version.strip():
            raise ValueError("strategy version cannot be empty")

        signal_ids: set[str] = set()
        previous_close_time = None

        for signal in signals:
            if signal.strategy_name != strategy_name:
                raise ValueError("signal strategy name does not match")
            if signal.strategy_version != strategy_version:
                raise ValueError("signal strategy version does not match")
            if signal.signal_id in signal_ids:
                raise ValueError("precomputed signals cannot contain duplicates")
            if previous_close_time is not None and signal.candle_close_time < previous_close_time:
                raise ValueError("precomputed signals must be chronological")

            signal_ids.add(signal.signal_id)
            previous_close_time = signal.candle_close_time
