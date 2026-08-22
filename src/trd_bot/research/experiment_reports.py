from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.research.acceptance import (
    ExperimentAcceptanceEvaluator,
    ExperimentAcceptancePolicy,
    ExperimentAcceptanceResult,
)
from trd_bot.research.experiments import ExperimentSummary


class HistoricalDrawdownComparison(StrEnum):
    """Relative historical drawdown of a strategy and its benchmark."""

    LOWER = "lower"
    EQUAL = "equal"
    HIGHER = "higher"


class HistoricalBenchmarkContext(BaseModel):
    """Dashboard-ready historical strategy and benchmark metrics."""

    model_config = ConfigDict(frozen=True)

    benchmark_type: Literal["buy_and_hold"]
    strategy_total_return: Decimal
    benchmark_return: Decimal
    excess_return: Decimal

    comparison_outcome: Literal[
        "strategy",
        "benchmark",
        "tie",
    ]

    strategy_max_drawdown_fraction: Decimal = Field(ge=0)
    benchmark_max_drawdown_fraction: Decimal = Field(ge=0)
    drawdown_comparison: HistoricalDrawdownComparison


class ExperimentResearchReport(BaseModel):
    """Consolidated historical experiment report for dashboard clients."""

    model_config = ConfigDict(frozen=True)

    experiment: ExperimentSummary
    benchmark_context: HistoricalBenchmarkContext
    acceptance: ExperimentAcceptanceResult

    passed_checks: int = Field(ge=0)
    failed_checks: int = Field(ge=0)

    interpretation: Literal["historical_research_only"] = "historical_research_only"

    @model_validator(mode="after")
    def validate_check_counts(self) -> Self:
        if self.passed_checks + self.failed_checks != len(self.acceptance.checks):
            raise ValueError("report check counts must match acceptance checks")

        return self


class ExperimentResearchReportBuilder:
    """Build one consolidated historical report from an experiment summary."""

    def __init__(
        self,
        *,
        acceptance_evaluator: (ExperimentAcceptanceEvaluator | None) = None,
    ) -> None:
        self._acceptance_evaluator = acceptance_evaluator or ExperimentAcceptanceEvaluator()

    def build(
        self,
        *,
        experiment: ExperimentSummary,
        policy: ExperimentAcceptancePolicy,
    ) -> ExperimentResearchReport:
        acceptance = self._acceptance_evaluator.evaluate(
            experiment=experiment,
            policy=policy,
        )

        passed_checks = sum(check.passed for check in acceptance.checks)

        return ExperimentResearchReport(
            experiment=experiment,
            benchmark_context=HistoricalBenchmarkContext(
                benchmark_type=experiment.benchmark_type,
                strategy_total_return=(experiment.total_return),
                benchmark_return=(experiment.benchmark_return),
                excess_return=experiment.excess_return,
                comparison_outcome=(experiment.comparison_outcome),
                strategy_max_drawdown_fraction=(experiment.max_drawdown_fraction),
                benchmark_max_drawdown_fraction=(experiment.benchmark_max_drawdown_fraction),
                drawdown_comparison=(self._drawdown_comparison(experiment)),
            ),
            acceptance=acceptance,
            passed_checks=passed_checks,
            failed_checks=(len(acceptance.checks) - passed_checks),
        )

    @staticmethod
    def _drawdown_comparison(
        experiment: ExperimentSummary,
    ) -> HistoricalDrawdownComparison:
        strategy_drawdown = experiment.max_drawdown_fraction
        benchmark_drawdown = experiment.benchmark_max_drawdown_fraction

        if strategy_drawdown < benchmark_drawdown:
            return HistoricalDrawdownComparison.LOWER

        if strategy_drawdown > benchmark_drawdown:
            return HistoricalDrawdownComparison.HIGHER

        return HistoricalDrawdownComparison.EQUAL
