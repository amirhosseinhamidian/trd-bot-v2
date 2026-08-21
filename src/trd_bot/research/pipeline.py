from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    ) -> None:
        if backtest_engine is None:
            from trd_bot.backtesting.engine import BacktestEngine

            backtest_engine = BacktestEngine()

        self._signal_evaluator = signal_evaluator or SignalEvaluator()
        self._report_builder = report_builder or StrategyReportBuilder()
        self._backtest_engine = backtest_engine
        self._performance_analyzer = performance_analyzer or BacktestPerformanceAnalyzer()

    def run(
        self,
        *,
        dataset: DatasetSnapshot,
        strategy: BaseStrategy,
        horizon_candles: int = 1,
        backtest_config: BacktestConfig | None = None,
    ) -> ResearchPipelineResult:
        effective_backtest_config = backtest_config or DEFAULT_RESEARCH_BACKTEST_CONFIG

        signals = strategy.generate(dataset)

        evaluation_report = self._signal_evaluator.evaluate(
            dataset=dataset,
            signals=signals,
            horizon_candles=horizon_candles,
        )

        summary = self._report_builder.build(evaluation_report)

        backtest_run_id = build_research_backtest_run_id(
            dataset_id=dataset.dataset_id,
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            config=effective_backtest_config,
        )

        backtest_events = self._backtest_engine.run(
            run_id=backtest_run_id,
            dataset=dataset,
            signals=signals,
            config=effective_backtest_config,
        )

        performance_report = self._performance_analyzer.analyze(
            run_id=backtest_run_id,
            dataset_id=dataset.dataset_id,
            events=backtest_events,
            config=effective_backtest_config,
        )

        return ResearchPipelineResult(
            dataset_id=dataset.dataset_id,
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            generated_signals=len(signals),
            signals=signals,
            evaluation_report=evaluation_report,
            summary=summary,
            backtest_run_id=backtest_run_id,
            backtest_config=effective_backtest_config,
            backtest_events=backtest_events,
            performance_report=performance_report,
        )
