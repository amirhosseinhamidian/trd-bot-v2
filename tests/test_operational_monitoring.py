from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain.market_data import MarketType, Timeframe, TradingPair
from trd_bot.jobs import BackgroundJobBuilder, BackgroundJobKind
from trd_bot.market_data import (
    InMemoryMarketDataConnectionRepository,
    MarketDataConnection,
    MarketDataConnectionHealth,
)
from trd_bot.market_data.import_history import (
    InMemoryMarketDataImportRepository,
    MarketDataImportRecord,
    MarketDataImportStatus,
)
from trd_bot.market_data.providers import MarketDataProviderErrorCode
from trd_bot.monitoring import (
    InMemoryArchitectureRecommendationRepository,
    InMemorySystemMetricRepository,
    MonitoringOverallStatus,
    MonitoringSummaryBuilder,
)

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


def build_import(*, import_id: str, status: MarketDataImportStatus) -> MarketDataImportRecord:
    failed = status is MarketDataImportStatus.FAILED
    return MarketDataImportRecord(
        import_id=import_id,
        connection_id="connection-nobitex",
        provider_id="nobitex-public",
        dataset_name="BTC hourly",
        pair=TradingPair(
            base_asset="BTC",
            quote_asset="USDT",
            market_type=MarketType.SPOT,
        ),
        timeframe=Timeframe.HOUR_1,
        requested_start_time=NOW - timedelta(hours=2),
        requested_end_time=NOW - timedelta(hours=1),
        created_at=NOW - timedelta(minutes=8 if failed else 10),
        completed_at=NOW - timedelta(minutes=7 if failed else 9),
        status=status,
        candle_count=0 if failed else 1,
        dataset_id=None if failed else "dataset-operations-test",
        error_code="provider_unavailable" if failed else None,
        error_message="provider request failed" if failed else None,
    )


def test_operational_summary_surfaces_provider_import_and_stuck_job_failures() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    connections = InMemoryMarketDataConnectionRepository()
    connections.save(
        MarketDataConnection(
            connection_id="connection-nobitex",
            provider_id="nobitex-public",
            display_name="Nobitex public",
            health_status=MarketDataConnectionHealth.UNHEALTHY,
            created_at=NOW - timedelta(days=1),
            updated_at=NOW - timedelta(minutes=6),
            last_tested_at=NOW - timedelta(minutes=6),
            last_error_code=MarketDataProviderErrorCode.UNAVAILABLE,
            last_error="provider health check failed",
        )
    )
    imports = InMemoryMarketDataImportRepository()
    imports.save(build_import(import_id="import-success", status=MarketDataImportStatus.SUCCEEDED))
    imports.save(build_import(import_id="import-failed", status=MarketDataImportStatus.FAILED))

    try:
        with factory() as session:
            jobs = SqlAlchemyBackgroundJobRepository(session)
            failed, _ = jobs.enqueue(
                BackgroundJobBuilder().build(
                    kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
                    payload={"execution_id": "execution-failed"},
                    now=NOW - timedelta(minutes=5),
                )
            )
            jobs.claim_next(
                worker_id="worker-b",
                lease_duration=timedelta(minutes=10),
                now=NOW - timedelta(minutes=4),
            )
            jobs.fail(
                job_id=failed.job_id,
                worker_id="worker-b",
                error_code="job_handler_failed",
                error_message="background job handler failed",
                retryable=False,
                now=NOW - timedelta(minutes=3),
            )
            stuck, _ = jobs.enqueue(
                BackgroundJobBuilder().build(
                    kind=BackgroundJobKind.MARKET_DATA_IMPORT,
                    payload={"import_id": "stuck"},
                    now=NOW - timedelta(minutes=2),
                )
            )
            jobs.claim_next(
                worker_id="stale-worker",
                lease_duration=timedelta(seconds=30),
                now=NOW - timedelta(minutes=1),
            )

            summary = MonitoringSummaryBuilder().build(
                metrics=InMemorySystemMetricRepository(),
                recommendations=InMemoryArchitectureRecommendationRepository(),
                jobs=jobs,
                connections=connections,
                imports=imports,
                generated_at=NOW,
            )

            assert summary.overall_status is MonitoringOverallStatus.CRITICAL
            assert summary.operations is not None
            assert summary.operations.connections.unhealthy_count == 1
            assert summary.operations.connections.latest_error_code == "provider_unavailable"
            assert summary.operations.imports.failure_rate == Decimal("0.5")
            assert summary.operations.imports.latest_failure_code == "provider_unavailable"
            assert summary.operations.jobs.running_count == 1
            assert summary.operations.jobs.stuck_count == 1
            assert summary.operations.jobs.failed_count == 1
            assert summary.operations.jobs.failure_reasons[0].error_code == "job_handler_failed"
            assert {job.job_id for job in summary.operations.jobs.recent_jobs} == {
                stuck.job_id,
                failed.job_id,
            }
            assert all(
                "error_message" not in job.model_dump()
                for job in summary.operations.jobs.recent_jobs
            )
    finally:
        engine.dispose()


def test_empty_operational_summary_has_no_misleading_rates_or_durations() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with factory() as session:
            summary = MonitoringSummaryBuilder().build(
                metrics=InMemorySystemMetricRepository(),
                recommendations=InMemoryArchitectureRecommendationRepository(),
                jobs=SqlAlchemyBackgroundJobRepository(session),
                connections=InMemoryMarketDataConnectionRepository(),
                imports=InMemoryMarketDataImportRepository(),
                generated_at=NOW,
            )

            assert summary.overall_status is MonitoringOverallStatus.HEALTHY
            assert summary.operations is not None
            assert summary.operations.imports.failure_rate is None
            assert summary.operations.jobs.average_duration_seconds is None
            assert summary.operations.jobs.recent_jobs == ()
    finally:
        engine.dispose()
