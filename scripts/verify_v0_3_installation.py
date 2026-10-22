#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.engine import Engine, make_url

from trd_bot.db import DatabaseBase, create_database_engine
from trd_bot.release_hardening import build_release_hardening_report
from trd_bot.release_installation import (
    LINEAGE_RELATIONS,
    V0_2_MIGRATION_REVISION,
    ReleaseDatabaseState,
    ReleaseFreshInstallEvidence,
    ReleaseRelationFingerprint,
    ReleaseUpgradeEvidence,
    build_release_installation_report,
    fingerprint_strings,
    serialize_release_installation_report,
)

_ROOT = Path(__file__).resolve().parents[1]
_ALEMBIC_VERSION_TABLE = "alembic_version"
_LINEAGE_PRIMARY_KEYS = {
    "candidate_journals": "journal_id",
    "dataset_snapshots": "dataset_id",
    "research_experiments": "experiment_id",
    "simulated_portfolios": "portfolio_id",
    "simulated_positions": "position_id",
}
_FIXTURE_DATASET_ID = "dataset-p6-06-upgrade-fixture-00000001"
_FIXTURE_EXPERIMENT_ID = "experiment-p6-06-upgrade-fixture-000001"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a clean v0.3 fresh install and an in-place v0.2-to-v0.3 "
            "upgrade on two dedicated disposable PostgreSQL databases."
        )
    )
    parser.add_argument("--fresh-database-url", required=True)
    parser.add_argument("--upgrade-database-url", required=True)
    parser.add_argument("--confirm-fresh-database", required=True)
    parser.add_argument("--confirm-upgrade-database", required=True)
    parser.add_argument("--seed-upgrade-fixture", action="store_true")
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def validate_release_database_url(value: str, *, purpose: str) -> tuple[str, str]:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{purpose} database URL is required")
    url = make_url(normalized)
    database_name = url.database or ""
    if url.get_backend_name() != "postgresql":
        raise ValueError(f"{purpose} verification requires PostgreSQL")
    lowered = database_name.casefold()
    if purpose not in lowered or not ({"test", "bench"} & set(lowered.split("_"))):
        raise ValueError(
            f"{purpose} database name must contain '{purpose}' and a test or bench marker"
        )
    if database_name in {"postgres", "template0", "template1", "trd_bot", "trd_bot_test"}:
        raise ValueError(f"{purpose} verification requires a dedicated disposable database")
    return normalized, database_name


def _git_identity() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise ValueError("release installation verification requires a clean worktree")
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().casefold()


def _alembic_config(database_url: str) -> Config:
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _migration_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        heads = tuple(sorted(MigrationContext.configure(connection).get_current_heads()))
    if len(heads) > 1:
        raise ValueError(f"release verification database has multiple migration heads: {heads}")
    return heads[0] if heads else None


def _application_tables(engine: Engine) -> tuple[str, ...]:
    with engine.connect() as connection:
        names = inspect(connection).get_table_names(schema="public")
    return tuple(sorted(name for name in names if name != _ALEMBIC_VERSION_TABLE))


def _relation_fingerprint(engine: Engine, relation: str) -> ReleaseRelationFingerprint:
    metadata = MetaData()
    with engine.connect() as connection:
        table = Table(relation, metadata, autoload_with=connection)
        primary_key = _LINEAGE_PRIMARY_KEYS[relation]
        rows = tuple(connection.execute(select(table).order_by(table.c[primary_key])).mappings())
    identities = tuple(str(row[primary_key]) for row in rows)
    canonical_rows = tuple(
        json.dumps(dict(row), default=str, sort_keys=True, separators=(",", ":")) for row in rows
    )
    return ReleaseRelationFingerprint(
        relation=relation,
        row_count=len(identities),
        identity_checksum=fingerprint_strings(identities),
        content_checksum=fingerprint_strings(canonical_rows),
    )


def collect_database_state(
    engine: Engine,
    *,
    database_name: str,
    schema_drift_free: bool,
) -> ReleaseDatabaseState:
    tables = _application_tables(engine)
    available = set(tables)
    lineage = tuple(
        _relation_fingerprint(engine, relation)
        for relation in LINEAGE_RELATIONS
        if relation in available
    )
    return ReleaseDatabaseState(
        database_name=database_name,
        migration_revision=_migration_revision(engine),
        application_table_count=len(tables),
        application_schema_checksum=fingerprint_strings(tables),
        lineage=lineage,
        schema_drift_free=schema_drift_free,
    )


def _assert_fresh_precondition(state: ReleaseDatabaseState) -> None:
    if state.migration_revision is not None or state.application_table_count or state.lineage:
        raise ValueError("fresh verification database must have an empty public schema")


def _assert_upgrade_precondition(state: ReleaseDatabaseState) -> None:
    if state.migration_revision != V0_2_MIGRATION_REVISION:
        raise ValueError(f"upgrade verification database must start at {V0_2_MIGRATION_REVISION}")
    if tuple(item.relation for item in state.lineage) != LINEAGE_RELATIONS:
        raise ValueError("upgrade database is missing a v0.2 lineage relation")


def _seed_upgrade_fixture(engine: Engine) -> None:
    metadata = MetaData()
    with engine.begin() as connection:
        datasets = Table("dataset_snapshots", metadata, autoload_with=connection)
        experiments = Table("research_experiments", metadata, autoload_with=connection)
        existing_dataset = connection.scalar(
            select(datasets.c.dataset_id).where(datasets.c.dataset_id == _FIXTURE_DATASET_ID)
        )
        existing_experiment = connection.scalar(
            select(experiments.c.experiment_id).where(
                experiments.c.experiment_id == _FIXTURE_EXPERIMENT_ID
            )
        )
        if existing_dataset is not None or existing_experiment is not None:
            raise ValueError("P6-06 upgrade fixture already exists")
        created_at = datetime(2026, 1, 1, tzinfo=UTC)
        connection.execute(
            datasets.insert().values(
                dataset_id=_FIXTURE_DATASET_ID,
                created_at=created_at,
                source="p6-06-upgrade-fixture",
                base_asset="BTC",
                quote_asset="USDT",
                market_type="spot",
                timeframe="1h",
                start_time=created_at,
                end_time=datetime(2026, 1, 1, 1, tzinfo=UTC),
                candle_count=1,
                checksum=hashlib.sha256(b"p6-06-upgrade-fixture").hexdigest(),
                payload_json=json.dumps({"fixture": "p6-06", "candles": 1}),
            )
        )
        connection.execute(
            experiments.insert().values(
                experiment_id=_FIXTURE_EXPERIMENT_ID,
                created_at=created_at,
                dataset_id=_FIXTURE_DATASET_ID,
                strategy_name="ema-crossover",
                strategy_version="1.0.0",
                horizon_candles=1,
                payload_json=json.dumps({"fixture": "p6-06"}),
            )
        )


def _upgrade_and_check(database_url: str) -> None:
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    command.check(config)


def main() -> int:
    args = build_parser().parse_args()
    if args.output.exists():
        raise FileExistsError(f"output file already exists: {args.output}")
    fresh_url, fresh_name = validate_release_database_url(args.fresh_database_url, purpose="fresh")
    upgrade_url, upgrade_name = validate_release_database_url(
        args.upgrade_database_url, purpose="upgrade"
    )
    if fresh_url == upgrade_url or fresh_name == upgrade_name:
        raise ValueError("fresh and upgrade verification databases must be distinct")
    if args.confirm_fresh_database != fresh_name:
        raise ValueError("fresh database confirmation does not match its URL")
    if args.confirm_upgrade_database != upgrade_name:
        raise ValueError("upgrade database confirmation does not match its URL")

    commit_sha = _git_identity()
    fresh_engine = create_database_engine(fresh_url)
    upgrade_engine = create_database_engine(upgrade_url)
    try:
        fresh_before = collect_database_state(
            fresh_engine,
            database_name=fresh_name,
            schema_drift_free=False,
        )
        upgrade_before = collect_database_state(
            upgrade_engine,
            database_name=upgrade_name,
            schema_drift_free=False,
        )
        _assert_fresh_precondition(fresh_before)
        _assert_upgrade_precondition(upgrade_before)
        if args.seed_upgrade_fixture:
            _seed_upgrade_fixture(upgrade_engine)
            upgrade_before = collect_database_state(
                upgrade_engine,
                database_name=upgrade_name,
                schema_drift_free=False,
            )
        fresh_engine.dispose()
        upgrade_engine.dispose()

        _upgrade_and_check(fresh_url)
        _upgrade_and_check(upgrade_url)

        fresh_engine = create_database_engine(fresh_url)
        upgrade_engine = create_database_engine(upgrade_url)
        fresh_after = collect_database_state(
            fresh_engine,
            database_name=fresh_name,
            schema_drift_free=True,
        )
        upgrade_after = collect_database_state(
            upgrade_engine,
            database_name=upgrade_name,
            schema_drift_free=True,
        )
    finally:
        fresh_engine.dispose()
        upgrade_engine.dispose()

    inventory_report = build_release_hardening_report(_ROOT)
    target_tables = tuple(sorted(DatabaseBase.metadata.tables))
    report = build_release_installation_report(
        environment_label=args.environment_label,
        commit_sha=commit_sha,
        generated_at=datetime.now(UTC),
        expected_application_table_count=len(target_tables),
        target_schema_checksum=fingerprint_strings(target_tables),
        release_inventory_checksum=inventory_report.inventory.definition_checksum,
        release_security_boundary_passed=inventory_report.passed,
        fresh_install=ReleaseFreshInstallEvidence(before=fresh_before, after=fresh_after),
        upgrade=ReleaseUpgradeEvidence(
            before=upgrade_before,
            after=upgrade_after,
            fixture_seeded=args.seed_upgrade_fixture,
        ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output_file:
        output_file.write(serialize_release_installation_report(report) + "\n")
    print(
        json.dumps(
            {
                "commit_sha": report.commit_sha,
                "failure_reasons": list(report.failure_reasons),
                "fresh_database": fresh_name,
                "passed": report.passed,
                "report_checksum": report.report_checksum,
                "target_revision": report.target_migration_revision,
                "upgrade_database": upgrade_name,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
