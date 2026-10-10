from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

import trd_bot.api.job_handlers as job_handlers
from trd_bot.api.background_jobs import (
    run_experiment_execution_with_session_factory,
)
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.core.config import Settings
from trd_bot.db import (
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentExecutionEnqueuer,
    SqlAlchemyExperimentExecutionRepository,
    SqlAlchemyExperimentRegistry,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.candidate_journal_repositories import (
    SqlAlchemyCandidateJournalRepository,
)
from trd_bot.db.candidate_projection_repositories import (
    SqlAlchemyCandidateProjectionRepository,
)
from trd_bot.db.simulated_portfolio_repositories import (
    SqlAlchemySimulatedPortfolioRepository,
)
from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.jobs import (
    BackgroundJobBuilder,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)
from trd_bot.research import (
    DatasetBuilder,
    EMACrossoverExecutionParameters,
    ExperimentExecutionBuilder,
    ExperimentExecutionJobPayload,
    ExperimentExecutionStatus,
    build_experiment_execution_idempotency_key,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_test_database_url() -> str:
    database_url = Settings().test_database_url

    if database_url is None:
        pytest.skip("TRD_BOT_TEST_DATABASE_URL is not configured")

    url = make_url(database_url)

    if url.get_backend_name() != "postgresql":
        raise AssertionError("integration tests require a PostgreSQL database")

    if url.database != "trd_bot_test":
        raise AssertionError("integration tests may run only against trd_bot_test")

    return database_url


def build_alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    return config


def build_dataset_candles() -> tuple[OHLCVCandle, ...]:
    start_time = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[OHLCVCandle] = []

    for index in range(60):
        open_time = start_time + timedelta(hours=index)
        close_time = open_time + timedelta(hours=1) - timedelta(milliseconds=1)

        close_price = 200 - index if index < 30 else 170 + (index - 30) * 2

        close_decimal = Decimal(str(close_price))
        open_price = close_decimal - Decimal("0.5")
        high_price = max(
            open_price,
            close_decimal,
        ) + Decimal("1")
        low_price = min(
            open_price,
            close_decimal,
        ) - Decimal("1")

        candles.append(
            OHLCVCandle.model_validate(
                {
                    "source": "postgresql-integration",
                    "pair": {
                        "base_asset": "BTC",
                        "quote_asset": "USDT",
                        "market_type": "spot",
                    },
                    "timeframe": "1h",
                    "open_time": open_time,
                    "close_time": close_time,
                    "received_at": close_time,
                    "open_price": open_price,
                    "high_price": high_price,
                    "low_price": low_price,
                    "close_price": close_decimal,
                    "volume": Decimal(str(1000 + index)),
                    "is_closed": True,
                }
            )
        )

    return tuple(candles)


def clean_execution_tables(database_url: str) -> None:
    engine = create_database_engine(database_url)

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE TABLE "
                    "candidate_projections, "
                    "candidate_journals, "
                    "portfolio_timeline_events, "
                    "simulated_positions, "
                    "simulated_portfolios, "
                    "background_jobs, "
                    "experiment_executions, "
                    "research_experiments, "
                    "dataset_snapshots "
                    "CASCADE"
                )
            )
    finally:
        engine.dispose()


@pytest.mark.integration
def test_background_execution_lifecycle_with_postgresql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = get_test_database_url()

    command.upgrade(
        build_alembic_config(database_url),
        "head",
    )

    clean_execution_tables(database_url)

    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)

    try:
        dataset = DatasetBuilder().build(
            name="PostgreSQL execution dataset",
            candles=build_dataset_candles(),
        )

        queued = ExperimentExecutionBuilder().build(
            dataset_id=dataset.dataset_id,
            parameters=EMACrossoverExecutionParameters(
                fast_period=9,
                slow_period=21,
                horizon_candles=1,
                starting_balance=Decimal("10000"),
                allocation_fraction=Decimal("0.10"),
                fee_rate=Decimal("0.001"),
                slippage_rate=Decimal("0.0005"),
            ),
        )

        with session_factory() as session:
            SqlAlchemyDatasetRepository(session).save(dataset)
            job = BackgroundJobBuilder().build(
                kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
                payload=ExperimentExecutionJobPayload(
                    execution_id=queued.execution_id,
                ).model_dump(mode="json"),
                idempotency_key=build_experiment_execution_idempotency_key(queued),
                now=queued.created_at,
            )
            submission = SqlAlchemyExperimentExecutionEnqueuer(session).enqueue(
                execution=queued,
                job=job,
            )

        monkeypatch.setattr(job_handlers, "get_session_factory", lambda: session_factory)
        with session_factory() as session:
            completed_job = BackgroundJobWorker(
                repository=SqlAlchemyBackgroundJobRepository(session),
                handlers=build_background_job_handler_registry(),
                worker_id="postgresql-experiment-worker",
                lease_duration=timedelta(minutes=5),
            ).run_once()

        assert completed_job is not None
        assert completed_job.job_id == submission.job.job_id
        assert completed_job.status is BackgroundJobStatus.SUCCEEDED
        assert completed_job.result_reference == queued.execution_id

        with session_factory() as session:
            execution_repository = SqlAlchemyExperimentExecutionRepository(session)

            experiment_registry = SqlAlchemyExperimentRegistry(session)

            completed = execution_repository.get(queued.execution_id)

            assert completed is not None
            assert completed.status is ExperimentExecutionStatus.SUCCEEDED
            assert completed.progress_percent == 100
            assert completed.started_at is not None
            assert completed.finished_at is not None
            assert completed.experiment_id is not None
            assert completed.error_code is None
            assert completed.error_message is None

            experiment = experiment_registry.get(completed.experiment_id)

            assert experiment is not None
            assert experiment.strategy_fingerprint is not None
            assert experiment.dataset_id == dataset.dataset_id
            assert experiment.strategy_name == "ema-crossover"

            journal_repository = SqlAlchemyCandidateJournalRepository(session)
            portfolio_repository = SqlAlchemySimulatedPortfolioRepository(session)
            projection_repository = SqlAlchemyCandidateProjectionRepository(session)

            # The production background runtime must continue beyond Experiment
            # persistence into Candidate -> Risk -> Portfolio persistence.
            assert journal_repository.count() == 1
            assert portfolio_repository.count() == 1

            journals = journal_repository.list_by_dataset(
                dataset_id=dataset.dataset_id,
                limit=10,
                offset=0,
            )
            assert len(journals) == 1

            journal = journals[0]
            portfolio = portfolio_repository.get(journal.portfolio_id)

            assert portfolio is not None
            assert portfolio.dataset_id == dataset.dataset_id

            projections = projection_repository.list_page(
                limit=100,
                offset=0,
            )

            assert projections
            assert all(
                projection.candidate.dataset_id == dataset.dataset_id for projection in projections
            )
            assert all(
                projection.candidate.experiment_id == completed.experiment_id
                for projection in projections
            )

            first_experiment_id = completed.experiment_id
            first_journal_ids = tuple(
                journal.journal_id
                for journal in journal_repository.list_by_dataset(
                    dataset_id=dataset.dataset_id,
                    limit=100,
                    offset=0,
                )
            )
            first_portfolio_ids = tuple(
                portfolio.portfolio_id
                for portfolio in portfolio_repository.list_page(
                    limit=100,
                    offset=0,
                )
            )
            first_projection_ids = tuple(
                projection.candidate.candidate_id
                for projection in projection_repository.list_page(
                    limit=100,
                    offset=0,
                )
            )

        # Retry the exact same completed execution through the production
        # background runtime.
        run_experiment_execution_with_session_factory(
            queued.execution_id,
            session_factory,
        )

        with session_factory() as session:
            execution_repository = SqlAlchemyExperimentExecutionRepository(session)
            journal_repository = SqlAlchemyCandidateJournalRepository(session)
            portfolio_repository = SqlAlchemySimulatedPortfolioRepository(session)
            projection_repository = SqlAlchemyCandidateProjectionRepository(session)

            retried = execution_repository.get(queued.execution_id)

            assert retried is not None
            assert retried.status is ExperimentExecutionStatus.SUCCEEDED
            assert retried.experiment_id == first_experiment_id

            retry_journal_ids = tuple(
                journal.journal_id
                for journal in journal_repository.list_by_dataset(
                    dataset_id=dataset.dataset_id,
                    limit=100,
                    offset=0,
                )
            )
            retry_portfolio_ids = tuple(
                portfolio.portfolio_id
                for portfolio in portfolio_repository.list_page(
                    limit=100,
                    offset=0,
                )
            )
            retry_projection_ids = tuple(
                projection.candidate.candidate_id
                for projection in projection_repository.list_page(
                    limit=100,
                    offset=0,
                )
            )

            assert retry_journal_ids == first_journal_ids
            assert retry_portfolio_ids == first_portfolio_ids
            assert retry_projection_ids == first_projection_ids

            assert journal_repository.count() == len(first_journal_ids)
            assert portfolio_repository.count() == len(first_portfolio_ids)
            assert projection_repository.count() == len(first_projection_ids)

    finally:
        clean_execution_tables(database_url)
        engine.dispose()
