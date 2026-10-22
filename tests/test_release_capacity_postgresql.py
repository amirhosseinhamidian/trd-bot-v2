from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from scripts.benchmark_v0_3_release_capacity import run_release_capacity_benchmark
from sqlalchemy.engine import make_url

from trd_bot.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_test_database_url() -> str:
    database_url = Settings().test_database_url
    if database_url is None:
        pytest.skip("TRD_BOT_TEST_DATABASE_URL is not configured")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or url.database != "trd_bot_test":
        raise AssertionError("release capacity integration requires PostgreSQL trd_bot_test")
    return database_url


@pytest.mark.integration
def test_release_capacity_benchmark_exercises_postgresql_overload_and_recovery() -> None:
    database_url = get_test_database_url()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    report = run_release_capacity_benchmark(
        database_url=database_url,
        environment_label="postgresql-integration",
        commit_sha="b" * 40,
        job_count=100,
        contention_workers=8,
    )

    assert report.passed is True
    assert report.failure_reasons == ()
    assert report.observations.overload_depth_observed == 100
    assert report.observations.succeeded_jobs == 100
    assert report.observations.cleanup_verified is True
