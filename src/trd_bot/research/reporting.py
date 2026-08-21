from collections.abc import Sequence
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.research.evaluation import (
    SignalEvaluation,
    SignalEvaluationReport,
    SignalOutcome,
)
from trd_bot.strategies.signals import SignalDirection


class DirectionMetrics(BaseModel):
    """Aggregated metrics for one signal direction."""

    model_config = ConfigDict(frozen=True)

    direction: SignalDirection

    evaluated_signals: int = Field(ge=0)
    correct_signals: int = Field(ge=0)
    incorrect_signals: int = Field(ge=0)
    flat_signals: int = Field(ge=0)

    hit_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    average_directional_return: Decimal | None = None
    median_directional_return: Decimal | None = None
    best_directional_return: Decimal | None = None
    worst_directional_return: Decimal | None = None

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        outcome_count = self.correct_signals + self.incorrect_signals + self.flat_signals

        if outcome_count != self.evaluated_signals:
            raise ValueError("direction outcome counts must equal evaluated signals")

        if self.evaluated_signals == 0 and self.hit_rate is not None:
            raise ValueError("empty direction metrics cannot have a hit rate")

        if self.evaluated_signals > 0 and self.hit_rate is None:
            raise ValueError("non-empty direction metrics require a hit rate")

        return self


class StrategyEvaluationSummary(BaseModel):
    """Summary of a strategy signal-evaluation report."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str
    horizon_candles: int = Field(ge=1)

    total_signals: int = Field(ge=0)
    resolved_signals: int = Field(ge=0)
    unresolved_signals: int = Field(ge=0)
    ignored_neutral_signals: int = Field(ge=0)

    overall_hit_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    average_directional_return: Decimal | None = None
    median_directional_return: Decimal | None = None
    best_directional_return: Decimal | None = None
    worst_directional_return: Decimal | None = None

    long_metrics: DirectionMetrics
    short_metrics: DirectionMetrics


class StrategyReportBuilder:
    """Build statistical summaries from signal evaluations."""

    def build(
        self,
        report: SignalEvaluationReport,
    ) -> StrategyEvaluationSummary:
        evaluations = report.evaluations

        long_metrics = self._direction_metrics(
            evaluations=evaluations,
            direction=SignalDirection.LONG,
        )

        short_metrics = self._direction_metrics(
            evaluations=evaluations,
            direction=SignalDirection.SHORT,
        )

        directional_returns = [evaluation.directional_return for evaluation in evaluations]

        return StrategyEvaluationSummary(
            dataset_id=report.dataset_id,
            horizon_candles=report.horizon_candles,
            total_signals=report.total_signals,
            resolved_signals=report.resolved_signals,
            unresolved_signals=report.unresolved_signals,
            ignored_neutral_signals=(report.ignored_neutral_signals),
            overall_hit_rate=self._hit_rate(evaluations),
            average_directional_return=self._average(directional_returns),
            median_directional_return=self._median(directional_returns),
            best_directional_return=(max(directional_returns) if directional_returns else None),
            worst_directional_return=(min(directional_returns) if directional_returns else None),
            long_metrics=long_metrics,
            short_metrics=short_metrics,
        )

    def _direction_metrics(
        self,
        *,
        evaluations: Sequence[SignalEvaluation],
        direction: SignalDirection,
    ) -> DirectionMetrics:
        selected = [evaluation for evaluation in evaluations if evaluation.direction == direction]

        directional_returns = [evaluation.directional_return for evaluation in selected]

        correct_signals = sum(
            evaluation.outcome == SignalOutcome.CORRECT for evaluation in selected
        )

        incorrect_signals = sum(
            evaluation.outcome == SignalOutcome.INCORRECT for evaluation in selected
        )

        flat_signals = sum(evaluation.outcome == SignalOutcome.FLAT for evaluation in selected)

        return DirectionMetrics(
            direction=direction,
            evaluated_signals=len(selected),
            correct_signals=correct_signals,
            incorrect_signals=incorrect_signals,
            flat_signals=flat_signals,
            hit_rate=self._hit_rate(selected),
            average_directional_return=self._average(directional_returns),
            median_directional_return=self._median(directional_returns),
            best_directional_return=(max(directional_returns) if directional_returns else None),
            worst_directional_return=(min(directional_returns) if directional_returns else None),
        )

    @staticmethod
    def _hit_rate(
        evaluations: Sequence[SignalEvaluation],
    ) -> Decimal | None:
        if not evaluations:
            return None

        correct_signals = sum(
            evaluation.outcome == SignalOutcome.CORRECT for evaluation in evaluations
        )

        return Decimal(correct_signals) / Decimal(len(evaluations))

    @staticmethod
    def _average(
        values: Sequence[Decimal],
    ) -> Decimal | None:
        if not values:
            return None

        return sum(values, start=Decimal("0")) / Decimal(len(values))

    @staticmethod
    def _median(
        values: Sequence[Decimal],
    ) -> Decimal | None:
        if not values:
            return None

        ordered_values = sorted(values)
        middle = len(ordered_values) // 2

        if len(ordered_values) % 2 == 1:
            return ordered_values[middle]

        return (ordered_values[middle - 1] + ordered_values[middle]) / Decimal("2")
