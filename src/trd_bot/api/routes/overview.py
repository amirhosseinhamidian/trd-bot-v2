from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from trd_bot.api.dependencies import (
    get_acceptance_policy_preset_catalog,
    get_dataset_repository,
    get_experiment_registry,
    get_walk_forward_run_registry,
)
from trd_bot.research import (
    AcceptancePolicyPreset,
    AcceptancePolicyPresetCatalog,
    DatasetRepository,
    DatasetSummary,
    ExperimentRegistry,
    WalkForwardRunRegistry,
    WalkForwardRunSummary,
)
from trd_bot.research.experiments import (
    ExperimentSummary,
)

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

AcceptancePolicyPresetCatalogDependency = Annotated[
    AcceptancePolicyPresetCatalog,
    Depends(get_acceptance_policy_preset_catalog),
]


class ResearchStage(StrEnum):
    """Highest completed stage in the historical research workflow."""

    EMPTY = "empty"
    DATA_AVAILABLE = "data_available"
    EXPERIMENTS_AVAILABLE = "experiments_available"
    WALK_FORWARD_AVAILABLE = "walk_forward_available"


class ResearchOverview(BaseModel):
    """Compact persisted research state for a dashboard landing page."""

    model_config = ConfigDict(frozen=True)

    dataset_count: int = Field(ge=0)
    experiment_count: int = Field(ge=0)
    walk_forward_run_count: int = Field(ge=0)

    acceptance_policy_preset_count: int = Field(ge=0)

    research_stage: ResearchStage

    acceptance_policy_presets: tuple[
        AcceptancePolicyPreset,
        ...,
    ]

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


def _research_stage(
    *,
    dataset_count: int,
    experiment_count: int,
    walk_forward_run_count: int,
) -> ResearchStage:
    if walk_forward_run_count > 0:
        return ResearchStage.WALK_FORWARD_AVAILABLE

    if experiment_count > 0:
        return ResearchStage.EXPERIMENTS_AVAILABLE

    if dataset_count > 0:
        return ResearchStage.DATA_AVAILABLE

    return ResearchStage.EMPTY


@router.get(
    "",
    response_model=ResearchOverview,
)
def get_research_overview(
    datasets: DatasetRepositoryDependency,
    experiments: ExperimentRegistryDependency,
    walk_forward_runs: (WalkForwardRunRegistryDependency),
    policy_presets: (AcceptancePolicyPresetCatalogDependency),
) -> ResearchOverview:
    """Return counts and latest compact records for persisted research."""

    dataset_count = datasets.count()
    experiment_count = experiments.count()

    walk_forward_run_count = walk_forward_runs.count()

    acceptance_policy_presets = policy_presets.list_all()

    return ResearchOverview(
        dataset_count=dataset_count,
        experiment_count=experiment_count,
        walk_forward_run_count=(walk_forward_run_count),
        acceptance_policy_preset_count=len(acceptance_policy_presets),
        research_stage=_research_stage(
            dataset_count=dataset_count,
            experiment_count=experiment_count,
            walk_forward_run_count=(walk_forward_run_count),
        ),
        acceptance_policy_presets=(acceptance_policy_presets),
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
