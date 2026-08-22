import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Protocol, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from trd_bot.research.pipeline import ResearchPipelineResult


class ExperimentParameter(BaseModel):
    """A reproducible strategy experiment parameter."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=200)


class ResearchExperiment(BaseModel):
    """Immutable record of one research experiment."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str = Field(
        pattern=r"^experiment-[a-f0-9]{16}$",
    )

    created_at: datetime
    dataset_id: str

    strategy_name: str
    strategy_version: str
    horizon_candles: int = Field(ge=1)

    parameters: tuple[ExperimentParameter, ...]
    result: ResearchPipelineResult

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created time must include timezone information")

        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_experiment(self) -> Self:
        parameter_names = [parameter.name for parameter in self.parameters]

        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("experiment parameter names must be unique")

        if self.result.dataset_id != self.dataset_id:
            raise ValueError("experiment dataset does not match result")

        if self.result.strategy_name != self.strategy_name:
            raise ValueError("experiment strategy does not match result")

        if self.result.strategy_version != self.strategy_version:
            raise ValueError("experiment strategy version does not match result")

        if self.result.evaluation_report.horizon_candles != self.horizon_candles:
            raise ValueError("experiment horizon does not match result")

        return self


class ExperimentSummary(BaseModel):
    """Lightweight representation used in experiment lists."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str
    created_at: datetime
    dataset_id: str
    strategy_name: str
    strategy_version: str
    horizon_candles: int = Field(ge=1)
    parameters: tuple[ExperimentParameter, ...]
    generated_signals: int = Field(ge=0)
    total_trades: int = Field(ge=0)
    net_pnl: Decimal
    total_return: Decimal
    win_rate: Decimal | None = Field(default=None, ge=0, le=1)
    max_drawdown_fraction: Decimal = Field(ge=0)
    profit_factor: Decimal | None = Field(default=None, ge=0)
    benchmark_type: Literal["buy_and_hold"]
    benchmark_return: Decimal
    excess_return: Decimal
    benchmark_max_drawdown_fraction: Decimal = Field(ge=0)
    max_drawdown_fraction_delta: Decimal
    strategy_has_lower_drawdown: bool
    comparison_outcome: Literal["strategy", "benchmark", "tie"]

    @classmethod
    def from_experiment(
        cls,
        experiment: ResearchExperiment,
    ) -> Self:
        return cls(
            experiment_id=experiment.experiment_id,
            created_at=experiment.created_at,
            dataset_id=experiment.dataset_id,
            strategy_name=experiment.strategy_name,
            strategy_version=experiment.strategy_version,
            horizon_candles=experiment.horizon_candles,
            parameters=experiment.parameters,
            generated_signals=experiment.result.generated_signals,
            total_trades=experiment.result.performance_report.total_trades,
            net_pnl=experiment.result.performance_report.net_pnl,
            total_return=experiment.result.performance_report.total_return,
            win_rate=experiment.result.performance_report.win_rate,
            max_drawdown_fraction=(experiment.result.performance_report.max_drawdown_fraction),
            profit_factor=experiment.result.performance_report.profit_factor,
            benchmark_type=experiment.result.benchmark_result.benchmark_type.value,
            benchmark_return=(experiment.result.benchmark_result.performance_report.total_return),
            excess_return=experiment.result.benchmark_comparison.return_delta,
            benchmark_max_drawdown_fraction=(
                experiment.result.benchmark_result.performance_report.max_drawdown_fraction
            ),
            max_drawdown_fraction_delta=(
                experiment.result.benchmark_comparison.max_drawdown_fraction_delta
            ),
            strategy_has_lower_drawdown=(
                experiment.result.benchmark_comparison.strategy_has_lower_drawdown
            ),
            comparison_outcome=experiment.result.benchmark_comparison.outcome.value,
        )


class ExperimentSortField(StrEnum):
    """Supported experiment catalog sort fields."""

    CREATED_AT = "created_at"
    HORIZON_CANDLES = "horizon_candles"


class ExperimentSortDirection(StrEnum):
    """Supported experiment catalog sort directions."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class ExperimentCatalogQuery(BaseModel):
    """Normalized filters and ordering for stored experiments."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    dataset_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    strategy_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    strategy_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    horizon_candles: int | None = Field(
        default=None,
        ge=1,
    )

    sort_by: ExperimentSortField = ExperimentSortField.CREATED_AT

    sort_direction: ExperimentSortDirection = ExperimentSortDirection.ASCENDING

    @field_validator(
        "dataset_id",
        "strategy_name",
        "strategy_version",
        mode="before",
    )
    @classmethod
    def normalize_text_filter(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            return value.strip()

        return value


def build_experiment_id(
    *,
    dataset_id: str,
    strategy_name: str,
    strategy_version: str,
    horizon_candles: int,
    parameters: Sequence[ExperimentParameter],
) -> str:
    """Build a deterministic experiment identifier."""

    ordered_parameters = sorted(
        parameters,
        key=lambda parameter: (
            parameter.name,
            parameter.value,
        ),
    )

    parameter_identity = "::".join(
        f"{parameter.name}={parameter.value}" for parameter in ordered_parameters
    )

    identity = "::".join(
        [
            dataset_id,
            strategy_name,
            strategy_version,
            str(horizon_candles),
            parameter_identity,
        ]
    )

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    return f"experiment-{digest[:16]}"


class ExperimentBuilder:
    """Build immutable experiment records."""

    def build(
        self,
        *,
        result: ResearchPipelineResult,
        parameters: Sequence[ExperimentParameter],
        created_at: datetime | None = None,
    ) -> ResearchExperiment:
        ordered_parameters = tuple(
            sorted(
                parameters,
                key=lambda parameter: (
                    parameter.name,
                    parameter.value,
                ),
            )
        )

        experiment_id = build_experiment_id(
            dataset_id=result.dataset_id,
            strategy_name=result.strategy_name,
            strategy_version=result.strategy_version,
            horizon_candles=(result.evaluation_report.horizon_candles),
            parameters=ordered_parameters,
        )

        return ResearchExperiment(
            experiment_id=experiment_id,
            created_at=created_at or datetime.now(UTC),
            dataset_id=result.dataset_id,
            strategy_name=result.strategy_name,
            strategy_version=result.strategy_version,
            horizon_candles=(result.evaluation_report.horizon_candles),
            parameters=ordered_parameters,
            result=result,
        )


class ExperimentRegistry(Protocol):
    """Persistence contract for standard research experiments."""

    def save(self, experiment: ResearchExperiment) -> ResearchExperiment: ...

    def get(self, experiment_id: str) -> ResearchExperiment | None: ...

    def count(self) -> int: ...

    def count_matching(
        self,
        query: ExperimentCatalogQuery,
    ) -> int: ...

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[ResearchExperiment, ...]: ...

    def search_page(
        self,
        *,
        query: ExperimentCatalogQuery,
        limit: int,
        offset: int,
    ) -> tuple[ResearchExperiment, ...]: ...


class InMemoryExperimentRegistry:
    """Store research experiments in memory."""

    def __init__(self) -> None:
        self._experiments: dict[
            str,
            ResearchExperiment,
        ] = {}

    def save(
        self,
        experiment: ResearchExperiment,
    ) -> ResearchExperiment:
        existing = self._experiments.get(experiment.experiment_id)

        if existing is not None:
            if not self._same_experiment(
                first=existing,
                second=experiment,
            ):
                raise ValueError("experiment ID already exists with different content")

            return existing

        self._experiments[experiment.experiment_id] = experiment

        return experiment

    def get(
        self,
        experiment_id: str,
    ) -> ResearchExperiment | None:
        return self._experiments.get(experiment_id)

    def list_all(self) -> tuple[ResearchExperiment, ...]:
        return tuple(
            sorted(
                self._experiments.values(),
                key=lambda experiment: (
                    experiment.created_at,
                    experiment.experiment_id,
                ),
            )
        )

    def count(self) -> int:
        """Return the number of stored experiments."""

        return len(self._experiments)

    def count_matching(
        self,
        query: ExperimentCatalogQuery,
    ) -> int:
        return len(self._filter(query))

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[ResearchExperiment, ...]:
        """Return a validated slice of stored experiments."""

        return self.search_page(
            query=ExperimentCatalogQuery(),
            limit=limit,
            offset=offset,
        )

    def search_page(
        self,
        *,
        query: ExperimentCatalogQuery,
        limit: int,
        offset: int,
    ) -> tuple[ResearchExperiment, ...]:
        """Return a filtered, ordered experiment slice."""

        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        experiments = self._sort(
            self._filter(query),
            query,
        )

        return experiments[offset : offset + limit]

    def _filter(
        self,
        query: ExperimentCatalogQuery,
    ) -> tuple[ResearchExperiment, ...]:
        return tuple(
            experiment
            for experiment in self._experiments.values()
            if (query.dataset_id is None or experiment.dataset_id == query.dataset_id)
            and (query.strategy_name is None or experiment.strategy_name == query.strategy_name)
            and (
                query.strategy_version is None
                or experiment.strategy_version == query.strategy_version
            )
            and (
                query.horizon_candles is None or experiment.horizon_candles == query.horizon_candles
            )
        )

    @staticmethod
    def _sort(
        experiments: tuple[ResearchExperiment, ...],
        query: ExperimentCatalogQuery,
    ) -> tuple[ResearchExperiment, ...]:
        reverse = query.sort_direction is ExperimentSortDirection.DESCENDING

        if query.sort_by is ExperimentSortField.HORIZON_CANDLES:
            ordered = sorted(
                experiments,
                key=lambda experiment: (
                    experiment.horizon_candles,
                    experiment.experiment_id,
                ),
                reverse=reverse,
            )

        else:
            ordered = sorted(
                experiments,
                key=lambda experiment: (
                    experiment.created_at,
                    experiment.experiment_id,
                ),
                reverse=reverse,
            )

        return tuple(ordered)

    @staticmethod
    def _same_experiment(
        *,
        first: ResearchExperiment,
        second: ResearchExperiment,
    ) -> bool:
        return (
            first.dataset_id == second.dataset_id
            and first.strategy_name == second.strategy_name
            and first.strategy_version == second.strategy_version
            and first.horizon_candles == second.horizon_candles
            and first.parameters == second.parameters
            and first.result == second.result
        )
