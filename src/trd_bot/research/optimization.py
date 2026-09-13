from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from itertools import product
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.experiments import ExperimentParameter, ExperimentSummary
from trd_bot.strategies import (
    StrategyMetadata,
    StrategyParameterKind,
    StrategyParameterMetadata,
    StrategyParameterValue,
    StrategyRegistry,
    build_default_strategy_registry,
)

MAX_OPTIMIZATION_TRIALS = 100


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


class OptimizationParameterGrid(BaseModel):
    """Explicit candidate values for one strategy parameter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    values: tuple[str, ...] = Field(min_length=1, max_length=20)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("optimization parameter name cannot be empty")
        return normalized

    @field_validator("values")
    @classmethod
    def normalize_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)

        if any(not value for value in normalized):
            raise ValueError("optimization parameter values cannot be empty")

        return normalized


class OptimizationTrial(BaseModel):
    """One valid deterministic parameter combination."""

    model_config = ConfigDict(frozen=True)

    trial_number: int = Field(ge=1)
    parameters: tuple[ExperimentParameter, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def parameter_names_must_be_unique(self) -> Self:
        names = tuple(parameter.name for parameter in self.parameters)
        if len(names) != len(set(names)):
            raise ValueError("optimization trial parameter names must be unique")
        return self


class OptimizationPlan(BaseModel):
    """Validated bounded grid of historical research trials."""

    model_config = ConfigDict(frozen=True)

    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=50)
    objective: ExperimentComparisonMetric
    requested_combinations: int = Field(ge=1)
    skipped_combinations: int = Field(ge=0)
    total_trials: int = Field(ge=1, le=MAX_OPTIMIZATION_TRIALS)
    trials: tuple[OptimizationTrial, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def counts_must_match_trials(self) -> Self:
        if self.total_trials != len(self.trials):
            raise ValueError("optimization trial count does not match trials")

        if self.requested_combinations != self.total_trials + self.skipped_combinations:
            raise ValueError("optimization combination counts are inconsistent")

        for expected_number, trial in enumerate(self.trials, start=1):
            if trial.trial_number != expected_number:
                raise ValueError("optimization trial numbers must be continuous")

        return self


class OptimizationPlanner:
    """Expand an explicit strategy parameter grid into valid historical trials."""

    def __init__(
        self,
        *,
        strategy_registry: StrategyRegistry | None = None,
        max_trials: int = MAX_OPTIMIZATION_TRIALS,
    ) -> None:
        if max_trials <= 0:
            raise ValueError("optimization max trials must be greater than zero")

        self._strategy_registry = strategy_registry or build_default_strategy_registry()
        self._max_trials = max_trials

    def plan(
        self,
        *,
        strategy_name: str,
        strategy_version: str,
        parameter_grid: Sequence[OptimizationParameterGrid],
        objective: ExperimentComparisonMetric = ExperimentComparisonMetric.EXCESS_RETURN,
    ) -> OptimizationPlan:
        definition = self._strategy_registry.require(
            name=strategy_name,
            version=strategy_version,
        )

        metadata = definition.metadata
        if metadata is None:
            raise ValueError("strategy does not expose optimization metadata")

        grids = tuple(parameter_grid)
        self._require_exact_parameter_names(
            metadata=metadata,
            grids=grids,
        )

        canonical_values: list[
            tuple[StrategyParameterMetadata, tuple[tuple[str, StrategyParameterValue], ...]]
        ] = []
        requested_combinations = 1

        grids_by_name = {grid.name: grid for grid in grids}

        for parameter in metadata.parameters:
            grid = grids_by_name[parameter.name]
            parsed_values = self._parse_grid_values(
                parameter=parameter,
                values=grid.values,
            )
            canonical_values.append((parameter, parsed_values))
            requested_combinations *= len(parsed_values)

            if requested_combinations > self._max_trials:
                raise ValueError(
                    f"optimization parameter grid exceeds maximum of {self._max_trials} trials"
                )

        trials: list[OptimizationTrial] = []
        skipped_combinations = 0

        value_groups = tuple(values for _, values in canonical_values)

        for combination in product(*value_groups):
            typed_parameters: dict[str, StrategyParameterValue] = {}
            experiment_parameters: list[ExperimentParameter] = []

            for (parameter, _), (canonical_value, typed_value) in zip(
                canonical_values,
                combination,
                strict=True,
            ):
                typed_parameters[parameter.name] = typed_value
                experiment_parameters.append(
                    ExperimentParameter(
                        name=parameter.name,
                        value=canonical_value,
                    )
                )

            try:
                self._strategy_registry.create(
                    name=strategy_name,
                    version=strategy_version,
                    parameters=typed_parameters,
                )
            except ValueError:
                skipped_combinations += 1
                continue

            trials.append(
                OptimizationTrial(
                    trial_number=len(trials) + 1,
                    parameters=tuple(experiment_parameters),
                )
            )

        if not trials:
            raise ValueError("optimization parameter grid contains no valid strategy trials")

        return OptimizationPlan(
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            objective=objective,
            requested_combinations=requested_combinations,
            skipped_combinations=skipped_combinations,
            total_trials=len(trials),
            trials=tuple(trials),
        )

    @staticmethod
    def _require_exact_parameter_names(
        *,
        metadata: StrategyMetadata,
        grids: tuple[OptimizationParameterGrid, ...],
    ) -> None:
        names = tuple(grid.name for grid in grids)
        if len(names) != len(set(names)):
            raise ValueError("optimization parameter names must be unique")

        expected = {parameter.name for parameter in metadata.parameters}
        received = set(names)

        missing = sorted(expected - received)
        if missing:
            raise ValueError(f"missing optimization parameter: {missing[0]}")

        unexpected = sorted(received - expected)
        if unexpected:
            raise ValueError(f"unexpected optimization parameter: {unexpected[0]}")

    def _parse_grid_values(
        self,
        *,
        parameter: StrategyParameterMetadata,
        values: tuple[str, ...],
    ) -> tuple[tuple[str, StrategyParameterValue], ...]:
        parsed = tuple(
            self._parse_parameter_value(
                parameter=parameter,
                value=value,
            )
            for value in values
        )

        canonical = tuple(value for value, _ in parsed)
        if len(canonical) != len(set(canonical)):
            raise ValueError(f"optimization parameter {parameter.name!r} contains duplicate values")

        return parsed

    @staticmethod
    def _parse_parameter_value(
        *,
        parameter: StrategyParameterMetadata,
        value: str,
    ) -> tuple[str, StrategyParameterValue]:
        typed_value: StrategyParameterValue
        numeric_value: Decimal

        if parameter.kind is StrategyParameterKind.INTEGER:
            try:
                typed_value = int(value)
            except ValueError as error:
                raise ValueError(
                    f"optimization parameter {parameter.name!r} must contain integer values"
                ) from error

            canonical_value = str(typed_value)
            numeric_value = Decimal(typed_value)

        else:
            try:
                typed_decimal = Decimal(value)
            except InvalidOperation as error:
                raise ValueError(
                    f"optimization parameter {parameter.name!r} must contain decimal values"
                ) from error

            if not typed_decimal.is_finite():
                raise ValueError(
                    f"optimization parameter {parameter.name!r} must contain finite values"
                )

            typed_value = typed_decimal
            canonical_value = _canonical_decimal(typed_decimal)
            numeric_value = typed_decimal

        OptimizationPlanner._validate_bounds(
            parameter=parameter,
            value=numeric_value,
        )

        return canonical_value, typed_value

    @staticmethod
    def _validate_bounds(
        *,
        parameter: StrategyParameterMetadata,
        value: Decimal,
    ) -> None:
        if parameter.minimum is not None:
            minimum = Decimal(parameter.minimum)
            invalid_minimum = value <= minimum if parameter.minimum_exclusive else value < minimum
            if invalid_minimum:
                raise ValueError(f"optimization parameter {parameter.name!r} is below its minimum")

        if parameter.maximum is not None:
            maximum = Decimal(parameter.maximum)
            invalid_maximum = value >= maximum if parameter.maximum_exclusive else value > maximum
            if invalid_maximum:
                raise ValueError(f"optimization parameter {parameter.name!r} is above its maximum")


class OptimizationRankingEntry(BaseModel):
    """One successful experiment ranked by the selected historical objective."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=1)
    metric_value: Decimal
    experiment: ExperimentSummary


class OptimizationRankingResult(BaseModel):
    """Deterministic ranking of successful optimization experiments."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str
    strategy_name: str
    strategy_version: str
    horizon_candles: int = Field(ge=1)
    objective: ExperimentComparisonMetric
    ranking_direction: Literal["higher_is_better", "lower_is_better"]
    ranked_experiments: int = Field(ge=1)
    best_experiment_id: str
    entries: tuple[OptimizationRankingEntry, ...] = Field(min_length=1)
    interpretation: Literal["historical_research_only"] = "historical_research_only"


class OptimizationScorer:
    """Rank comparable stored experiments without the comparison UI's ten-item cap."""

    def rank(
        self,
        *,
        experiments: Sequence[ExperimentSummary],
        objective: ExperimentComparisonMetric,
    ) -> OptimizationRankingResult:
        selected = tuple(experiments)
        self._validate_comparable(selected)

        ordered = tuple(
            sorted(
                selected,
                key=lambda experiment: self._sort_key(
                    experiment=experiment,
                    objective=objective,
                ),
            )
        )

        entries = tuple(
            OptimizationRankingEntry(
                position=position,
                metric_value=self.metric_value(
                    experiment=experiment,
                    objective=objective,
                ),
                experiment=experiment,
            )
            for position, experiment in enumerate(ordered, start=1)
        )

        first = ordered[0]

        return OptimizationRankingResult(
            dataset_id=first.dataset_id,
            strategy_name=first.strategy_name,
            strategy_version=first.strategy_version,
            horizon_candles=first.horizon_candles,
            objective=objective,
            ranking_direction=self.ranking_direction(objective),
            ranked_experiments=len(ordered),
            best_experiment_id=first.experiment_id,
            entries=entries,
        )

    @staticmethod
    def metric_value(
        *,
        experiment: ExperimentSummary,
        objective: ExperimentComparisonMetric,
    ) -> Decimal:
        if objective is ExperimentComparisonMetric.TOTAL_RETURN:
            return experiment.total_return

        if objective is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return experiment.max_drawdown_fraction

        return experiment.excess_return

    @staticmethod
    def ranking_direction(
        objective: ExperimentComparisonMetric,
    ) -> Literal["higher_is_better", "lower_is_better"]:
        if objective is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return "lower_is_better"
        return "higher_is_better"

    def _sort_key(
        self,
        *,
        experiment: ExperimentSummary,
        objective: ExperimentComparisonMetric,
    ) -> tuple[Decimal, str]:
        value = self.metric_value(
            experiment=experiment,
            objective=objective,
        )

        if objective is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return value, experiment.experiment_id

        return -value, experiment.experiment_id

    @staticmethod
    def _validate_comparable(experiments: tuple[ExperimentSummary, ...]) -> None:
        if not experiments:
            raise ValueError("at least one optimization experiment is required")

        experiment_ids = {experiment.experiment_id for experiment in experiments}
        if len(experiment_ids) != len(experiments):
            raise ValueError("optimization experiment IDs must be unique")

        identities = {
            (
                experiment.dataset_id,
                experiment.strategy_name,
                experiment.strategy_version,
                experiment.horizon_candles,
            )
            for experiment in experiments
        }
        if len(identities) != 1:
            raise ValueError(
                "optimization experiments must share dataset, strategy version, and horizon"
            )
