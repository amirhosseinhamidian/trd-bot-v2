from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from trd_bot.api.dependencies import (
    get_acceptance_policy_preset_catalog,
    get_dataset_repository,
    get_experiment_registry,
    get_walk_forward_run_registry,
)
from trd_bot.api.pagination import (
    Page,
    PaginationParams,
    build_page,
)
from trd_bot.research import (
    AcceptancePolicyPreset,
    AcceptancePolicyPresetCatalog,
    DatasetCatalogQuery,
    DatasetRepository,
    DatasetSummary,
    ExperimentCatalogQuery,
    ExperimentRegistry,
    ResearchActivityBuilder,
    ResearchActivityItem,
    ResearchActivityType,
    WalkForwardRunCatalogQuery,
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


class ResearchActivityParams(PaginationParams):
    """Filters and pagination for the research activity feed."""

    activity_type: ResearchActivityType | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None

    @field_validator("from_time", "to_time")
    @classmethod
    def time_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("activity time must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if (
            self.from_time is not None
            and self.to_time is not None
            and self.to_time < self.from_time
        ):
            raise ValueError("to_time must be on or after from_time")
        return self


ResearchActivityParamsQuery = Annotated[
    ResearchActivityParams,
    Query(),
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


def _tail_window(
    *,
    total: int,
    window_size: int,
) -> tuple[int, int]:
    selected_size = min(
        total,
        window_size,
    )

    return (
        selected_size,
        total - selected_size,
    )


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


@router.get(
    "/activity",
    response_model=Page[ResearchActivityItem],
)
def get_research_activity(
    datasets: DatasetRepositoryDependency,
    experiments: ExperimentRegistryDependency,
    walk_forward_runs: WalkForwardRunRegistryDependency,
    params: ResearchActivityParamsQuery,
) -> Page[ResearchActivityItem]:
    """Return a newest-first paginated feed of persisted research resources."""

    dataset_query = DatasetCatalogQuery(
        created_at_from=params.from_time,
        created_at_to=params.to_time,
    )
    experiment_query = ExperimentCatalogQuery(
        created_at_from=params.from_time,
        created_at_to=params.to_time,
    )
    walk_forward_query = WalkForwardRunCatalogQuery(
        created_at_from=params.from_time,
        created_at_to=params.to_time,
    )

    dataset_count = (
        datasets.count_matching(dataset_query)
        if params.activity_type in (None, ResearchActivityType.DATASET)
        else 0
    )
    experiment_count = (
        experiments.count_matching(experiment_query)
        if params.activity_type in (None, ResearchActivityType.EXPERIMENT)
        else 0
    )
    walk_forward_run_count = (
        walk_forward_runs.count_matching(walk_forward_query)
        if params.activity_type in (None, ResearchActivityType.WALK_FORWARD_RUN)
        else 0
    )

    total = dataset_count + experiment_count + walk_forward_run_count
    window_size = min(total, params.offset + params.limit)

    dataset_limit, dataset_offset = _tail_window(
        total=dataset_count,
        window_size=window_size,
    )
    experiment_limit, experiment_offset = _tail_window(
        total=experiment_count,
        window_size=window_size,
    )
    run_limit, run_offset = _tail_window(
        total=walk_forward_run_count,
        window_size=window_size,
    )

    selected_datasets = (
        datasets.search_page(
            query=dataset_query,
            limit=dataset_limit,
            offset=dataset_offset,
        )
        if dataset_limit
        else ()
    )
    selected_experiments = (
        experiments.search_page(
            query=experiment_query,
            limit=experiment_limit,
            offset=experiment_offset,
        )
        if experiment_limit
        else ()
    )
    selected_runs = (
        walk_forward_runs.search_page(
            query=walk_forward_query,
            limit=run_limit,
            offset=run_offset,
        )
        if run_limit
        else ()
    )

    activity = ResearchActivityBuilder().build(
        datasets=selected_datasets,
        experiments=selected_experiments,
        walk_forward_runs=selected_runs,
    )
    page_items = activity[params.offset : params.offset + params.limit]

    return build_page(
        page_items,
        total=total,
        pagination=PaginationParams(
            limit=params.limit,
            offset=params.offset,
        ),
    )
