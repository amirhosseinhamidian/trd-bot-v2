from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_optimization_execution_repository,
    get_optimization_runner,
)
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.datasets import DatasetRepository
from trd_bot.research.optimization import OptimizationParameterGrid, OptimizationPlanner
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionBuilder,
    OptimizationExecutionRepository,
)
from trd_bot.research.optimization_runner import OptimizationRunner

router = APIRouter(
    prefix="/research/optimization-executions",
    tags=["Research"],
)


class CreateOptimizationExecutionRequest(BaseModel):
    """Untrusted inputs accepted when creating one bounded optimization plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str = Field(min_length=1, max_length=100)
    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=30)
    objective: ExperimentComparisonMetric = ExperimentComparisonMetric.EXCESS_RETURN
    parameter_grid: tuple[OptimizationParameterGrid, ...] = Field(min_length=1)
    horizon_candles: int = Field(default=1, ge=1)
    backtest_config: BacktestConfig


class OptimizationExecutionCatalogParams(BaseModel):
    """Pagination parameters for persisted optimization executions."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


OptimizationExecutionCatalogParamsQuery = Annotated[
    OptimizationExecutionCatalogParams,
    Query(),
]

OptimizationExecutionRepositoryDependency = Annotated[
    OptimizationExecutionRepository,
    Depends(get_optimization_execution_repository),
]

OptimizationRunnerDependency = Annotated[
    OptimizationRunner,
    Depends(get_optimization_runner),
]

DatasetRepositoryDependency = Annotated[
    DatasetRepository,
    Depends(get_dataset_repository),
]


def _error_detail(*, code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
    }


@router.post(
    "",
    response_model=OptimizationExecution,
    status_code=201,
)
def create_optimization_execution(
    request: CreateOptimizationExecutionRequest,
    datasets: DatasetRepositoryDependency,
    runner: OptimizationRunnerDependency,
) -> OptimizationExecution:
    """Persist a server-built bounded plan without starting inline work."""

    dataset = datasets.get(request.dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail=_error_detail(
                code="dataset_not_found",
                message="dataset not found",
            ),
        )

    try:
        plan = OptimizationPlanner().plan(
            strategy_name=request.strategy_name,
            strategy_version=request.strategy_version,
            parameter_grid=request.parameter_grid,
            objective=request.objective,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=_error_detail(
                code="invalid_optimization_plan",
                message=str(error),
            ),
        ) from error

    execution = OptimizationExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        plan=plan,
        horizon_candles=request.horizon_candles,
        backtest_config=request.backtest_config,
    )

    try:
        return runner.create(execution)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                code="optimization_execution_conflict",
                message="optimization execution could not be stored",
            ),
        ) from error


@router.get(
    "",
    response_model=Page[OptimizationExecution],
)
def list_optimization_executions(
    repository: OptimizationExecutionRepositoryDependency,
    params: OptimizationExecutionCatalogParamsQuery,
) -> Page[OptimizationExecution]:
    """List persisted optimization execution state newest first."""

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )
    items = repository.list_page(
        limit=params.limit,
        offset=params.offset,
    )
    return build_page(
        items,
        total=repository.count(),
        pagination=pagination,
    )


@router.get(
    "/{execution_id}",
    response_model=OptimizationExecution,
)
def get_optimization_execution(
    execution_id: str,
    repository: OptimizationExecutionRepositoryDependency,
) -> OptimizationExecution:
    """Return one persisted optimization execution."""

    execution = repository.get(execution_id)
    if execution is None:
        raise HTTPException(
            status_code=404,
            detail=_error_detail(
                code="optimization_execution_not_found",
                message="optimization execution not found",
            ),
        )
    return execution
