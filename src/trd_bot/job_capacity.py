import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final

from trd_bot.alerts import (
    AlertEvaluationDisposition,
    AlertEvaluationJobPayload,
    AlertRuleDefinition,
    AlertRuleState,
    AlertSeverity,
    MarketContextAlertCondition,
    evaluate_alert,
)
from trd_bot.backtesting.models import BacktestConfig
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyMarketContextEvaluationEnqueuer,
    SqlAlchemyMarketContextEvaluationRunner,
    SqlAlchemyMarketDataEventStore,
    SqlAlchemyMarketDataIngestor,
    SqlAlchemyMarketDataPollingScheduler,
    SqlAlchemyMarketDataPollJobRunner,
    SqlAlchemyMarketDataReplayEnqueuer,
    SqlAlchemyMarketDataReplayRunner,
    SqlAlchemyMarketDataWatchlistManager,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.market_data_connection_repositories import (
    SqlAlchemyMarketDataConnectionRepository,
)
from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.jobs import BackgroundJobKind
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextEvaluationJobPayload,
    MarketContextEvidence,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
    build_market_regime_assessment_id,
)
from trd_bot.market_data.connections import (
    InMemoryMarketDataConnectionRepository,
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataProviderCatalog,
)
from trd_bot.market_data.events import (
    MarketDataEvent,
    MarketDataWatermark,
    MarketDataWindowSnapshot,
    MarketDataWindowState,
)
from trd_bot.market_data.import_history import InMemoryMarketDataImportRepository
from trd_bot.market_data.polling import MarketDataPollJobPayload, MarketDataPollRunStatus
from trd_bot.market_data.providers import (
    MarketDataProvider,
    MarketDataProviderAccessMode,
    MarketDataProviderMetadata,
)
from trd_bot.market_data.storage import MarketDataRawObservation, VersionedMarketDataWatermark
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

BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION: Final = "background-job-workloads-v2"

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
    def __init__(
        self,
        candles: Sequence[OHLCVCandle],
        *,
        provider_id: str = "capacity-benchmark-provider",
    ) -> None:
        self._candles = tuple(candles)
        self._provider_id = provider_id

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return MarketDataProviderMetadata(
            provider_id=self._provider_id,
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


def _market_data_poll_workload() -> Callable[[], None]:
    candles = tuple(
        OHLCVCandle(
            source="kraken-public",
            pair=_PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=_EXECUTION_TIME - timedelta(hours=offset),
            close_time=_EXECUTION_TIME - timedelta(hours=offset - 1),
            received_at=_EXECUTION_TIME,
            open_price=Decimal("100"),
            high_price=Decimal("110"),
            low_price=Decimal("95"),
            close_price=Decimal("105"),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for offset in (2, 1)
    )
    kraken = _FixtureMarketDataProvider(candles, provider_id="kraken-public")
    binance = _FixtureMarketDataProvider((), provider_id="binance-public")
    providers = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: kraken,
            "binance-public": lambda: binance,
        }
    )

    def execute() -> None:
        engine = create_database_engine("sqlite+pysqlite:///:memory:")
        DatabaseBase.metadata.create_all(engine)
        factory = create_session_factory(engine)
        try:
            with factory() as session:
                connections = SqlAlchemyMarketDataConnectionRepository(session)
                for provider_id in ("kraken-public", "binance-public"):
                    connections.save(
                        MarketDataConnection(
                            connection_id=f"capacity-{provider_id}",
                            provider_id=provider_id,
                            display_name=provider_id,
                            state=MarketDataConnectionState.ENABLED,
                            health_status=MarketDataConnectionHealth.HEALTHY,
                            created_at=_EXECUTION_TIME,
                            updated_at=_EXECUTION_TIME,
                            last_tested_at=_EXECUTION_TIME,
                        )
                    )
                entry = SqlAlchemyMarketDataWatchlistManager(
                    session=session,
                    providers=providers,
                    clock=lambda: _EXECUTION_TIME,
                ).create(
                    pair=_PAIR,
                    timeframe=Timeframe.HOUR_1,
                    kraken_connection_id="capacity-kraken-public",
                    binance_connection_id="capacity-binance-public",
                    lookback_candles=2,
                )

            with factory() as session:
                jobs = SqlAlchemyMarketDataPollingScheduler(session).enqueue_due(
                    now=_EXECUTION_TIME
                )
            if len(jobs) != 1:
                raise RuntimeError("market-data poll workload did not enqueue one job")
            payload = MarketDataPollJobPayload.model_validate(jobs[0].payload)
            run = asyncio.run(
                SqlAlchemyMarketDataPollJobRunner(
                    session_factory=factory,
                    providers=providers,
                    clock=lambda: _EXECUTION_TIME + timedelta(seconds=1),
                ).run(
                    payload=payload,
                    job_id=jobs[0].job_id,
                    job_attempt=1,
                )
            )
            if (
                run.status is not MarketDataPollRunStatus.SUCCEEDED
                or run.watchlist_id != entry.watchlist_id
                or run.received_candles != 2
            ):
                raise RuntimeError("market-data poll workload produced inconsistent output")
        finally:
            engine.dispose()

    return execute


def _market_data_replay_workload() -> Callable[[], None]:
    def execute() -> None:
        engine = create_database_engine("sqlite+pysqlite:///:memory:")
        DatabaseBase.metadata.create_all(engine)
        factory = create_session_factory(engine)
        candle = OHLCVCandle(
            source="capacity-replay-provider",
            pair=_PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=_EXECUTION_TIME - timedelta(hours=2),
            close_time=_EXECUTION_TIME - timedelta(hours=1),
            received_at=_EXECUTION_TIME + timedelta(minutes=1),
            open_price=Decimal("100"),
            high_price=Decimal("110"),
            low_price=Decimal("95"),
            close_price=Decimal("105"),
            volume=Decimal("1000"),
            is_closed=True,
        )
        event = MarketDataEvent.from_candle(candle)
        observation = MarketDataRawObservation.from_candle(
            candle,
            created_at=candle.received_at,
        )
        watermark = VersionedMarketDataWatermark.build(
            watermark=MarketDataWatermark.build(
                source=candle.source,
                pair=candle.pair,
                timeframe=candle.timeframe,
                high_water_event_time=_EXECUTION_TIME + timedelta(minutes=5),
                allowed_lateness_seconds=300,
                calculated_at=_EXECUTION_TIME + timedelta(minutes=6),
            ),
            version=1,
            policy_version="market-data-service-level-policy-v1",
            stored_at=_EXECUTION_TIME + timedelta(minutes=6),
        )
        try:
            with factory.begin() as session:
                SqlAlchemyMarketDataEventStore(session).stage_watermark(watermark)
            with factory() as session:
                ingestion = SqlAlchemyMarketDataIngestor(session).ingest(
                    observation=observation,
                    event=event,
                    decided_at=_EXECUTION_TIME + timedelta(minutes=7),
                )
            with factory() as session:
                queued = SqlAlchemyMarketDataReplayEnqueuer(session).enqueue(
                    decision_id=ingestion.decision_id,
                    requested_by="capacity-benchmark",
                    requested_at=_EXECUTION_TIME + timedelta(minutes=8),
                )
            with factory() as session:
                revision = SqlAlchemyMarketDataReplayRunner(session).apply(
                    queued.request.replay_id,
                    applied_at=_EXECUTION_TIME + timedelta(minutes=9),
                )
            if revision.revised_version != 1:
                raise RuntimeError("market-data replay workload produced an invalid revision")
        finally:
            engine.dispose()

    return execute


def _market_context_evaluation_workload() -> Callable[[], None]:
    source = "capacity-context-provider"
    requested_at = _EXECUTION_TIME + timedelta(minutes=2)
    counts = {
        Timeframe.HOUR_1: 24,
        Timeframe.HOURS_4: 18,
        Timeframe.DAY_1: 14,
    }
    windows: list[MarketDataWindowSnapshot] = []
    for timeframe, count in counts.items():
        for index in range(count):
            window_start = _EXECUTION_TIME - timeframe.duration * (count - index)
            window_end = window_start + timeframe.duration
            close_price = Decimal("100") + Decimal(index + 1)
            candle = OHLCVCandle(
                source=source,
                pair=_PAIR,
                timeframe=timeframe,
                open_time=window_start,
                close_time=window_end,
                received_at=window_end + timedelta(seconds=30),
                open_price=close_price,
                high_price=close_price + Decimal("1"),
                low_price=close_price - Decimal("1"),
                close_price=close_price,
                volume=Decimal("1000") + Decimal(index),
                is_closed=True,
            )
            event = MarketDataEvent.from_candle(candle)
            windows.append(
                MarketDataWindowSnapshot(
                    window_id=event.window_id,
                    version=2,
                    state=MarketDataWindowState.FINALIZED,
                    source=source,
                    pair=_PAIR,
                    timeframe=timeframe,
                    window_start=window_start,
                    window_end=window_end,
                    event_id=event.event_id,
                    payload_checksum=event.payload_checksum,
                    candle=candle,
                    created_at=window_end + timedelta(seconds=30),
                    finalized_at=window_end + timedelta(minutes=1),
                )
            )

    def execute() -> None:
        engine = create_database_engine("sqlite+pysqlite:///:memory:")
        DatabaseBase.metadata.create_all(engine)
        factory = create_session_factory(engine)
        try:
            with factory.begin() as session:
                store = SqlAlchemyMarketDataEventStore(session)
                for window in windows:
                    store.stage_window_version(window)
            with factory() as session:
                queued = SqlAlchemyMarketContextEvaluationEnqueuer(session).enqueue(
                    source=source,
                    pair=_PAIR,
                    as_of=_EXECUTION_TIME,
                    requested_at=requested_at,
                )
            payload = MarketContextEvaluationJobPayload.model_validate(queued.job.payload)
            assessment = SqlAlchemyMarketContextEvaluationRunner(factory).run(payload)
            if assessment.as_of != _EXECUTION_TIME or len(assessment.evidence) != 5:
                raise RuntimeError("market-context workload produced inconsistent output")
        finally:
            engine.dispose()

    return execute


def _alert_evaluation_workload() -> Callable[[], None]:
    source = "capacity-context-provider"
    input_checksum = "a" * 64
    evidence = MarketContextEvidence(
        feature_key="trend_slope_1h",
        timeframe=Timeframe.HOUR_1,
        value=Decimal("0.013"),
        calculation_version="trend-slope-v1",
        window_reference_checksums=("b" * 64,),
    )
    assessment = MarketRegimeAssessment(
        assessment_id=build_market_regime_assessment_id(
            source=source,
            pair=_PAIR,
            as_of=_EXECUTION_TIME,
            input_checksum=input_checksum,
            feature_set_version="market-context-features-v1",
            algorithm_version="market-regime-v1",
        ),
        source=source,
        pair=_PAIR,
        as_of=_EXECUTION_TIME,
        input_manifest_id=f"market-context-input-{input_checksum[:16]}",
        input_checksum=input_checksum,
        feature_set_version="market-context-features-v1",
        feature_set_checksum="c" * 64,
        feature_snapshot_id="market-context-features-dddddddddddddddd",
        feature_snapshot_checksum="d" * 64,
        algorithm_version="market-regime-v1",
        status=MarketContextAssessmentStatus.READY,
        trend=MarketTrendRegime.TRENDING_UP,
        volatility=MarketVolatilityRegime.HIGH,
        confidence=Decimal("0.82"),
        evidence=(evidence,),
        assessed_at=_EXECUTION_TIME + timedelta(minutes=1),
        expires_at=_EXECUTION_TIME + timedelta(hours=1),
    )
    rule = AlertRuleDefinition.build(
        rule_key="capacity-high-volatility-uptrend",
        rule_version=1,
        name="Capacity high-volatility uptrend",
        description="Measure deterministic alert evaluation capacity.",
        state=AlertRuleState.ENABLED,
        severity=AlertSeverity.WARNING,
        condition=MarketContextAlertCondition(
            trends=(MarketTrendRegime.TRENDING_UP,),
            volatilities=(MarketVolatilityRegime.HIGH,),
            minimum_confidence=Decimal("0.75"),
        ),
        expires_after_seconds=1800,
        deduplication_window_seconds=3600,
        cooldown_seconds=7200,
        created_at=_EXECUTION_TIME + timedelta(minutes=1),
    )
    payload = AlertEvaluationJobPayload.build(
        rule=rule,
        assessment=assessment,
        requested_at=_EXECUTION_TIME + timedelta(minutes=2),
    )

    def execute() -> None:
        outcome = evaluate_alert(rule=rule, source=payload.source)
        if (
            outcome.evaluation.disposition is not AlertEvaluationDisposition.PUBLISHED
            or outcome.draft is None
        ):
            raise RuntimeError("alert-evaluation workload did not publish its fixture")

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
            kind=BackgroundJobKind.MARKET_DATA_POLL,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("candles", 2), ("provider_count", 2)),
            execute=_market_data_poll_workload(),
        ),
        BackgroundJobWorkload(
            kind=BackgroundJobKind.MARKET_DATA_REPLAY,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("events", 1), ("window_revisions", 1)),
            execute=_market_data_replay_workload(),
        ),
        BackgroundJobWorkload(
            kind=BackgroundJobKind.MARKET_CONTEXT_EVALUATION,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("finalized_windows", 56), ("features", 5)),
            execute=_market_context_evaluation_workload(),
        ),
        BackgroundJobWorkload(
            kind=BackgroundJobKind.ALERT_EVALUATION,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("rules", 1), ("assessments", 1)),
            execute=_alert_evaluation_workload(),
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
