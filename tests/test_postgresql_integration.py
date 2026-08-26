from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from trd_bot.core.config import Settings
from trd_bot.db import create_database_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
            "dataset_snapshots",
            "experiment_executions",
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
