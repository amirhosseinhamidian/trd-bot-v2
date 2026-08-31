from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
)
from pydantic import BaseModel, ConfigDict, Field

from trd_bot.api.background_jobs import (
    ExperimentExecutionTask,
    WalkForwardExecutionTask,
)
from trd_bot.api.dependencies import (
    get_acceptance_policy_preset_catalog,
    get_dataset_repository,
    get_experiment_execution_repository,
    get_experiment_execution_task,
    get_experiment_registry,
    get_walk_forward_execution_repository,
    get_walk_forward_execution_task,
    get_walk_forward_run_registry,
)
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.backtesting.models import BacktestConfig
from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research import (
    AcceptancePolicyPreset,
    AcceptancePolicyPresetCatalog,
    DatasetBuilder,
    DatasetRepository,
    DatasetSnapshot,
    EMACrossoverExecutionParameters,
    ExperimentAcceptanceEvaluator,
    ExperimentAcceptancePolicy,
    ExperimentAcceptanceResult,
    ExperimentBuilder,
    ExperimentCatalogQuery,
    ExperimentComparator,
    ExperimentComparisonRequest,
    ExperimentComparisonResult,
    ExperimentExecution,
    ExperimentExecutionBuilder,
    ExperimentExecutionRepository,
    ExperimentParameter,
    ExperimentPerformanceSeries,
    ExperimentPerformanceSeriesBuilder,
    ExperimentRegistry,
    ExperimentReportCsvExporter,
    ExperimentResearchReport,
    ExperimentResearchReportBuilder,
    ExperimentSignalCatalog,
    ExperimentSignalCatalogQuery,
    InvalidDatasetError,
    PresetExperimentResearchReport,
    ResearchExperiment,
    ResearchPipeline,
    ResearchPipelineResult,
    RSIThresholdExecutionParameters,
    SMACrossoverExecutionParameters,
    StrategyExecutionParameters,
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
    WalkForwardStabilityAnalyzer,
    WalkForwardStabilityReport,
)
from trd_bot.research.experiments import ExperimentSummary
from trd_bot.research.walk_forward_executions import (
    WalkForwardExecution,
    WalkForwardExecutionBuilder,
    WalkForwardExecutionRepository,
)
from trd_bot.strategies import (
    EMACrossoverStrategy,
    StrategyMetadata,
    build_default_strategy_registry,
)
from trd_bot.strategies.signals import StrategySignal

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

AcceptancePolicyPresetCatalogDependency = Annotated[
    AcceptancePolicyPresetCatalog,
    Depends(get_acceptance_policy_preset_catalog),
]

ExperimentExecutionRepositoryDependency = Annotated[
    ExperimentExecutionRepository,
    Depends(get_experiment_execution_repository),
]

ExperimentExecutionTaskDependency = Annotated[
    ExperimentExecutionTask,
    Depends(get_experiment_execution_task),
]

WalkForwardExecutionRepositoryDependency = Annotated[
    WalkForwardExecutionRepository,
    Depends(get_walk_forward_execution_repository),
]

WalkForwardExecutionTaskDependency = Annotated[
    WalkForwardExecutionTask,
    Depends(get_walk_forward_execution_task),
]


@router.get(
    "/strategies",
    response_model=tuple[StrategyMetadata, ...],
)
def list_research_strategies() -> tuple[StrategyMetadata, ...]:
    """List versioned strategies available for historical research execution."""

    return build_default_strategy_registry().list_metadata()


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


class StoredDatasetEMACrossoverResearchRequest(BaseModel):
    """Request for running EMA research against an already stored dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(
        min_length=1,
        max_length=200,
    )

    fast_period: int = Field(default=9, ge=2)
    slow_period: int = Field(default=21, ge=3)
    horizon_candles: int = Field(default=1, ge=1)

    starting_balance: Decimal = Field(default=Decimal("10000"), gt=0)
    allocation_fraction: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    slippage_rate: Decimal = Field(default=Decimal("0.0005"), ge=0, lt=1)


class StoredDatasetSMACrossoverResearchRequest(BaseModel):
    """Request for running SMA research against an already stored dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(
        min_length=1,
        max_length=200,
    )

    fast_period: int = Field(default=9, ge=2)
    slow_period: int = Field(default=21, ge=3)
    horizon_candles: int = Field(default=1, ge=1)

    starting_balance: Decimal = Field(default=Decimal("10000"), gt=0)
    allocation_fraction: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    slippage_rate: Decimal = Field(default=Decimal("0.0005"), ge=0, lt=1)


class StoredDatasetRSIThresholdResearchRequest(BaseModel):
    """Request for running RSI research against an already stored dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(
        min_length=1,
        max_length=200,
    )

    period: int = Field(default=14, ge=2)
    oversold_threshold: Decimal = Field(
        default=Decimal("30"),
        gt=0,
        lt=50,
    )
    overbought_threshold: Decimal = Field(
        default=Decimal("70"),
        gt=50,
        lt=100,
    )
    horizon_candles: int = Field(default=1, ge=1)

    starting_balance: Decimal = Field(default=Decimal("10000"), gt=0)
    allocation_fraction: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    slippage_rate: Decimal = Field(default=Decimal("0.0005"), ge=0, lt=1)


class StoredDatasetEMACrossoverExecutionRequest(
    StoredDatasetEMACrossoverResearchRequest,
):
    """Versioned EMA request accepted by generic experiment execution dispatch."""

    strategy_name: Literal["ema-crossover"]
    strategy_version: Literal["1.0.0"]


class StoredDatasetSMACrossoverExecutionRequest(
    StoredDatasetSMACrossoverResearchRequest,
):
    """Versioned SMA request accepted by generic experiment execution dispatch."""

    strategy_name: Literal["sma-crossover"]
    strategy_version: Literal["1.0.0"]


class StoredDatasetRSIThresholdExecutionRequest(
    StoredDatasetRSIThresholdResearchRequest,
):
    """Versioned RSI request accepted by generic experiment execution dispatch."""

    strategy_name: Literal["rsi-threshold"]
    strategy_version: Literal["1.0.0"]


StoredDatasetStrategyExecutionRequest = Annotated[
    StoredDatasetEMACrossoverExecutionRequest
    | StoredDatasetRSIThresholdExecutionRequest
    | StoredDatasetSMACrossoverExecutionRequest,
    Field(discriminator="strategy_name"),
]


class EMACrossoverWalkForwardRequest(EMACrossoverResearchRequest):
    """Request for an offline EMA walk-forward execution."""

    train_candles: int = Field(default=100, ge=2)
    test_candles: int = Field(default=20, ge=1)
    step_candles: int = Field(default=20, ge=1)
    gap_candles: int = Field(default=0, ge=0)
    mode: WalkForwardMode = WalkForwardMode.ROLLING


class StoredDatasetEMACrossoverWalkForwardRequest(
    StoredDatasetEMACrossoverResearchRequest,
):
    """Request for walk-forward analysis against a stored dataset."""

    train_candles: int = Field(default=100, ge=2)
    test_candles: int = Field(default=20, ge=1)
    step_candles: int = Field(default=20, ge=1)
    gap_candles: int = Field(default=0, ge=0)
    mode: WalkForwardMode = WalkForwardMode.ROLLING


class StoredDatasetSMACrossoverWalkForwardRequest(
    StoredDatasetSMACrossoverResearchRequest,
):
    """Request for SMA walk-forward analysis against a stored dataset."""

    train_candles: int = Field(default=100, ge=2)
    test_candles: int = Field(default=20, ge=1)
    step_candles: int = Field(default=20, ge=1)
    gap_candles: int = Field(default=0, ge=0)
    mode: WalkForwardMode = WalkForwardMode.ROLLING


class StoredDatasetRSIThresholdWalkForwardRequest(
    StoredDatasetRSIThresholdResearchRequest,
):
    """Request for RSI walk-forward analysis against a stored dataset."""

    train_candles: int = Field(default=100, ge=2)
    test_candles: int = Field(default=20, ge=1)
    step_candles: int = Field(default=20, ge=1)
    gap_candles: int = Field(default=0, ge=0)
    mode: WalkForwardMode = WalkForwardMode.ROLLING


class StoredDatasetEMACrossoverWalkForwardExecutionRequest(
    StoredDatasetEMACrossoverWalkForwardRequest,
):
    """Versioned EMA request accepted by generic walk-forward dispatch."""

    strategy_name: Literal["ema-crossover"]
    strategy_version: Literal["1.0.0"]


class StoredDatasetSMACrossoverWalkForwardExecutionRequest(
    StoredDatasetSMACrossoverWalkForwardRequest,
):
    """Versioned SMA request accepted by generic walk-forward dispatch."""

    strategy_name: Literal["sma-crossover"]
    strategy_version: Literal["1.0.0"]


class StoredDatasetRSIThresholdWalkForwardExecutionRequest(
    StoredDatasetRSIThresholdWalkForwardRequest,
):
    """Versioned RSI request accepted by generic walk-forward dispatch."""

    strategy_name: Literal["rsi-threshold"]
    strategy_version: Literal["1.0.0"]


StoredDatasetStrategyWalkForwardExecutionRequest = Annotated[
    StoredDatasetEMACrossoverWalkForwardExecutionRequest
    | StoredDatasetRSIThresholdWalkForwardExecutionRequest
    | StoredDatasetSMACrossoverWalkForwardExecutionRequest,
    Field(discriminator="strategy_name"),
]


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


class ExperimentExecutionCatalogParams(BaseModel):
    """Pagination parameters for experiment execution lists."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )


ExperimentExecutionCatalogParamsQuery = Annotated[
    ExperimentExecutionCatalogParams,
    Query(),
]


class WalkForwardExecutionCatalogParams(BaseModel):
    """Pagination parameters for walk-forward execution lists."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )


WalkForwardExecutionCatalogParamsQuery = Annotated[
    WalkForwardExecutionCatalogParams,
    Query(),
]


class ExperimentSignalCatalogParams(ExperimentSignalCatalogQuery):
    """Filtering, ordering, and pagination for experiment signals."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )

    def catalog_query(self) -> ExperimentSignalCatalogQuery:
        return ExperimentSignalCatalogQuery.model_validate(
            self.model_dump(
                exclude={
                    "limit",
                    "offset",
                }
            )
        )


ExperimentSignalCatalogParamsQuery = Annotated[
    ExperimentSignalCatalogParams,
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


def _build_ema_execution_parameters(
    request: StoredDatasetEMACrossoverResearchRequest,
) -> EMACrossoverExecutionParameters:
    try:
        return EMACrossoverExecutionParameters(
            fast_period=request.fast_period,
            slow_period=request.slow_period,
            horizon_candles=request.horizon_candles,
            starting_balance=request.starting_balance,
            allocation_fraction=request.allocation_fraction,
            fee_rate=request.fee_rate,
            slippage_rate=request.slippage_rate,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="invalid EMA execution parameters",
        ) from error


def _build_sma_execution_parameters(
    request: StoredDatasetSMACrossoverResearchRequest,
) -> SMACrossoverExecutionParameters:
    try:
        return SMACrossoverExecutionParameters(
            fast_period=request.fast_period,
            slow_period=request.slow_period,
            horizon_candles=request.horizon_candles,
            starting_balance=request.starting_balance,
            allocation_fraction=request.allocation_fraction,
            fee_rate=request.fee_rate,
            slippage_rate=request.slippage_rate,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="invalid SMA execution parameters",
        ) from error


def _build_rsi_execution_parameters(
    request: StoredDatasetRSIThresholdResearchRequest,
) -> RSIThresholdExecutionParameters:
    try:
        return RSIThresholdExecutionParameters(
            period=request.period,
            oversold_threshold=request.oversold_threshold,
            overbought_threshold=request.overbought_threshold,
            horizon_candles=request.horizon_candles,
            starting_balance=request.starting_balance,
            allocation_fraction=request.allocation_fraction,
            fee_rate=request.fee_rate,
            slippage_rate=request.slippage_rate,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="invalid RSI execution parameters",
        ) from error


def _build_strategy_execution_parameters(
    request: (
        StoredDatasetEMACrossoverResearchRequest
        | StoredDatasetRSIThresholdResearchRequest
        | StoredDatasetSMACrossoverResearchRequest
    ),
) -> StrategyExecutionParameters:
    if isinstance(request, StoredDatasetEMACrossoverResearchRequest):
        return _build_ema_execution_parameters(request)

    if isinstance(request, StoredDatasetSMACrossoverResearchRequest):
        return _build_sma_execution_parameters(request)

    return _build_rsi_execution_parameters(request)


def _build_walk_forward_config(
    request: (
        EMACrossoverWalkForwardRequest
        | StoredDatasetEMACrossoverWalkForwardRequest
        | StoredDatasetRSIThresholdWalkForwardRequest
        | StoredDatasetSMACrossoverWalkForwardRequest
    ),
) -> WalkForwardConfig:
    try:
        return WalkForwardConfig(
            train_candles=request.train_candles,
            test_candles=request.test_candles,
            step_candles=request.step_candles,
            gap_candles=request.gap_candles,
            mode=request.mode,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def _build_ema_parameters(
    request: (EMACrossoverResearchRequest | StoredDatasetEMACrossoverResearchRequest),
) -> tuple[ExperimentParameter, ...]:
    return (
        ExperimentParameter(
            name="fast_period",
            value=str(request.fast_period),
        ),
        ExperimentParameter(
            name="slow_period",
            value=str(request.slow_period),
        ),
    )


def _build_experiment_parameters(
    request: EMACrossoverResearchRequest | StoredDatasetEMACrossoverResearchRequest,
) -> tuple[ExperimentParameter, ...]:
    return (
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


def _run_stored_dataset_research_pipeline(
    request: StoredDatasetEMACrossoverResearchRequest,
    datasets: DatasetRepository,
) -> _ResearchExecution:
    dataset = datasets.get(request.dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="dataset not found",
        )

    try:
        strategy = EMACrossoverStrategy(
            fast_period=request.fast_period,
            slow_period=request.slow_period,
        )

        result = ResearchPipeline().run(
            dataset=dataset,
            strategy=strategy,
            horizon_candles=request.horizon_candles,
            backtest_config=BacktestConfig(
                starting_balance=request.starting_balance,
                allocation_fraction=request.allocation_fraction,
                fee_rate=request.fee_rate,
                slippage_rate=request.slippage_rate,
            ),
        )

        return _ResearchExecution(
            dataset=dataset,
            result=result,
        )

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


def _run_stored_dataset_walk_forward_pipeline(
    request: StoredDatasetEMACrossoverWalkForwardRequest,
    datasets: DatasetRepository,
) -> _WalkForwardExecution:
    dataset = datasets.get(request.dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="dataset not found",
        )

    try:
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

        result = WalkForwardExecutor().execute(
            dataset=dataset,
            materialization=materialization,
            strategy=strategy,
            strategy_parameters=_build_ema_parameters(request),
            horizon_candles=request.horizon_candles,
            backtest_config=backtest_config,
        )

        return _WalkForwardExecution(
            dataset=dataset,
            config=walk_forward_config,
            result=result,
        )

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


@router.post(
    "/walk-forward/runs/ema-crossover/from-dataset",
    response_model=WalkForwardResearchRun,
)
def create_ema_crossover_walk_forward_run_from_dataset(
    request: StoredDatasetEMACrossoverWalkForwardRequest,
    registry: WalkForwardRunRegistryDependency,
    datasets: DatasetRepositoryDependency,
) -> WalkForwardResearchRun:
    """Run and store walk-forward analysis for a stored dataset."""

    execution = _run_stored_dataset_walk_forward_pipeline(
        request=request,
        datasets=datasets,
    )

    run = WalkForwardRunBuilder().build(
        result=execution.result,
        walk_forward_config=execution.config,
    )

    try:
        return registry.save(run)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


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
    "/walk-forward/runs/{execution_id}/summary",
    response_model=WalkForwardRunSummary,
)
def get_walk_forward_run_summary(
    execution_id: str,
    registry: WalkForwardRunRegistryDependency,
) -> WalkForwardRunSummary:
    """Return a lightweight summary for one stored walk-forward run."""

    run = registry.get(execution_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="walk-forward run not found",
        )

    return WalkForwardRunSummary.from_run(run)


@router.get(
    ("/walk-forward/runs/{execution_id}/stability"),
    response_model=WalkForwardStabilityReport,
)
def get_walk_forward_stability_report(
    execution_id: str,
    registry: WalkForwardRunRegistryDependency,
) -> WalkForwardStabilityReport:
    """Return historical fold stability metrics for one stored run."""

    run = registry.get(execution_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="walk-forward run not found",
        )

    return WalkForwardStabilityAnalyzer().analyze(run)


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
    "/experiment-executions",
    response_model=ExperimentExecution,
    status_code=202,
)
def create_experiment_execution(
    request: StoredDatasetStrategyExecutionRequest,
    background_tasks: BackgroundTasks,
    executions: ExperimentExecutionRepositoryDependency,
    datasets: DatasetRepositoryDependency,
    execution_task: ExperimentExecutionTaskDependency,
) -> ExperimentExecution:
    """Queue a versioned historical strategy experiment execution."""

    dataset = datasets.get(request.dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="dataset not found",
        )

    execution = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=_build_strategy_execution_parameters(request),
    )

    try:
        stored_execution = executions.save(execution)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail="experiment execution could not be stored",
        ) from error

    background_tasks.add_task(
        execution_task,
        stored_execution.execution_id,
    )

    return stored_execution


@router.get(
    "/experiment-executions",
    response_model=Page[ExperimentExecution],
)
def list_experiment_executions(
    executions: ExperimentExecutionRepositoryDependency,
    params: ExperimentExecutionCatalogParamsQuery,
) -> Page[ExperimentExecution]:
    """List persisted experiment executions."""

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )

    items = executions.list_page(
        limit=params.limit,
        offset=params.offset,
    )

    return build_page(
        items,
        total=executions.count(),
        pagination=pagination,
    )


@router.get(
    "/experiment-executions/{execution_id}",
    response_model=ExperimentExecution,
)
def get_experiment_execution(
    execution_id: str,
    executions: ExperimentExecutionRepositoryDependency,
) -> ExperimentExecution:
    """Return one persisted experiment execution."""

    execution = executions.get(execution_id)

    if execution is None:
        raise HTTPException(
            status_code=404,
            detail="experiment execution not found",
        )

    return execution


@router.post(
    "/walk-forward-executions",
    response_model=WalkForwardExecution,
    status_code=202,
)
def create_walk_forward_execution(
    request: StoredDatasetStrategyWalkForwardExecutionRequest,
    background_tasks: BackgroundTasks,
    executions: WalkForwardExecutionRepositoryDependency,
    datasets: DatasetRepositoryDependency,
    execution_task: WalkForwardExecutionTaskDependency,
) -> WalkForwardExecution:
    """Queue versioned walk-forward analysis for a stored historical dataset."""

    dataset = datasets.get(request.dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="dataset not found",
        )

    walk_forward_config = _build_walk_forward_config(request)

    try:
        plan = WalkForwardPlanner().plan(
            dataset=dataset,
            config=walk_forward_config,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    execution = WalkForwardExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=_build_strategy_execution_parameters(request),
        walk_forward_config=walk_forward_config,
        total_folds=len(plan.folds),
    )

    try:
        stored_execution = executions.save(execution)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail="walk-forward execution could not be stored",
        ) from error

    background_tasks.add_task(
        execution_task,
        stored_execution.execution_id,
    )

    return stored_execution


@router.get(
    "/walk-forward-executions",
    response_model=Page[WalkForwardExecution],
)
def list_walk_forward_executions(
    executions: WalkForwardExecutionRepositoryDependency,
    params: WalkForwardExecutionCatalogParamsQuery,
) -> Page[WalkForwardExecution]:
    """List persisted walk-forward executions."""

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )

    items = executions.list_page(
        limit=params.limit,
        offset=params.offset,
    )

    return build_page(
        items,
        total=executions.count(),
        pagination=pagination,
    )


@router.get(
    "/walk-forward-executions/{execution_id}",
    response_model=WalkForwardExecution,
)
def get_walk_forward_execution(
    execution_id: str,
    executions: WalkForwardExecutionRepositoryDependency,
) -> WalkForwardExecution:
    """Return one persisted walk-forward execution."""

    execution = executions.get(execution_id)

    if execution is None:
        raise HTTPException(
            status_code=404,
            detail="walk-forward execution not found",
        )

    return execution


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
        parameters=_build_experiment_parameters(request),
    )

    try:
        datasets.save(execution.dataset)
        return registry.save(experiment)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/experiments/ema-crossover/from-dataset",
    response_model=ResearchExperiment,
)
def create_ema_crossover_experiment_from_dataset(
    request: StoredDatasetEMACrossoverResearchRequest,
    registry: ExperimentRegistryDependency,
    datasets: DatasetRepositoryDependency,
) -> ResearchExperiment:
    """Run and store EMA research using an already persisted dataset."""

    execution = _run_stored_dataset_research_pipeline(
        request=request,
        datasets=datasets,
    )

    experiment = ExperimentBuilder().build(
        result=execution.result,
        parameters=_build_experiment_parameters(request),
    )

    try:
        return registry.save(experiment)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


@router.get(
    "/experiments/{experiment_id}/performance-series",
    response_model=ExperimentPerformanceSeries,
)
def get_experiment_performance_series(
    experiment_id: str,
    registry: ExperimentRegistryDependency,
) -> ExperimentPerformanceSeries:
    """Return realized historical equity series for a stored experiment."""

    experiment = registry.get(experiment_id)

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="experiment not found",
        )

    return ExperimentPerformanceSeriesBuilder().build(experiment)


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


@router.post(
    "/experiments/{experiment_id}/acceptance",
    response_model=ExperimentAcceptanceResult,
)
def assess_experiment_acceptance(
    experiment_id: str,
    policy: ExperimentAcceptancePolicy,
    registry: ExperimentRegistryDependency,
) -> ExperimentAcceptanceResult:
    """Assess one experiment against explicit historical thresholds."""

    experiment = registry.get(experiment_id)

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="experiment not found",
        )

    return ExperimentAcceptanceEvaluator().evaluate(
        experiment=ExperimentSummary.from_experiment(experiment),
        policy=policy,
    )


@router.post(
    "/experiments/{experiment_id}/report",
    response_model=ExperimentResearchReport,
)
def build_experiment_research_report(
    experiment_id: str,
    policy: ExperimentAcceptancePolicy,
    registry: ExperimentRegistryDependency,
) -> ExperimentResearchReport:
    """Build a dashboard-ready report from stored historical results."""

    experiment = registry.get(experiment_id)

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="experiment not found",
        )

    return ExperimentResearchReportBuilder().build(
        experiment=ExperimentSummary.from_experiment(experiment),
        policy=policy,
    )


@router.get(
    "/acceptance-policies",
    response_model=tuple[
        AcceptancePolicyPreset,
        ...,
    ],
)
def list_acceptance_policy_presets(
    catalog: AcceptancePolicyPresetCatalogDependency,
) -> tuple[AcceptancePolicyPreset, ...]:
    """List built-in versioned policies for historical research."""

    return catalog.list_all()


@router.get(
    "/acceptance-policies/{preset_id}",
    response_model=AcceptancePolicyPreset,
)
def get_acceptance_policy_preset(
    preset_id: str,
    catalog: AcceptancePolicyPresetCatalogDependency,
) -> AcceptancePolicyPreset:
    """Return one built-in historical policy preset."""

    preset = catalog.get(preset_id)

    if preset is None:
        raise HTTPException(
            status_code=404,
            detail=("acceptance policy preset not found"),
        )

    return preset


@router.post(
    ("/experiments/{experiment_id}/report/presets/{preset_id}"),
    response_model=PresetExperimentResearchReport,
)
def build_experiment_report_from_preset(
    experiment_id: str,
    preset_id: str,
    registry: ExperimentRegistryDependency,
    catalog: AcceptancePolicyPresetCatalogDependency,
) -> PresetExperimentResearchReport:
    """Build a historical report using one exact versioned policy preset."""

    experiment = registry.get(experiment_id)

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="experiment not found",
        )

    preset = catalog.get(preset_id)

    if preset is None:
        raise HTTPException(
            status_code=404,
            detail=("acceptance policy preset not found"),
        )

    report = ExperimentResearchReportBuilder().build(
        experiment=ExperimentSummary.from_experiment(experiment),
        policy=preset.policy,
    )

    return PresetExperimentResearchReport(
        preset=preset,
        report=report,
    )


@router.get(
    "/experiments/{experiment_id}/report/presets/{preset_id}/export.csv",
    response_class=Response,
)
def export_experiment_report_csv(
    experiment_id: str,
    preset_id: str,
    registry: ExperimentRegistryDependency,
    catalog: AcceptancePolicyPresetCatalogDependency,
) -> Response:
    """Download one versioned historical experiment report as CSV."""

    experiment = registry.get(experiment_id)

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="experiment not found",
        )

    preset = catalog.get(preset_id)

    if preset is None:
        raise HTTPException(
            status_code=404,
            detail="acceptance policy preset not found",
        )

    report = ExperimentResearchReportBuilder().build(
        experiment=ExperimentSummary.from_experiment(experiment),
        policy=preset.policy,
    )

    csv_content = ExperimentReportCsvExporter().export(
        PresetExperimentResearchReport(
            preset=preset,
            report=report,
        )
    )

    filename = f"{experiment_id}-{preset_id}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (f'attachment; filename="{filename}"'),
        },
    )


@router.get(
    "/experiments/{experiment_id}/signals",
    response_model=Page[StrategySignal],
)
def list_experiment_signals(
    experiment_id: str,
    registry: ExperimentRegistryDependency,
    params: ExperimentSignalCatalogParamsQuery,
) -> Page[StrategySignal]:
    """List historical signals generated by one stored experiment."""

    experiment = registry.get(experiment_id)

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="experiment not found",
        )

    query = params.catalog_query()
    catalog = ExperimentSignalCatalog()

    signals = catalog.search_page(
        signals=experiment.result.signals,
        query=query,
        limit=params.limit,
        offset=params.offset,
    )

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )

    return build_page(
        signals,
        total=catalog.count_matching(
            signals=experiment.result.signals,
            query=query,
        ),
        pagination=pagination,
    )


@router.get(
    "/experiments/{experiment_id}/summary",
    response_model=ExperimentSummary,
)
def get_experiment_summary(
    experiment_id: str,
    registry: ExperimentRegistryDependency,
) -> ExperimentSummary:
    """Return a lightweight historical summary for one stored experiment."""

    experiment = registry.get(experiment_id)

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="experiment not found",
        )

    return ExperimentSummary.from_experiment(experiment)


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
