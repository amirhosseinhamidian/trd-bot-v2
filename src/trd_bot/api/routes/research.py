from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from trd_bot.api.dependencies import get_experiment_registry
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research import (
    DatasetBuilder,
    ExperimentBuilder,
    ExperimentParameter,
    InMemoryExperimentRegistry,
    InvalidDatasetError,
    ResearchExperiment,
    ResearchPipeline,
    ResearchPipelineResult,
)
from trd_bot.research.experiments import ExperimentSummary
from trd_bot.strategies import EMACrossoverStrategy

router = APIRouter(
    prefix="/research",
    tags=["Research"],
)

ExperimentRegistryDependency = Annotated[
    InMemoryExperimentRegistry,
    Depends(get_experiment_registry),
]

PaginationQuery = Annotated[
    PaginationParams,
    Query(),
]


class EMACrossoverResearchRequest(BaseModel):
    """Request for running an offline EMA research pipeline."""

    model_config = ConfigDict(extra="forbid")

    dataset_name: str = Field(
        min_length=1,
        max_length=100,
    )

    candles: tuple[OHLCVCandle, ...] = Field(
        min_length=1,
    )

    fast_period: int = Field(default=9, ge=2)
    slow_period: int = Field(default=21, ge=3)
    horizon_candles: int = Field(default=1, ge=1)


def _run_research_pipeline(
    request: EMACrossoverResearchRequest,
) -> ResearchPipelineResult:
    try:
        dataset = DatasetBuilder().build(
            name=request.dataset_name,
            candles=request.candles,
        )

        strategy = EMACrossoverStrategy(
            fast_period=request.fast_period,
            slow_period=request.slow_period,
        )

        return ResearchPipeline().run(
            dataset=dataset,
            strategy=strategy,
            horizon_candles=request.horizon_candles,
        )

    except InvalidDatasetError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "dataset failed quality checks",
                "issues": [issue.model_dump(mode="json") for issue in error.report.issues],
            },
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


@router.post(
    "/ema-crossover",
    response_model=ResearchPipelineResult,
)
def run_ema_crossover_research(
    request: EMACrossoverResearchRequest,
) -> ResearchPipelineResult:
    """Run the EMA research workflow without storing it."""

    return _run_research_pipeline(request)


@router.post(
    "/experiments/ema-crossover",
    response_model=ResearchExperiment,
)
def create_ema_crossover_experiment(
    request: EMACrossoverResearchRequest,
    registry: ExperimentRegistryDependency,
) -> ResearchExperiment:
    """Run and store an EMA research experiment."""

    result = _run_research_pipeline(request)

    experiment = ExperimentBuilder().build(
        result=result,
        parameters=(
            ExperimentParameter(
                name="fast_period",
                value=str(request.fast_period),
            ),
            ExperimentParameter(
                name="slow_period",
                value=str(request.slow_period),
            ),
        ),
    )

    return registry.save(experiment)


@router.get(
    "/experiments",
    response_model=Page[ExperimentSummary],
)
def list_experiments(
    registry: ExperimentRegistryDependency,
    pagination: PaginationQuery,
) -> Page[ExperimentSummary]:
    """List lightweight experiment summaries with pagination."""

    experiments = registry.list_page(
        limit=pagination.limit,
        offset=pagination.offset,
    )

    summaries = tuple(ExperimentSummary.from_experiment(experiment) for experiment in experiments)

    return build_page(
        summaries,
        total=registry.count(),
        pagination=pagination,
    )


@router.get(
    "/experiments/{experiment_id}",
    response_model=ResearchExperiment,
)
def get_experiment(
    experiment_id: str,
    registry: ExperimentRegistryDependency,
) -> ResearchExperiment:
    """Return one stored experiment."""

    experiment = registry.get(experiment_id)

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="experiment not found",
        )

    return experiment
