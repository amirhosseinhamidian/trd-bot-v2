from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.backtesting.benchmarks import BenchmarkType
from trd_bot.backtesting.performance import (
    BacktestPerformanceReport,
    EquityPoint,
)
from trd_bot.research.experiments import ResearchExperiment


class HistoricalPerformanceSeries(BaseModel):
    """Realized historical equity series for one simulated run."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1, max_length=200)
    starting_balance: str
    ending_balance: str
    total_return: str
    max_drawdown_fraction: str
    points: tuple[EquityPoint, ...]

    @model_validator(mode="after")
    def validate_series(self) -> Self:
        if self.points and str(self.points[-1].balance) != self.ending_balance:
            raise ValueError("final performance-series point must match ending balance")

        return self

    @classmethod
    def from_report(
        cls,
        report: BacktestPerformanceReport,
    ) -> Self:
        return cls(
            run_id=report.run_id,
            starting_balance=str(report.starting_balance),
            ending_balance=str(report.ending_balance),
            total_return=str(report.total_return),
            max_drawdown_fraction=str(report.max_drawdown_fraction),
            points=report.equity_curve,
        )


class ExperimentPerformanceSeries(BaseModel):
    """Dashboard-ready historical series for one stored experiment."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str
    dataset_id: str
    benchmark_type: BenchmarkType
    strategy: HistoricalPerformanceSeries
    benchmark: HistoricalPerformanceSeries
    interpretation: Literal["historical_research_only"] = "historical_research_only"


class ExperimentPerformanceSeriesBuilder:
    """Build chart data from an immutable stored experiment."""

    def build(
        self,
        experiment: ResearchExperiment,
    ) -> ExperimentPerformanceSeries:
        benchmark_result = experiment.result.benchmark_result

        return ExperimentPerformanceSeries(
            experiment_id=experiment.experiment_id,
            dataset_id=experiment.dataset_id,
            benchmark_type=benchmark_result.benchmark_type,
            strategy=HistoricalPerformanceSeries.from_report(experiment.result.performance_report),
            benchmark=HistoricalPerformanceSeries.from_report(benchmark_result.performance_report),
        )
