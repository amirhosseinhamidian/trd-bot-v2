from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

        return self


class ResearchPipeline:
    """Run a complete offline strategy research workflow."""

    def __init__(
        self,
        *,
        signal_evaluator: SignalEvaluator | None = None,
        report_builder: StrategyReportBuilder | None = None,
    ) -> None:
        self._signal_evaluator = signal_evaluator or SignalEvaluator()
        self._report_builder = report_builder or StrategyReportBuilder()

    def run(
        self,
        *,
        dataset: DatasetSnapshot,
        strategy: BaseStrategy,
        horizon_candles: int = 1,
    ) -> ResearchPipelineResult:
        signals = strategy.generate(dataset)

        evaluation_report = self._signal_evaluator.evaluate(
            dataset=dataset,
            signals=signals,
            horizon_candles=horizon_candles,
        )

        summary = self._report_builder.build(evaluation_report)

        return ResearchPipelineResult(
            dataset_id=dataset.dataset_id,
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            generated_signals=len(signals),
            signals=signals,
            evaluation_report=evaluation_report,
            summary=summary,
        )
