from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from trd_bot.research.datasets import (
    DatasetSnapshot,
)
from trd_bot.research.experiments import (
    ResearchExperiment,
)
from trd_bot.research.walk_forward_runs import (
    WalkForwardResearchRun,
)


class ResearchActivityType(StrEnum):
    """Persisted research resource types shown in the dashboard feed."""

    DATASET = "dataset"
    EXPERIMENT = "experiment"
    WALK_FORWARD_RUN = "walk_forward_run"


class ResearchActivityItem(BaseModel):
    """Compact immutable item in the historical research activity feed."""

    model_config = ConfigDict(frozen=True)

    activity_type: ResearchActivityType

    resource_id: str = Field(min_length=1)

    created_at: datetime

    label: str = Field(
        min_length=1,
        max_length=100,
    )

    dataset_id: str = Field(min_length=1)

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

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created time must include timezone information")

        return value.astimezone(UTC)


class ResearchActivityBuilder:
    """Build a newest-first feed from compact persisted research resources."""

    def build(
        self,
        *,
        datasets: Sequence[DatasetSnapshot] = (),
        experiments: Sequence[ResearchExperiment] = (),
        walk_forward_runs: Sequence[WalkForwardResearchRun] = (),
    ) -> tuple[ResearchActivityItem, ...]:
        items = [self._from_dataset(dataset) for dataset in datasets]

        items.extend(self._from_experiment(experiment) for experiment in experiments)

        items.extend(self._from_walk_forward_run(run) for run in walk_forward_runs)

        return tuple(
            sorted(
                items,
                key=lambda item: (
                    item.created_at,
                    item.activity_type.value,
                    item.resource_id,
                ),
                reverse=True,
            )
        )

    @staticmethod
    def _from_dataset(
        dataset: DatasetSnapshot,
    ) -> ResearchActivityItem:
        return ResearchActivityItem(
            activity_type=(ResearchActivityType.DATASET),
            resource_id=dataset.dataset_id,
            created_at=dataset.created_at,
            label=dataset.name,
            dataset_id=dataset.dataset_id,
        )

    @staticmethod
    def _from_experiment(
        experiment: ResearchExperiment,
    ) -> ResearchActivityItem:
        return ResearchActivityItem(
            activity_type=(ResearchActivityType.EXPERIMENT),
            resource_id=experiment.experiment_id,
            created_at=experiment.created_at,
            label=experiment.strategy_name,
            dataset_id=experiment.dataset_id,
            strategy_name=experiment.strategy_name,
            strategy_version=(experiment.strategy_version),
            horizon_candles=(experiment.horizon_candles),
        )

    @staticmethod
    def _from_walk_forward_run(
        run: WalkForwardResearchRun,
    ) -> ResearchActivityItem:
        result = run.result

        return ResearchActivityItem(
            activity_type=(ResearchActivityType.WALK_FORWARD_RUN),
            resource_id=run.execution_id,
            created_at=run.created_at,
            label=result.strategy_name,
            dataset_id=result.source_dataset_id,
            strategy_name=result.strategy_name,
            strategy_version=(result.strategy_version),
            horizon_candles=(result.horizon_candles),
        )
