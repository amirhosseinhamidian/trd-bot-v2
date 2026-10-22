import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from scripts.verify_v0_3_installation import validate_release_database_url

from trd_bot.db import DatabaseBase
from trd_bot.release_installation import (
    LINEAGE_RELATIONS,
    V0_2_MIGRATION_REVISION,
    V0_3_MIGRATION_REVISION,
    ReleaseDatabaseState,
    ReleaseFreshInstallEvidence,
    ReleaseInstallationVerificationReport,
    ReleaseRelationFingerprint,
    ReleaseUpgradeEvidence,
    build_release_installation_report,
    empty_schema_checksum,
    fingerprint_strings,
    parse_release_installation_report,
    serialize_release_installation_report,
)

_NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)
_COMMIT_SHA = "c" * 40
_TARGET_TABLES = tuple(sorted(DatabaseBase.metadata.tables))
_TARGET_SCHEMA_CHECKSUM = fingerprint_strings(_TARGET_TABLES)
_INVENTORY_CHECKSUM = "d" * 64
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _lineage(*, populated: bool) -> tuple[ReleaseRelationFingerprint, ...]:
    values: list[ReleaseRelationFingerprint] = []
    for relation in LINEAGE_RELATIONS:
        identities: tuple[str, ...] = ()
        if populated and relation == "dataset_snapshots":
            identities = ("dataset-p6-06-upgrade-fixture-00000001",)
        if populated and relation == "research_experiments":
            identities = ("experiment-p6-06-upgrade-fixture-000001",)
        values.append(
            ReleaseRelationFingerprint(
                relation=relation,
                row_count=len(identities),
                identity_checksum=fingerprint_strings(identities),
                content_checksum=fingerprint_strings(identities),
            )
        )
    return tuple(values)


def _state(
    *,
    database_name: str,
    revision: str | None,
    target_schema: bool,
    lineage: tuple[ReleaseRelationFingerprint, ...],
    drift_free: bool,
) -> ReleaseDatabaseState:
    tables = _TARGET_TABLES if target_schema else ("dataset_snapshots", "research_experiments")
    return ReleaseDatabaseState(
        database_name=database_name,
        migration_revision=revision,
        application_table_count=len(tables),
        application_schema_checksum=fingerprint_strings(tables),
        lineage=lineage,
        schema_drift_free=drift_free,
    )


def _fresh_before() -> ReleaseDatabaseState:
    return ReleaseDatabaseState(
        database_name="trd_bot_v03_fresh_test",
        migration_revision=None,
        application_table_count=0,
        application_schema_checksum=empty_schema_checksum(),
        lineage=(),
        schema_drift_free=False,
    )


def _passing_report() -> ReleaseInstallationVerificationReport:
    upgrade_lineage = _lineage(populated=True)
    return build_release_installation_report(
        environment_label="unit-test",
        commit_sha=_COMMIT_SHA,
        generated_at=_NOW,
        expected_application_table_count=len(_TARGET_TABLES),
        target_schema_checksum=_TARGET_SCHEMA_CHECKSUM,
        release_inventory_checksum=_INVENTORY_CHECKSUM,
        release_security_boundary_passed=True,
        fresh_install=ReleaseFreshInstallEvidence(
            before=_fresh_before(),
            after=_state(
                database_name="trd_bot_v03_fresh_test",
                revision=V0_3_MIGRATION_REVISION,
                target_schema=True,
                lineage=_lineage(populated=False),
                drift_free=True,
            ),
        ),
        upgrade=ReleaseUpgradeEvidence(
            before=_state(
                database_name="trd_bot_v02_upgrade_test",
                revision=V0_2_MIGRATION_REVISION,
                target_schema=False,
                lineage=upgrade_lineage,
                drift_free=False,
            ),
            after=_state(
                database_name="trd_bot_v02_upgrade_test",
                revision=V0_3_MIGRATION_REVISION,
                target_schema=True,
                lineage=upgrade_lineage,
                drift_free=True,
            ),
            fixture_seeded=True,
        ),
    )


def test_release_installation_report_passes_and_round_trips() -> None:
    report = _passing_report()

    assert report.passed is True
    assert report.failure_reasons == ()
    assert report.source_migration_revision == V0_2_MIGRATION_REVISION
    assert report.target_migration_revision == V0_3_MIGRATION_REVISION
    assert (
        parse_release_installation_report(serialize_release_installation_report(report)) == report
    )
    assert len(report.report_checksum) == 64


def test_release_installation_fails_closed_for_nonempty_fresh_database() -> None:
    passing = _passing_report()
    bad_before = passing.fresh_install.before.model_copy(
        update={
            "application_table_count": 1,
            "application_schema_checksum": fingerprint_strings(("unexpected",)),
        }
    )
    report = build_release_installation_report(
        environment_label=passing.environment_label,
        commit_sha=passing.commit_sha,
        generated_at=passing.generated_at,
        expected_application_table_count=passing.expected_application_table_count,
        target_schema_checksum=passing.target_schema_checksum,
        release_inventory_checksum=passing.release_inventory_checksum,
        release_security_boundary_passed=True,
        fresh_install=passing.fresh_install.model_copy(update={"before": bad_before}),
        upgrade=passing.upgrade,
    )

    assert report.passed is False
    assert "fresh-install database was not empty" in report.failure_reasons


def test_release_installation_detects_lineage_identity_loss() -> None:
    passing = _passing_report()
    changed_lineage = list(passing.upgrade.after.lineage)
    changed_lineage[1] = changed_lineage[1].model_copy(
        update={
            "row_count": 0,
            "identity_checksum": fingerprint_strings(()),
            "content_checksum": fingerprint_strings(()),
        }
    )
    report = build_release_installation_report(
        environment_label=passing.environment_label,
        commit_sha=passing.commit_sha,
        generated_at=passing.generated_at,
        expected_application_table_count=passing.expected_application_table_count,
        target_schema_checksum=passing.target_schema_checksum,
        release_inventory_checksum=passing.release_inventory_checksum,
        release_security_boundary_passed=True,
        fresh_install=passing.fresh_install,
        upgrade=passing.upgrade.model_copy(
            update={
                "after": passing.upgrade.after.model_copy(
                    update={"lineage": tuple(changed_lineage)}
                )
            }
        ),
    )

    assert "upgrade did not preserve lineage row identities" in report.failure_reasons


def test_release_installation_detects_schema_drift_and_security_failure() -> None:
    passing = _passing_report()
    report = build_release_installation_report(
        environment_label=passing.environment_label,
        commit_sha=passing.commit_sha,
        generated_at=passing.generated_at,
        expected_application_table_count=passing.expected_application_table_count,
        target_schema_checksum=passing.target_schema_checksum,
        release_inventory_checksum=passing.release_inventory_checksum,
        release_security_boundary_passed=False,
        fresh_install=passing.fresh_install.model_copy(
            update={
                "after": passing.fresh_install.after.model_copy(update={"schema_drift_free": False})
            }
        ),
        upgrade=passing.upgrade,
    )

    assert "fresh install has Alembic schema drift" in report.failure_reasons
    assert "release security inventory failed after installation" in report.failure_reasons


def test_release_installation_parser_rejects_tampering() -> None:
    payload = json.loads(serialize_release_installation_report(_passing_report()))
    payload["upgrade"]["after"]["lineage"][1]["row_count"] = 0

    with pytest.raises(ValueError, match=r"failure reasons|checksum"):
        parse_release_installation_report(json.dumps(payload))


@pytest.mark.parametrize(
    ("database_url", "purpose"),
    [
        ("", "fresh"),
        ("sqlite:///trd_bot_v03_fresh_test", "fresh"),
        ("postgresql+psycopg://localhost/trd_bot", "fresh"),
        ("postgresql+psycopg://localhost/trd_bot_test", "fresh"),
        ("postgresql+psycopg://localhost/trd_bot_v03_test", "fresh"),
        ("postgresql+psycopg://localhost/trd_bot_v03_fresh", "fresh"),
        ("postgresql+psycopg://localhost/trd_bot_v02_upgrade", "upgrade"),
    ],
)
def test_release_installation_rejects_unsafe_database_targets(
    database_url: str,
    purpose: str,
) -> None:
    with pytest.raises(ValueError):
        validate_release_database_url(database_url, purpose=purpose)


def test_release_installation_accepts_dedicated_disposable_databases() -> None:
    fresh = "postgresql+psycopg://localhost/trd_bot_v03_fresh_test"
    upgrade = "postgresql+psycopg://localhost/trd_bot_v02_upgrade_bench"

    assert validate_release_database_url(fresh, purpose="fresh") == (
        fresh,
        "trd_bot_v03_fresh_test",
    )
    assert validate_release_database_url(upgrade, purpose="upgrade") == (
        upgrade,
        "trd_bot_v02_upgrade_bench",
    )


def test_target_schema_contract_is_deterministic() -> None:
    assert len(_TARGET_TABLES) == 55
    assert _TARGET_SCHEMA_CHECKSUM == (
        "0cf9dafa463f590936e316275a008ad8cf8e828a3d0e2bc27ed6a527ea6d3259"
    )


def test_installation_revisions_match_the_repository_migration_chain() -> None:
    script = ScriptDirectory.from_config(Config(str(_REPOSITORY_ROOT / "alembic.ini")))
    head = script.get_current_head()
    revisions = {revision.revision for revision in script.iterate_revisions(head, "base")}

    assert head == V0_3_MIGRATION_REVISION
    assert V0_2_MIGRATION_REVISION in revisions
