from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, literal, select
from sqlalchemy.orm import Session

from trd_bot.core.config import Settings
from trd_bot.db import (
    DatabaseBase,
    DatasetSnapshotRow,
    ResearchExperimentRow,
    WalkForwardRunRow,
    create_database_engine,
    create_session_factory,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = datetime(2026, 8, 22, 10, tzinfo=UTC)


def build_alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_settings_load_database_url_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = "sqlite+pysqlite:///./custom-test.db"
    monkeypatch.setenv("TRD_BOT_DATABASE_URL", database_url)

    assert Settings().database_url == database_url


def test_database_engine_rejects_empty_url() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        create_database_engine("  ")


def test_session_factory_executes_sqlite_query() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    factory = create_session_factory(engine)

    try:
        with factory() as session:
            assert session.scalar(select(literal(1))) == 1
    finally:
        engine.dispose()


def test_database_metadata_contains_research_tables() -> None:
    assert set(DatabaseBase.metadata.tables) == {
        "dataset_snapshots",
        "research_experiments",
        "walk_forward_runs",
    }


def test_orm_rows_can_be_persisted_and_retrieved() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    dataset = DatasetSnapshotRow(
        dataset_id="dataset-0000000000000001",
        created_at=CREATED_AT,
        source="test-exchange",
        base_asset="BTC",
        quote_asset="USDT",
        market_type="spot",
        timeframe="1h",
        start_time=CREATED_AT,
        end_time=CREATED_AT,
        candle_count=1,
        checksum="a" * 64,
        payload_json='{"dataset_id":"dataset-0000000000000001"}',
    )
    experiment = ResearchExperimentRow(
        experiment_id="experiment-0000000000000001",
        created_at=CREATED_AT,
        dataset_id=dataset.dataset_id,
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        horizon_candles=1,
        payload_json='{"experiment_id":"experiment-0000000000000001"}',
    )
    run = WalkForwardRunRow(
        execution_id="walk-forward-execution-0000000000000001",
        created_at=CREATED_AT,
        source_dataset_id=dataset.dataset_id,
        plan_id="walk-forward-0000000000000001",
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        horizon_candles=1,
        payload_json=('{"execution_id":"walk-forward-execution-0000000000000001"}'),
    )

    try:
        with factory.begin() as session:
            session.add_all([dataset, experiment, run])

        with factory() as session:
            assert session.get(DatasetSnapshotRow, dataset.dataset_id) is not None
            assert session.get(ResearchExperimentRow, experiment.experiment_id) is not None
            stored_run = session.get(WalkForwardRunRow, run.execution_id)
            assert stored_run is not None
            assert stored_run.strategy_name == "ema-crossover"
    finally:
        engine.dispose()


def test_migration_upgrades_matches_metadata_and_downgrades(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    config = build_alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_database_engine(database_url)
    try:
        table_names = set(inspect(engine).get_table_names())
        assert {
            "alembic_version",
            "dataset_snapshots",
            "research_experiments",
            "walk_forward_runs",
        }.issubset(table_names)
        command.check(config)
    finally:
        engine.dispose()

    command.downgrade(config, "base")

    downgraded_engine = create_database_engine(database_url)
    try:
        downgraded_tables = set(inspect(downgraded_engine).get_table_names())
        assert "dataset_snapshots" not in downgraded_tables
        assert "research_experiments" not in downgraded_tables
        assert "walk_forward_runs" not in downgraded_tables
    finally:
        downgraded_engine.dispose()


def test_session_factory_returns_sqlalchemy_sessions() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    factory = create_session_factory(engine)

    try:
        with factory() as session:
            assert isinstance(session, Session)
    finally:
        engine.dispose()
