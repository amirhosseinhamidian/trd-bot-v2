from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from trd_bot.research.walk_forward import (
    WalkForwardFoldExecution,
)
from trd_bot.research.walk_forward_runs import (
    WalkForwardResearchRun,
)


class HistoricalFoldReturnDirection(StrEnum):
    """Direction of one fold's realized historical strategy return."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    FLAT = "flat"


class WalkForwardFoldStatistics(BaseModel):
    """Dashboard-ready historical metrics for one walk-forward fold."""

    model_config = ConfigDict(frozen=True)

    fold_number: int = Field(ge=1)
    total_trades: int = Field(ge=0)

    strategy_return: Decimal
    benchmark_return: Decimal
    excess_return: Decimal

    max_drawdown_fraction: Decimal = Field(ge=0)
    benchmark_max_drawdown_fraction: Decimal = Field(ge=0)

    return_direction: HistoricalFoldReturnDirection


class WalkForwardStabilityReport(BaseModel):
    """Historical fold distribution and dispersion for one stored run."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(
        pattern=(
            r"^walk-forward-execution-"
            r"[a-f0-9]{16}$"
        )
    )

    total_folds: int = Field(ge=1)

    positive_return_folds: int = Field(ge=0)
    negative_return_folds: int = Field(ge=0)
    flat_return_folds: int = Field(ge=0)

    positive_return_fraction: Decimal = Field(
        ge=0,
        le=1,
    )

    outperforming_benchmark_folds: int = Field(ge=0)
    underperforming_benchmark_folds: int = Field(ge=0)
    benchmark_ties: int = Field(ge=0)

    average_strategy_return: Decimal
    median_strategy_return: Decimal
    best_strategy_return: Decimal
    worst_strategy_return: Decimal

    strategy_return_range: Decimal = Field(ge=0)

    strategy_return_mean_absolute_deviation: Decimal = Field(ge=0)

    average_excess_return: Decimal
    median_excess_return: Decimal

    worst_max_drawdown_fraction: Decimal = Field(ge=0)

    folds: tuple[
        WalkForwardFoldStatistics,
        ...,
    ] = Field(min_length=1)

    interpretation: Literal["historical_research_only"] = "historical_research_only"

    @model_validator(mode="after")
    def validate_fold_counts(self) -> Self:
        if len(self.folds) != self.total_folds:
            raise ValueError("stability fold count does not match fold details")

        return_outcomes = (
            self.positive_return_folds + self.negative_return_folds + self.flat_return_folds
        )

        if return_outcomes != self.total_folds:
            raise ValueError("return outcome counts must equal total folds")

        benchmark_outcomes = (
            self.outperforming_benchmark_folds
            + self.underperforming_benchmark_folds
            + self.benchmark_ties
        )

        if benchmark_outcomes != self.total_folds:
            raise ValueError("benchmark outcome counts must equal total folds")

        expected_fraction = Decimal(self.positive_return_folds) / Decimal(self.total_folds)

        if self.positive_return_fraction != expected_fraction:
            raise ValueError("positive return fraction is inconsistent")

        return self


class WalkForwardStabilityAnalyzer:
    """Calculate fold-level historical stability and dispersion metrics."""

    def analyze(
        self,
        run: WalkForwardResearchRun,
    ) -> WalkForwardStabilityReport:
        folds = tuple(self._fold_statistics(fold_result) for fold_result in run.result.fold_results)

        strategy_returns = tuple(fold.strategy_return for fold in folds)

        excess_returns = tuple(fold.excess_return for fold in folds)

        average_strategy_return = self._average(strategy_returns)

        positive_return_folds = sum(
            fold.return_direction is HistoricalFoldReturnDirection.POSITIVE for fold in folds
        )

        return WalkForwardStabilityReport(
            execution_id=run.execution_id,
            total_folds=len(folds),
            positive_return_folds=(positive_return_folds),
            negative_return_folds=sum(
                fold.return_direction is HistoricalFoldReturnDirection.NEGATIVE for fold in folds
            ),
            flat_return_folds=sum(
                fold.return_direction is HistoricalFoldReturnDirection.FLAT for fold in folds
            ),
            positive_return_fraction=(Decimal(positive_return_folds) / Decimal(len(folds))),
            outperforming_benchmark_folds=sum(fold.excess_return > 0 for fold in folds),
            underperforming_benchmark_folds=sum(fold.excess_return < 0 for fold in folds),
            benchmark_ties=sum(fold.excess_return == 0 for fold in folds),
            average_strategy_return=(average_strategy_return),
            median_strategy_return=self._median(strategy_returns),
            best_strategy_return=max(strategy_returns),
            worst_strategy_return=min(strategy_returns),
            strategy_return_range=(max(strategy_returns) - min(strategy_returns)),
            strategy_return_mean_absolute_deviation=(
                self._mean_absolute_deviation(
                    strategy_returns,
                    average=average_strategy_return,
                )
            ),
            average_excess_return=self._average(excess_returns),
            median_excess_return=self._median(excess_returns),
            worst_max_drawdown_fraction=max(fold.max_drawdown_fraction for fold in folds),
            folds=folds,
        )

    @staticmethod
    def _fold_statistics(
        fold: WalkForwardFoldExecution,
    ) -> WalkForwardFoldStatistics:
        result = fold.result
        performance = result.performance_report

        benchmark_performance = result.benchmark_result.performance_report

        strategy_return = performance.total_return

        benchmark_return = benchmark_performance.total_return

        return WalkForwardFoldStatistics(
            fold_number=fold.fold_number,
            total_trades=performance.total_trades,
            strategy_return=strategy_return,
            benchmark_return=benchmark_return,
            excess_return=(strategy_return - benchmark_return),
            max_drawdown_fraction=(performance.max_drawdown_fraction),
            benchmark_max_drawdown_fraction=(benchmark_performance.max_drawdown_fraction),
            return_direction=(WalkForwardStabilityAnalyzer._return_direction(strategy_return)),
        )

    @staticmethod
    def _return_direction(
        value: Decimal,
    ) -> HistoricalFoldReturnDirection:
        if value > 0:
            return HistoricalFoldReturnDirection.POSITIVE

        if value < 0:
            return HistoricalFoldReturnDirection.NEGATIVE

        return HistoricalFoldReturnDirection.FLAT

    @staticmethod
    def _average(
        values: Sequence[Decimal],
    ) -> Decimal:
        return sum(
            values,
            start=Decimal("0"),
        ) / Decimal(len(values))

    @staticmethod
    def _median(
        values: Sequence[Decimal],
    ) -> Decimal:
        ordered = sorted(values)
        middle = len(ordered) // 2

        if len(ordered) % 2 == 1:
            return ordered[middle]

        return (ordered[middle - 1] + ordered[middle]) / Decimal("2")

    @staticmethod
    def _mean_absolute_deviation(
        values: Sequence[Decimal],
        *,
        average: Decimal,
    ) -> Decimal:
        absolute_deviations = tuple(abs(value - average) for value in values)

        return WalkForwardStabilityAnalyzer._average(absolute_deviations)
