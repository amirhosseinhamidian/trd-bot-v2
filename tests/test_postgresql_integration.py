from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, inspect, text
from sqlalchemy.engine import make_url

import trd_bot.api.job_handlers as job_handlers
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.core.config import Settings
from trd_bot.db import (
    BackgroundJobConflictError,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyDatasetFileImportEnqueuer,
    SqlAlchemyDatasetFileStageRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemySimulatedPortfolioRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.models import BackgroundJobRow, DatasetFileStageRow, DatasetSnapshotRow
from trd_bot.domain import Timeframe, TradingPair
from trd_bot.jobs import (
    BackgroundJob,
    BackgroundJobBuilder,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode
from trd_bot.research import (
    DatasetColumnMapping,
    DatasetFileCommitRequest,
    DatasetFileImportJobPayload,
    DatasetFileImportService,
    DatasetFilePreviewRequest,
    DatasetFileStageBuilder,
    build_dataset_file_import_idempotency_key,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV = b"""timestamp,end,open,high,low,close,vol,closed
2026-08-20T10:00:00+00:00,2026-08-20T11:00:00+00:00,100,102,99,101,1500,true
2026-08-20T11:00:00+00:00,2026-08-20T12:00:00+00:00,101,103,100,102,1600,true
"""


def build_alembic_config(database_url: str) -> Config:
    """Build an Alembic configuration for an explicit database."""

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    return config


def get_test_database_url() -> str:
    """Return and validate the isolated PostgreSQL test database URL."""

    database_url = Settings().test_database_url

    if database_url is None:
        pytest.skip("TRD_BOT_TEST_DATABASE_URL is not configured")

    url = make_url(database_url)

    if url.get_backend_name() != "postgresql":
        raise AssertionError(
            "integration tests require a PostgreSQL database",
        )

    if url.database != "trd_bot_test":
        raise AssertionError(
            "integration migrations may run only against trd_bot_test",
        )

    return database_url


@pytest.mark.integration
def test_postgresql_connection_and_migrations() -> None:
    database_url = get_test_database_url()
    alembic_config = build_alembic_config(database_url)

    command.upgrade(alembic_config, "head")
    command.check(alembic_config)

    engine = create_database_engine(database_url)

    try:
        with engine.connect() as connection:
            assert connection.dialect.name == "postgresql"

            database_name = connection.scalar(text("SELECT current_database()"))

            assert database_name == "trd_bot_test"

        table_names = set(inspect(engine).get_table_names())

        assert {
            "alembic_version",
            "architecture_recommendations",
            "background_jobs",
            "candidate_journals",
            "candidate_projections",
            "dataset_file_stages",
            "dataset_snapshots",
            "experiment_executions",
            "market_data_connections",
            "market_data_imports",
            "monitoring_runtime_state",
            "optimization_executions",
            "portfolio_timeline_events",
            "research_experiments",
            "simulated_portfolios",
            "simulated_positions",
            "system_metric_samples",
            "walk_forward_executions",
            "walk_forward_runs",
        }.issubset(table_names)
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgresql_dataset_file_stage_survives_request_and_worker_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = get_test_database_url()
    command.upgrade(build_alembic_config(database_url), "head")
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)
    now = datetime.now(UTC)
    preview_request = DatasetFilePreviewRequest(
        name="PostgreSQL durable file dataset",
        source="manual-file",
        pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
        timeframe=Timeframe.HOUR_1,
        column_mapping=DatasetColumnMapping(
            open_time="timestamp",
            close_time="end",
            open_price="open",
            high_price="high",
            low_price="low",
            close_price="close",
            volume="vol",
            is_closed="closed",
        ),
    )
    preview = DatasetFileImportService().preview(
        file_name="candles.csv",
        content=CSV,
        request=preview_request,
    )
    commit_request = DatasetFileCommitRequest.model_validate(
        {
            **preview_request.model_dump(),
            "preview_checksum": preview.preview_checksum,
        }
    )
    stage = DatasetFileStageBuilder().build(
        file_name="candles.csv",
        content=CSV,
        request=commit_request,
        now=now,
    )
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.DATASET_FILE_IMPORT,
        payload=DatasetFileImportJobPayload(
            stage_id=stage.stage_id,
            file_checksum=stage.file_checksum,
        ).model_dump(mode="json"),
        idempotency_key=build_dataset_file_import_idempotency_key(stage),
        now=now,
    )
    dataset_id: str | None = None

    try:
        with factory() as session:
            submission = SqlAlchemyDatasetFileImportEnqueuer(session).enqueue(
                stage=stage,
                job=job,
            )

        with factory() as session:
            assert SqlAlchemyDatasetFileStageRepository(session).get(stage.stage_id) == stage
            completed = BackgroundJobWorker(
                repository=SqlAlchemyBackgroundJobRepository(session),
                handlers=build_background_job_handler_registry(),
                worker_id="postgresql-dataset-file-worker",
                lease_duration=timedelta(minutes=5),
            ).run_once()

        assert completed is not None
        assert completed.job_id == submission.job.job_id
        assert completed.status is BackgroundJobStatus.SUCCEEDED
        assert completed.result_reference is not None
        dataset_id = completed.result_reference

        with factory() as session:
            stored = SqlAlchemyDatasetRepository(session).get(dataset_id)
            assert stored is not None
            assert stored.checksum == preview.preview_checksum
            assert SqlAlchemyDatasetFileStageRepository(session).get(stage.stage_id) is None
    finally:
        with factory() as session:
            session.execute(
                delete(DatasetFileStageRow).where(DatasetFileStageRow.stage_id == stage.stage_id)
            )
            session.execute(delete(BackgroundJobRow).where(BackgroundJobRow.job_id == job.job_id))
            if dataset_id is not None:
                session.execute(
                    delete(DatasetSnapshotRow).where(DatasetSnapshotRow.dataset_id == dataset_id)
                )
            session.commit()
        engine.dispose()


@pytest.mark.integration
def test_postgresql_background_job_races_and_expired_lease_recovery() -> None:
    database_url = get_test_database_url()
    alembic_config = build_alembic_config(database_url)
    command.upgrade(alembic_config, "head")

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    idempotency_key = f"release-race-{uuid4().hex}"
    queued_at = datetime.now(UTC)
    jobs = tuple(
        BackgroundJobBuilder().build(
            kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
            payload={"execution_id": f"release-race-execution-{index}"},
            idempotency_key=idempotency_key,
            now=queued_at,
        )
        for index in range(2)
    )

    try:
        with factory() as session:
            session.execute(delete(BackgroundJobRow))
            session.commit()

        enqueue_barrier = Barrier(2)

        def enqueue(job: BackgroundJob) -> tuple[BackgroundJob, bool]:
            with factory() as session:
                enqueue_barrier.wait(timeout=10)
                return SqlAlchemyBackgroundJobRepository(session).enqueue(job)

        with ThreadPoolExecutor(max_workers=2) as executor:
            enqueue_results = tuple(executor.map(enqueue, jobs))

        assert sum(created for _, created in enqueue_results) == 1
        assert len({stored.job_id for stored, _ in enqueue_results}) == 1
        stored_job_id = enqueue_results[0][0].job_id

        claim_barrier = Barrier(2)

        def claim(worker_id: str) -> BackgroundJob | None:
            with factory() as session:
                claim_barrier.wait(timeout=10)
                return SqlAlchemyBackgroundJobRepository(session).claim_next(
                    worker_id=worker_id,
                    lease_duration=timedelta(seconds=30),
                    now=queued_at,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            claim_results = tuple(executor.map(claim, ("release-worker-a", "release-worker-b")))

        claimed = tuple(job for job in claim_results if job is not None)
        assert len(claimed) == 1
        assert claimed[0].job_id == stored_job_id
        assert claimed[0].attempt_count == 1
        stale_worker_id = claimed[0].lease_owner
        assert stale_worker_id is not None

        with factory() as session:
            reclaimed = SqlAlchemyBackgroundJobRepository(session).claim_next(
                worker_id="release-recovery-worker",
                lease_duration=timedelta(seconds=30),
                now=queued_at + timedelta(seconds=31),
            )

        assert reclaimed is not None
        assert reclaimed.job_id == stored_job_id
        assert reclaimed.attempt_count == 2
        assert reclaimed.lease_owner == "release-recovery-worker"

        with factory() as session, pytest.raises(BackgroundJobConflictError):
            SqlAlchemyBackgroundJobRepository(session).succeed(
                job_id=stored_job_id,
                worker_id=stale_worker_id,
                now=queued_at + timedelta(seconds=32),
            )
    finally:
        with factory() as session:
            session.execute(delete(BackgroundJobRow))
            session.commit()
        engine.dispose()


@pytest.mark.integration
def test_simulated_portfolio_with_timeline_persists_in_postgresql() -> None:
    database_url = get_test_database_url()
    alembic_config = build_alembic_config(database_url)

    command.upgrade(alembic_config, "head")

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    portfolio = SimulatedPortfolioLedger().create(
        mode=SimulationMode.PAPER,
        dataset_id="dataset-postgresql-portfolio-test",
        starting_cash=Decimal("10000"),
        fee_rate=Decimal("0.001"),
        created_at=datetime.now(UTC),
    )

    try:
        with factory() as session:
            repository = SqlAlchemySimulatedPortfolioRepository(session)

            repository.save(portfolio)

            stored = repository.get(portfolio.portfolio_id)

            assert stored == portfolio
            assert repository.count_timeline(portfolio.portfolio_id) == 1
    finally:
        engine.dispose()
