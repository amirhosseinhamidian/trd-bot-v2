import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.jobs import BackgroundJobKind
from trd_bot.market_data.connections import (
    InMemoryMarketDataConnectionRepository,
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataProviderCatalog,
)
from trd_bot.market_data.import_history import InMemoryMarketDataImportRepository
from trd_bot.market_data.providers import (
    MarketDataProvider,
    MarketDataProviderAccessMode,
    MarketDataProviderMetadata,
)
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.dataset_file_imports import (
    DatasetColumnMapping,
    DatasetFileCommitRequest,
    DatasetFileImportService,
    DatasetFilePreviewRequest,
)
from trd_bot.research.datasets import DatasetBuilder, InMemoryDatasetRepository
from trd_bot.research.experiment_execution_runner import ExperimentExecutionRunner
from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
    ExperimentExecutionBuilder,
    ExperimentExecutionStatus,
    InMemoryExperimentExecutionRepository,
)
from trd_bot.research.experiments import InMemoryExperimentRegistry
from trd_bot.research.historical_dataset_commits import InMemoryHistoricalDatasetCommitter
from trd_bot.research.historical_dataset_jobs import (
    HistoricalDatasetJobOperation,
    HistoricalDatasetJobPayload,
    HistoricalDatasetJobRequest,
    HistoricalDatasetJobRunner,
)
from trd_bot.research.optimization import OptimizationParameterGrid, OptimizationPlanner
from trd_bot.research.optimization_executions import (
    InMemoryOptimizationExecutionRepository,
    OptimizationExecutionBuilder,
    OptimizationExecutionState,
)
from trd_bot.research.optimization_worker import OptimizationExecutionJobRunner
from trd_bot.research.walk_forward import WalkForwardConfig, WalkForwardPlanner
from trd_bot.research.walk_forward_execution_runner import WalkForwardExecutionRunner
from trd_bot.research.walk_forward_executions import (
    InMemoryWalkForwardExecutionRepository,
    WalkForwardExecutionBuilder,
    WalkForwardExecutionStatus,
)
from trd_bot.research.walk_forward_runs import InMemoryWalkForwardRunRegistry

BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION: Final = "background-job-workloads-v1"

_FIXTURE_TIME: Final = datetime(2026, 1, 1, tzinfo=UTC)
_EXECUTION_TIME: Final = datetime(2026, 10, 1, tzinfo=UTC)
_PAIR: Final = TradingPair(base_asset="BTC", quote_asset="USDT")
_CONNECTION_ID: Final = "capacity-benchmark-connection"


@dataclass(frozen=True)
class BackgroundJobWorkload:
    """One bounded, versioned workload that executes canonical product logic."""

    kind: BackgroundJobKind
    fixture_version: str
    dimensions: tuple[tuple[str, int], ...]
    execute: Callable[[], None]


class _FixtureMarketDataProvider(MarketDataProvider):
    def __init__(self, candles: Sequence[OHLCVCandle]) -> None:
        self._candles = tuple(candles)

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return MarketDataProviderMetadata(
            provider_id="capacity-benchmark-provider",
            display_name="Capacity benchmark provider",
            requires_credentials=False,
            supported_market_types=(MarketType.SPOT,),
            supported_timeframes=(Timeframe.HOUR_1,),
            default_pair=_PAIR,
            access_mode=MarketDataProviderAccessMode.DIRECT,
            max_closed_candles=None,
        )

    async def test_connection(self) -> None:
        return None

    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        del pair, timeframe, start_time, end_time
        candles = self._candles if limit is None else self._candles[:limit]
        return list(candles)


def _build_candles(*, count: int, source: str) -> tuple[OHLCVCandle, ...]:
    candles: list[OHLCVCandle] = []
    for index in range(count):
        open_time = _FIXTURE_TIME + timedelta(hours=index)
        wave = Decimal(index % 24) - Decimal("12")
        trend = Decimal(index) / Decimal("50")
        open_price = Decimal("100") + trend + wave / Decimal("4")
        close_price = open_price + (Decimal("1.25") if index % 2 == 0 else Decimal("-0.75"))
        candles.append(
            OHLCVCandle(
                source=source,
                pair=_PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=open_time,
                close_time=open_time + timedelta(hours=1) - timedelta(milliseconds=1),
                received_at=open_time + timedelta(hours=1),
                open_price=open_price,
                high_price=max(open_price, close_price) + Decimal("1"),
                low_price=min(open_price, close_price) - Decimal("1"),
                close_price=close_price,
                volume=Decimal("1000") + Decimal(index),
                is_closed=True,
            )
        )
    return tuple(candles)


def _execution_parameters() -> EMACrossoverExecutionParameters:
    return EMACrossoverExecutionParameters(
        fast_period=9,
        slow_period=21,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )


def _backtest_config() -> BacktestConfig:
    return BacktestConfig(
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )


def _csv_content(candles: Sequence[OHLCVCandle]) -> bytes:
    rows = ["open_time,close_time,open,high,low,close,volume,is_closed"]
    rows.extend(
        ",".join(
            (
                candle.open_time.isoformat(),
                candle.close_time.isoformat(),
                str(candle.open_price),
                str(candle.high_price),
                str(candle.low_price),
                str(candle.close_price),
                str(candle.volume),
                "true",
            )
        )
        for candle in candles
    )
    return "\n".join(rows).encode("utf-8")


def _dataset_file_workload(candles: Sequence[OHLCVCandle]) -> Callable[[], None]:
    content = _csv_content(candles)
    request = DatasetFilePreviewRequest(
        name="Capacity benchmark file import",
        source="capacity-file-import",
        pair=_PAIR,
        timeframe=Timeframe.HOUR_1,
        column_mapping=DatasetColumnMapping(
            open_time="open_time",
            open_price="open",
            high_price="high",
            low_price="low",
            close_price="close",
            volume="volume",
            is_closed="is_closed",
        ),
    )

    def execute() -> None:
        service = DatasetFileImportService()
        preview = service.preview(
            file_name="capacity-candles.csv",
            content=content,
            request=request,
        )
        commit_request = DatasetFileCommitRequest.model_validate(
            {**request.model_dump(), "preview_checksum": preview.preview_checksum}
        )
        dataset = service.build_dataset(
            file_name="capacity-candles.csv",
            content=content,
            request=commit_request,
        )
        if dataset.candle_count != len(candles) or dataset.checksum != preview.preview_checksum:
            raise RuntimeError("dataset file workload produced inconsistent output")

    return execute


def _market_data_import_workload(candles: Sequence[OHLCVCandle]) -> Callable[[], None]:
    provider = _FixtureMarketDataProvider(candles)
    payload = HistoricalDatasetJobPayload(
        operation=HistoricalDatasetJobOperation.IMPORT,
        connection_id=_CONNECTION_ID,
        request=HistoricalDatasetJobRequest(
            name="Capacity benchmark market import",
            pair=_PAIR,
            timeframe=Timeframe.HOUR_1,
            start_time=candles[0].open_time,
            end_time=candles[-1].open_time + timedelta(hours=1),
            preview_checksum=DatasetBuilder()
            .build(
                name="Capacity benchmark checksum source",
                candles=candles,
                created_at=_EXECUTION_TIME,
            )
            .checksum,
        ),
    )

    def execute() -> None:
        connections = InMemoryMarketDataConnectionRepository()
        connections.save(
            MarketDataConnection(
                connection_id=_CONNECTION_ID,
                provider_id=provider.metadata.provider_id,
                display_name="Capacity benchmark connection",
                state=MarketDataConnectionState.ENABLED,
                health_status=MarketDataConnectionHealth.HEALTHY,
                created_at=_EXECUTION_TIME,
                updated_at=_EXECUTION_TIME,
                last_tested_at=_EXECUTION_TIME,
            )
        )
        datasets = InMemoryDatasetRepository()
        history = InMemoryMarketDataImportRepository()
        runner = HistoricalDatasetJobRunner(
            connections=connections,
            providers=MarketDataProviderCatalog({provider.metadata.provider_id: lambda: provider}),
            datasets=datasets,
            history=history,
            committer=InMemoryHistoricalDatasetCommitter(
                datasets=datasets,
                history=history,
            ),
        )
        result = asyncio.run(
            runner.run(
                payload=payload,
                import_id="capacity-market-import-1",
                created_at=_EXECUTION_TIME,
                report_progress=lambda _: None,
                cancellation_requested=lambda: False,
            )
        )
        if result is None or result.candle_count != len(candles) or datasets.count() != 1:
            raise RuntimeError("market data import workload produced inconsistent output")

    return execute


def _experiment_workload(candles: Sequence[OHLCVCandle]) -> Callable[[], None]:
    dataset = DatasetBuilder().build(
        name="Capacity benchmark experiment dataset",
        candles=candles,
        created_at=_EXECUTION_TIME,
    )

    def execute() -> None:
        datasets = InMemoryDatasetRepository()
        executions = InMemoryExperimentExecutionRepository()
        experiments = InMemoryExperimentRegistry()
        datasets.save(dataset)
        queued = executions.save(
            ExperimentExecutionBuilder().build(
                dataset_id=dataset.dataset_id,
                parameters=_execution_parameters(),
                now=_EXECUTION_TIME,
            )
        )
        completed = ExperimentExecutionRunner(
            executions=executions,
            datasets=datasets,
            experiments=experiments,
        ).run(queued.execution_id)
        if completed.status is not ExperimentExecutionStatus.SUCCEEDED:
            raise RuntimeError("experiment workload did not succeed")
        if completed.experiment_id is None or experiments.count() != 1:
            raise RuntimeError("experiment workload did not persist its result")

    return execute


def _walk_forward_workload(candles: Sequence[OHLCVCandle]) -> Callable[[], None]:
    dataset = DatasetBuilder().build(
        name="Capacity benchmark walk-forward dataset",
        candles=candles,
        created_at=_EXECUTION_TIME,
    )
    config = WalkForwardConfig(
        train_candles=240,
        test_candles=48,
        step_candles=48,
        gap_candles=0,
    )
    total_folds = len(WalkForwardPlanner().plan(dataset=dataset, config=config).folds)

    def execute() -> None:
        datasets = InMemoryDatasetRepository()
        executions = InMemoryWalkForwardExecutionRepository()
        runs = InMemoryWalkForwardRunRegistry()
        datasets.save(dataset)
        queued = executions.save(
            WalkForwardExecutionBuilder().build(
                dataset_id=dataset.dataset_id,
                parameters=_execution_parameters(),
                walk_forward_config=config,
                total_folds=total_folds,
                now=_EXECUTION_TIME,
            )
        )
        completed = WalkForwardExecutionRunner(
            executions=executions,
            datasets=datasets,
            runs=runs,
        ).run(queued.execution_id)
        if completed.status is not WalkForwardExecutionStatus.SUCCEEDED:
            raise RuntimeError("walk-forward workload did not succeed")
        if completed.completed_folds != total_folds or runs.count() != 1:
            raise RuntimeError("walk-forward workload produced inconsistent output")

    return execute


def _optimization_workload(candles: Sequence[OHLCVCandle]) -> Callable[[], None]:
    dataset = DatasetBuilder().build(
        name="Capacity benchmark optimization dataset",
        candles=candles,
        created_at=_EXECUTION_TIME,
    )
    plan = OptimizationPlanner().plan(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
        parameter_grid=(
            OptimizationParameterGrid(name="fast_period", values=("3", "5")),
            OptimizationParameterGrid(name="slow_period", values=("8", "13")),
        ),
    )

    def execute() -> None:
        datasets = InMemoryDatasetRepository()
        executions = InMemoryOptimizationExecutionRepository()
        experiments = InMemoryExperimentRegistry()
        datasets.save(dataset)
        queued = executions.save(
            OptimizationExecutionBuilder().build(
                dataset_id=dataset.dataset_id,
                plan=plan,
                horizon_candles=1,
                backtest_config=_backtest_config(),
                now=_EXECUTION_TIME,
            )
        )
        completed = OptimizationExecutionJobRunner(
            executions=executions,
            datasets=datasets,
            experiments=experiments,
        ).run(
            queued.execution_id,
            report_progress=lambda _: None,
            cancellation_requested=lambda: False,
        )
        if completed.status is not OptimizationExecutionState.SUCCEEDED:
            raise RuntimeError("optimization workload did not succeed")
        if completed.completed_trials != plan.total_trials:
            raise RuntimeError("optimization workload did not execute every trial")

    return execute


def build_background_job_workloads() -> Mapping[BackgroundJobKind, BackgroundJobWorkload]:
    """Build the complete v1 fixture set without using external state or credentials."""

    file_candles = _build_candles(count=1_000, source="capacity-file-import")
    market_candles = _build_candles(count=1_000, source="capacity-benchmark-provider")
    research_candles = _build_candles(count=720, source="capacity-research")
    workloads = (
        BackgroundJobWorkload(
            kind=BackgroundJobKind.DATASET_FILE_IMPORT,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("candles", len(file_candles)), ("format_count", 1)),
            execute=_dataset_file_workload(file_candles),
        ),
        BackgroundJobWorkload(
            kind=BackgroundJobKind.MARKET_DATA_IMPORT,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("candles", len(market_candles)), ("provider_count", 1)),
            execute=_market_data_import_workload(market_candles),
        ),
        BackgroundJobWorkload(
            kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("candles", len(research_candles)), ("strategy_count", 1)),
            execute=_experiment_workload(research_candles),
        ),
        BackgroundJobWorkload(
            kind=BackgroundJobKind.WALK_FORWARD_EXECUTION,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("candles", len(research_candles)), ("folds", 10)),
            execute=_walk_forward_workload(research_candles),
        ),
        BackgroundJobWorkload(
            kind=BackgroundJobKind.OPTIMIZATION_EXECUTION,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("candles", len(research_candles)), ("trials", 4)),
            execute=_optimization_workload(research_candles),
        ),
    )
    result = {workload.kind: workload for workload in workloads}
    if set(result) != set(BackgroundJobKind):
        raise RuntimeError("background job workload fixtures do not cover every job kind")
    return result
