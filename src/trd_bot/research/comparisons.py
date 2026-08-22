from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.research.experiments import ExperimentSummary

ExperimentId = Annotated[
    str,
    Field(pattern=r"^experiment-[a-f0-9]{16}$"),
]


class ExperimentComparisonMetric(StrEnum):
    """Metrics supported by historical experiment comparison."""

    EXCESS_RETURN = "excess_return"
    TOTAL_RETURN = "total_return"
    MAX_DRAWDOWN_FRACTION = "max_drawdown_fraction"


class ExperimentComparisonRequest(BaseModel):
    """Selection and metric for one historical experiment comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_ids: tuple[ExperimentId, ...] = Field(
        min_length=2,
        max_length=10,
    )
    metric: ExperimentComparisonMetric = ExperimentComparisonMetric.EXCESS_RETURN

    @model_validator(mode="after")
    def experiment_ids_must_be_unique(self) -> Self:
        if len(self.experiment_ids) != len(set(self.experiment_ids)):
            raise ValueError("experiment IDs must be unique")

        return self


class ExperimentComparisonEntry(BaseModel):
    """One ranked experiment and its selected historical metric."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=1)
    metric_value: Decimal
    experiment: ExperimentSummary


class ExperimentComparisonResult(BaseModel):
    """Ranked historical results for comparable stored experiments."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str
    horizon_candles: int = Field(ge=1)
    metric: ExperimentComparisonMetric
    ranking_direction: Literal["higher_is_better", "lower_is_better"]
    compared_experiments: int = Field(ge=2, le=10)
    best_experiment_id: str
    entries: tuple[ExperimentComparisonEntry, ...]
    interpretation: Literal["historical_research_only"] = "historical_research_only"


class ExperimentComparator:
    """Compare compatible experiment summaries using one historical metric."""

    def compare(
        self,
        *,
        experiments: Sequence[ExperimentSummary],
        metric: ExperimentComparisonMetric,
    ) -> ExperimentComparisonResult:
        selected = tuple(experiments)
        self._validate(selected)

        ordered = tuple(
            sorted(
                selected,
                key=lambda experiment: self._sort_key(
                    experiment=experiment,
                    metric=metric,
                ),
            )
        )

        entries = tuple(
            ExperimentComparisonEntry(
                position=position,
                metric_value=self._metric_value(
                    experiment=experiment,
                    metric=metric,
                ),
                experiment=experiment,
            )
            for position, experiment in enumerate(ordered, start=1)
        )

        first = ordered[0]

        return ExperimentComparisonResult(
            dataset_id=first.dataset_id,
            horizon_candles=first.horizon_candles,
            metric=metric,
            ranking_direction=self._ranking_direction(metric),
            compared_experiments=len(ordered),
            best_experiment_id=first.experiment_id,
            entries=entries,
        )

    @staticmethod
    def _validate(experiments: tuple[ExperimentSummary, ...]) -> None:
        if len(experiments) < 2:
            raise ValueError("at least two experiments are required")

        if len(experiments) > 10:
            raise ValueError("at most ten experiments can be compared")

        experiment_ids = {experiment.experiment_id for experiment in experiments}

        if len(experiment_ids) != len(experiments):
            raise ValueError("experiment IDs must be unique")

        dataset_ids = {experiment.dataset_id for experiment in experiments}

        if len(dataset_ids) != 1:
            raise ValueError("experiments must use the same dataset")

        horizons = {experiment.horizon_candles for experiment in experiments}

        if len(horizons) != 1:
            raise ValueError("experiments must use the same evaluation horizon")

    def _sort_key(
        self,
        *,
        experiment: ExperimentSummary,
        metric: ExperimentComparisonMetric,
    ) -> tuple[Decimal, str]:
        value = self._metric_value(
            experiment=experiment,
            metric=metric,
        )

        if metric is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return value, experiment.experiment_id

        return -value, experiment.experiment_id

    @staticmethod
    def _metric_value(
        *,
        experiment: ExperimentSummary,
        metric: ExperimentComparisonMetric,
    ) -> Decimal:
        if metric is ExperimentComparisonMetric.TOTAL_RETURN:
            return experiment.total_return

        if metric is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return experiment.max_drawdown_fraction

        return experiment.excess_return

    @staticmethod
    def _ranking_direction(
        metric: ExperimentComparisonMetric,
    ) -> Literal["higher_is_better", "lower_is_better"]:
        if metric is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return "lower_is_better"

        return "higher_is_better"
