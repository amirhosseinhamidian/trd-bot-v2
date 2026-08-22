from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_experiment_registry,
    get_walk_forward_run_registry,
)
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.backtesting.models import BacktestConfig
from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research import (
    DatasetBuilder,
    DatasetRepository,
    DatasetSnapshot,
    ExperimentBuilder,
    ExperimentCatalogQuery,
    ExperimentComparator,
    ExperimentComparisonRequest,
    ExperimentComparisonResult,
    ExperimentParameter,
    ExperimentRegistry,
    InvalidDatasetError,
    ResearchExperiment,
    ResearchPipeline,
    ResearchPipelineResult,
    WalkForwardConfig,
    WalkForwardDatasetMaterializer,
    WalkForwardExecutionResult,
    WalkForwardExecutor,
    WalkForwardMode,
    WalkForwardPlanner,
    WalkForwardResearchRun,
    WalkForwardRunBuilder,
    WalkForwardRunCatalogQuery,
    WalkForwardRunRegistry,
    WalkForwardRunSummary,
)
from trd_bot.research.experiments import ExperimentSummary
from trd_bot.strategies import EMACrossoverStrategy

router = APIRouter(
    prefix="/research",
    tags=["Research"],
)

ExperimentRegistryDependency = Annotated[
    ExperimentRegistry,
    Depends(get_experiment_registry),
]

DatasetRepositoryDependency = Annotated[
    DatasetRepository,
    Depends(get_dataset_repository),
]

WalkForwardRunRegistryDependency = Annotated[
    WalkForwardRunRegistry,
    Depends(get_walk_forward_run_registry),
]


@dataclass(frozen=True, slots=True)
class _ResearchExecution:
    dataset: DatasetSnapshot
    result: ResearchPipelineResult


@dataclass(frozen=True, slots=True)
class _WalkForwardExecution:
    dataset: DatasetSnapshot
    config: WalkForwardConfig
    result: WalkForwardExecutionResult


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

    starting_balance: Decimal = Field(default=Decimal("10000"), gt=0)
    allocation_fraction: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    slippage_rate: Decimal = Field(default=Decimal("0.0005"), ge=0, lt=1)


class EMACrossoverWalkForwardRequest(EMACrossoverResearchRequest):
    """Request for an offline EMA walk-forward execution."""

    train_candles: int = Field(default=100, ge=2)
    test_candles: int = Field(default=20, ge=1)
    step_candles: int = Field(default=20, ge=1)
    gap_candles: int = Field(default=0, ge=0)
    mode: WalkForwardMode = WalkForwardMode.ROLLING


class ExperimentCatalogParams(ExperimentCatalogQuery):
    """Filters, ordering, and pagination for experiment lists."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )

    def catalog_query(
        self,
    ) -> ExperimentCatalogQuery:
        return ExperimentCatalogQuery.model_validate(
            self.model_dump(
                exclude={
                    "limit",
                    "offset",
                }
            )
        )


ExperimentCatalogParamsQuery = Annotated[
    ExperimentCatalogParams,
    Query(),
]


class WalkForwardRunCatalogParams(WalkForwardRunCatalogQuery):
    """Filters, ordering, and pagination for walk-forward lists."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )

    def catalog_query(
        self,
    ) -> WalkForwardRunCatalogQuery:
        return WalkForwardRunCatalogQuery.model_validate(
            self.model_dump(
                exclude={
                    "limit",
                    "offset",
                }
            )
        )


WalkForwardRunCatalogParamsQuery = Annotated[
    WalkForwardRunCatalogParams,
    Query(),
]


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _build_walk_forward_config(
    request: EMACrossoverWalkForwardRequest,
) -> WalkForwardConfig:
    return WalkForwardConfig(
        train_candles=request.train_candles,
        test_candles=request.test_candles,
        step_candles=request.step_candles,
        gap_candles=request.gap_candles,
        mode=request.mode,
    )


def _build_ema_parameters(
    request: EMACrossoverResearchRequest,
) -> tuple[ExperimentParameter, ...]:
    return (
        ExperimentParameter(name="fast_period", value=str(request.fast_period)),
        ExperimentParameter(name="slow_period", value=str(request.slow_period)),
    )


def _run_research_pipeline(
    request: EMACrossoverResearchRequest,
) -> _ResearchExecution:
    try:
        dataset = DatasetBuilder().build(
            name=request.dataset_name,
            candles=request.candles,
        )

        strategy = EMACrossoverStrategy(
            fast_period=request.fast_period,
            slow_period=request.slow_period,
        )

        return _ResearchExecution(
            dataset=dataset,
            result=ResearchPipeline().run(
                dataset=dataset,
                strategy=strategy,
                horizon_candles=request.horizon_candles,
                backtest_config=BacktestConfig(
                    starting_balance=request.starting_balance,
                    allocation_fraction=request.allocation_fraction,
                    fee_rate=request.fee_rate,
                    slippage_rate=request.slippage_rate,
                ),
            ),
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


def _run_walk_forward_pipeline(
    request: EMACrossoverWalkForwardRequest,
) -> _WalkForwardExecution:
    try:
        dataset = DatasetBuilder().build(
            name=request.dataset_name,
            candles=request.candles,
        )
        strategy = EMACrossoverStrategy(
            fast_period=request.fast_period,
            slow_period=request.slow_period,
        )
        backtest_config = BacktestConfig(
            starting_balance=request.starting_balance,
            allocation_fraction=request.allocation_fraction,
            fee_rate=request.fee_rate,
            slippage_rate=request.slippage_rate,
        )
        walk_forward_config = _build_walk_forward_config(request)
        plan = WalkForwardPlanner().plan(
            dataset=dataset,
            config=walk_forward_config,
        )
        materialization = WalkForwardDatasetMaterializer().materialize(
            dataset=dataset,
            plan=plan,
        )

        return _WalkForwardExecution(
            dataset=dataset,
            config=walk_forward_config,
            result=WalkForwardExecutor().execute(
                dataset=dataset,
                materialization=materialization,
                strategy=strategy,
                strategy_parameters=_build_ema_parameters(request),
                horizon_candles=request.horizon_candles,
                backtest_config=backtest_config,
            ),
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

    return _run_research_pipeline(request).result


@router.post(
    "/walk-forward/ema-crossover",
    response_model=WalkForwardExecutionResult,
)
def run_ema_crossover_walk_forward(
    request: EMACrossoverWalkForwardRequest,
) -> WalkForwardExecutionResult:
    """Run an EMA strategy on chronological out-of-sample folds."""

    return _run_walk_forward_pipeline(request).result


@router.post(
    "/walk-forward/runs/ema-crossover",
    response_model=WalkForwardResearchRun,
)
def create_ema_crossover_walk_forward_run(
    request: EMACrossoverWalkForwardRequest,
    registry: WalkForwardRunRegistryDependency,
    datasets: DatasetRepositoryDependency,
) -> WalkForwardResearchRun:
    """Run and store an offline EMA walk-forward execution."""

    execution = _run_walk_forward_pipeline(request)
    run = WalkForwardRunBuilder().build(
        result=execution.result,
        walk_forward_config=execution.config,
    )

    try:
        datasets.save(execution.dataset)
        return registry.save(run)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get(
    "/walk-forward/runs",
    response_model=Page[WalkForwardRunSummary],
)
def list_walk_forward_runs(
    registry: WalkForwardRunRegistryDependency,
    params: WalkForwardRunCatalogParamsQuery,
) -> Page[WalkForwardRunSummary]:
    """List filtered lightweight walk-forward runs."""

    query = params.catalog_query()

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )

    runs = registry.search_page(
        query=query,
        limit=params.limit,
        offset=params.offset,
    )

    summaries = tuple(WalkForwardRunSummary.from_run(run) for run in runs)

    return build_page(
        summaries,
        total=registry.count_matching(query),
        pagination=pagination,
    )


@router.get(
    "/walk-forward/runs/{execution_id}",
    response_model=WalkForwardResearchRun,
)
def get_walk_forward_run(
    execution_id: str,
    registry: WalkForwardRunRegistryDependency,
) -> WalkForwardResearchRun:
    """Return one stored walk-forward run."""

    run = registry.get(execution_id)
    if run is None:
        raise HTTPException(status_code=404, detail="walk-forward run not found")
    return run


@router.post(
    "/experiments/ema-crossover",
    response_model=ResearchExperiment,
)
def create_ema_crossover_experiment(
    request: EMACrossoverResearchRequest,
    registry: ExperimentRegistryDependency,
    datasets: DatasetRepositoryDependency,
) -> ResearchExperiment:
    """Run and store an EMA research experiment."""

    execution = _run_research_pipeline(request)

    experiment = ExperimentBuilder().build(
        result=execution.result,
        parameters=(
            ExperimentParameter(
                name="fast_period",
                value=str(request.fast_period),
            ),
            ExperimentParameter(
                name="slow_period",
                value=str(request.slow_period),
            ),
            ExperimentParameter(
                name="starting_balance",
                value=_canonical_decimal(request.starting_balance),
            ),
            ExperimentParameter(
                name="allocation_fraction",
                value=_canonical_decimal(request.allocation_fraction),
            ),
            ExperimentParameter(
                name="fee_rate",
                value=_canonical_decimal(request.fee_rate),
            ),
            ExperimentParameter(
                name="slippage_rate",
                value=_canonical_decimal(request.slippage_rate),
            ),
        ),
    )

    try:
        datasets.save(execution.dataset)
        return registry.save(experiment)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get(
    "/experiments",
    response_model=Page[ExperimentSummary],
)
@router.get(
    "/experiments",
    response_model=Page[ExperimentSummary],
)
def list_experiments(
    registry: ExperimentRegistryDependency,
    params: ExperimentCatalogParamsQuery,
) -> Page[ExperimentSummary]:
    """List filtered lightweight experiment summaries."""

    query = params.catalog_query()

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )

    experiments = registry.search_page(
        query=query,
        limit=params.limit,
        offset=params.offset,
    )

    summaries = tuple(ExperimentSummary.from_experiment(experiment) for experiment in experiments)

    return build_page(
        summaries,
        total=registry.count_matching(query),
        pagination=pagination,
    )


@router.post(
    "/experiments/compare",
    response_model=ExperimentComparisonResult,
)
def compare_experiments(
    request: ExperimentComparisonRequest,
    registry: ExperimentRegistryDependency,
) -> ExperimentComparisonResult:
    """Compare stored experiments using historical research metrics."""

    experiments: list[ResearchExperiment] = []
    missing_ids: list[str] = []

    for experiment_id in request.experiment_ids:
        experiment = registry.get(experiment_id)

        if experiment is None:
            missing_ids.append(experiment_id)
        else:
            experiments.append(experiment)

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "experiments not found",
                "experiment_ids": missing_ids,
            },
        )

    summaries = tuple(ExperimentSummary.from_experiment(experiment) for experiment in experiments)

    try:
        return ExperimentComparator().compare(
            experiments=summaries,
            metric=request.metric,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


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
