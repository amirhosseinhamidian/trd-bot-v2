from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_experiment_registry,
    get_walk_forward_run_registry,
)
from trd_bot.research import (
    DatasetRepository,
    DatasetSummary,
    ExperimentRegistry,
    WalkForwardRunRegistry,
    WalkForwardRunSummary,
)
from trd_bot.research.experiments import ExperimentSummary

router = APIRouter(
    prefix="/research/overview",
    tags=["Research overview"],
)

DatasetRepositoryDependency = Annotated[
    DatasetRepository,
    Depends(get_dataset_repository),
]

ExperimentRegistryDependency = Annotated[
    ExperimentRegistry,
    Depends(get_experiment_registry),
]

WalkForwardRunRegistryDependency = Annotated[
    WalkForwardRunRegistry,
    Depends(get_walk_forward_run_registry),
]


class ResearchOverview(BaseModel):
    """Compact persisted research state for a dashboard landing page."""

    model_config = ConfigDict(frozen=True)

    dataset_count: int = Field(ge=0)
    experiment_count: int = Field(ge=0)
    walk_forward_run_count: int = Field(ge=0)

    latest_dataset: DatasetSummary | None
    latest_experiment: ExperimentSummary | None
    latest_walk_forward_run: WalkForwardRunSummary | None


def _latest_dataset(
    repository: DatasetRepository,
    *,
    total: int,
) -> DatasetSummary | None:
    if total == 0:
        return None

    datasets = repository.list_page(
        limit=1,
        offset=total - 1,
    )

    if not datasets:
        return None

    return DatasetSummary.from_dataset(datasets[0])


def _latest_experiment(
    registry: ExperimentRegistry,
    *,
    total: int,
) -> ExperimentSummary | None:
    if total == 0:
        return None

    experiments = registry.list_page(
        limit=1,
        offset=total - 1,
    )

    if not experiments:
        return None

    return ExperimentSummary.from_experiment(experiments[0])


def _latest_walk_forward_run(
    registry: WalkForwardRunRegistry,
    *,
    total: int,
) -> WalkForwardRunSummary | None:
    if total == 0:
        return None

    runs = registry.list_page(
        limit=1,
        offset=total - 1,
    )

    if not runs:
        return None

    return WalkForwardRunSummary.from_run(runs[0])


@router.get(
    "",
    response_model=ResearchOverview,
)
def get_research_overview(
    datasets: DatasetRepositoryDependency,
    experiments: ExperimentRegistryDependency,
    walk_forward_runs: WalkForwardRunRegistryDependency,
) -> ResearchOverview:
    """Return counts and latest compact records for persisted research."""

    dataset_count = datasets.count()
    experiment_count = experiments.count()
    walk_forward_run_count = walk_forward_runs.count()

    return ResearchOverview(
        dataset_count=dataset_count,
        experiment_count=experiment_count,
        walk_forward_run_count=walk_forward_run_count,
        latest_dataset=_latest_dataset(
            datasets,
            total=dataset_count,
        ),
        latest_experiment=_latest_experiment(
            experiments,
            total=experiment_count,
        ),
        latest_walk_forward_run=(
            _latest_walk_forward_run(
                walk_forward_runs,
                total=walk_forward_run_count,
            )
        ),
    )
