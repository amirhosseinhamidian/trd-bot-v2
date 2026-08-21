import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Self

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
        )


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

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[ResearchExperiment, ...]:
        """Return a validated slice of stored experiments."""

        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        experiments = self.list_all()

        return experiments[offset : offset + limit]

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
