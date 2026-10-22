import hashlib
import json
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RELEASE_INSTALLATION_SCHEMA_VERSION = "v0.3-release-installation-verification-v1"
V0_2_RELEASE_VERSION = "0.2.0"
V0_2_MIGRATION_REVISION = "20260926_0017"
V0_3_RELEASE_VERSION = "0.3.0"
V0_3_MIGRATION_REVISION = "20261020_0036"
MINIMUM_UPGRADE_FIXTURE_ROWS = 2
LINEAGE_RELATIONS = (
    "candidate_journals",
    "dataset_snapshots",
    "research_experiments",
    "simulated_portfolios",
    "simulated_positions",
)


class ReleaseRelationFingerprint(BaseModel):
    """Sanitized identity evidence for one lineage-bearing relation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relation: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    row_count: int = Field(ge=0)
    identity_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReleaseDatabaseState(BaseModel):
    """A credential-free schema and lineage snapshot from one disposable database."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    database_name: str = Field(pattern=r"^[a-zA-Z0-9_-]+$", max_length=63)
    migration_revision: str | None = Field(default=None, pattern=r"^[a-f0-9_]+$")
    application_table_count: int = Field(ge=0)
    application_schema_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    lineage: tuple[ReleaseRelationFingerprint, ...]
    schema_drift_free: bool

    @model_validator(mode="after")
    def validate_lineage_order(self) -> Self:
        names = tuple(item.relation for item in self.lineage)
        if names != tuple(sorted(set(names))):
            raise ValueError("release installation lineage relations must be sorted and unique")
        return self


class ReleaseFreshInstallEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    before: ReleaseDatabaseState
    after: ReleaseDatabaseState

    @model_validator(mode="after")
    def validate_database_identity(self) -> Self:
        if self.before.database_name != self.after.database_name:
            raise ValueError("fresh-install evidence must use one database")
        return self


class ReleaseUpgradeEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    before: ReleaseDatabaseState
    after: ReleaseDatabaseState
    fixture_seeded: bool

    @model_validator(mode="after")
    def validate_database_identity(self) -> Self:
        if self.before.database_name != self.after.database_name:
            raise ValueError("upgrade evidence must use one database")
        return self


class ReleaseInstallationVerificationReport(BaseModel):
    """Commit-bound P6-06 evidence for fresh install and v0.2 upgrade."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["v0.3-release-installation-verification-v1"] = (
        "v0.3-release-installation-verification-v1"
    )
    environment_label: str = Field(min_length=1, max_length=64)
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    generated_at: datetime
    source_version: Literal["0.2.0"] = "0.2.0"
    source_migration_revision: Literal["20260926_0017"] = "20260926_0017"
    target_version: Literal["0.3.0"] = "0.3.0"
    target_migration_revision: Literal["20261020_0036"] = "20261020_0036"
    expected_application_table_count: int = Field(ge=1)
    target_schema_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    release_inventory_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    release_security_boundary_passed: bool
    fresh_install: ReleaseFreshInstallEvidence
    upgrade: ReleaseUpgradeEvidence
    failure_reasons: tuple[str, ...] = ()

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("release installation timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        expected = evaluate_release_installation(self)
        if self.failure_reasons != expected:
            raise ValueError("release installation failure reasons are inconsistent")
        return self

    @property
    def passed(self) -> bool:
        return not self.failure_reasons

    @property
    def report_checksum(self) -> str:
        return _checksum(self.model_dump(mode="json"))


def fingerprint_strings(values: tuple[str, ...]) -> str:
    return _checksum(list(values))


def empty_schema_checksum() -> str:
    return fingerprint_strings(())


def evaluate_release_installation(
    report: ReleaseInstallationVerificationReport,
) -> tuple[str, ...]:
    reasons: list[str] = []
    fresh_before = report.fresh_install.before
    fresh_after = report.fresh_install.after
    upgrade_before = report.upgrade.before
    upgrade_after = report.upgrade.after

    if fresh_before.database_name == upgrade_before.database_name:
        reasons.append("fresh install and upgrade used the same database")
    if (
        fresh_before.migration_revision is not None
        or fresh_before.application_table_count != 0
        or fresh_before.application_schema_checksum != empty_schema_checksum()
        or fresh_before.lineage
    ):
        reasons.append("fresh-install database was not empty")
    if fresh_before.schema_drift_free:
        reasons.append("fresh-install pre-migration state cannot claim a drift check")
    if fresh_after.migration_revision != report.target_migration_revision:
        reasons.append("fresh install did not reach the target migration")
    if (
        fresh_after.application_table_count != report.expected_application_table_count
        or fresh_after.application_schema_checksum != report.target_schema_checksum
    ):
        reasons.append("fresh install does not match the target application schema")
    if not fresh_after.schema_drift_free:
        reasons.append("fresh install has Alembic schema drift")
    if any(item.row_count for item in fresh_after.lineage):
        reasons.append("fresh-install lineage relations are not empty")

    if upgrade_before.migration_revision != report.source_migration_revision:
        reasons.append("upgrade did not start at the frozen v0.2 migration")
    if tuple(item.relation for item in upgrade_before.lineage) != LINEAGE_RELATIONS:
        reasons.append("upgrade baseline does not cover every lineage relation")
    if sum(item.row_count for item in upgrade_before.lineage) < MINIMUM_UPGRADE_FIXTURE_ROWS:
        reasons.append("upgrade baseline does not contain the minimum lineage fixture")
    if upgrade_before.schema_drift_free:
        reasons.append("upgrade pre-migration state cannot claim a v0.3 drift check")
    if upgrade_after.migration_revision != report.target_migration_revision:
        reasons.append("upgrade did not reach the target migration")
    if (
        upgrade_after.application_table_count != report.expected_application_table_count
        or upgrade_after.application_schema_checksum != report.target_schema_checksum
    ):
        reasons.append("upgrade does not match the target application schema")
    if not upgrade_after.schema_drift_free:
        reasons.append("upgraded database has Alembic schema drift")
    if upgrade_before.lineage != upgrade_after.lineage:
        reasons.append("upgrade did not preserve lineage row identities")
    if not report.release_security_boundary_passed:
        reasons.append("release security inventory failed after installation")
    return tuple(reasons)


def build_release_installation_report(
    *,
    environment_label: str,
    commit_sha: str,
    generated_at: datetime,
    expected_application_table_count: int,
    target_schema_checksum: str,
    release_inventory_checksum: str,
    release_security_boundary_passed: bool,
    fresh_install: ReleaseFreshInstallEvidence,
    upgrade: ReleaseUpgradeEvidence,
) -> ReleaseInstallationVerificationReport:
    provisional = ReleaseInstallationVerificationReport.model_construct(
        environment_label=environment_label,
        commit_sha=commit_sha,
        generated_at=generated_at,
        expected_application_table_count=expected_application_table_count,
        target_schema_checksum=target_schema_checksum,
        release_inventory_checksum=release_inventory_checksum,
        release_security_boundary_passed=release_security_boundary_passed,
        fresh_install=fresh_install,
        upgrade=upgrade,
        failure_reasons=(),
    )
    return ReleaseInstallationVerificationReport(
        environment_label=environment_label,
        commit_sha=commit_sha,
        generated_at=generated_at,
        expected_application_table_count=expected_application_table_count,
        target_schema_checksum=target_schema_checksum,
        release_inventory_checksum=release_inventory_checksum,
        release_security_boundary_passed=release_security_boundary_passed,
        fresh_install=fresh_install,
        upgrade=upgrade,
        failure_reasons=evaluate_release_installation(provisional),
    )


def release_installation_report_to_dict(
    report: ReleaseInstallationVerificationReport,
) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    payload["passed"] = report.passed
    payload["report_checksum"] = report.report_checksum
    return payload


def serialize_release_installation_report(
    report: ReleaseInstallationVerificationReport,
) -> str:
    return json.dumps(
        release_installation_report_to_dict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_release_installation_report(
    value: str | bytes,
) -> ReleaseInstallationVerificationReport:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("release installation report is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("release installation report must be a JSON object")
    payload = dict(raw)
    persisted_passed = payload.pop("passed", None)
    persisted_checksum = payload.pop("report_checksum", None)
    report = ReleaseInstallationVerificationReport.model_validate(payload)
    if persisted_passed is not None and persisted_passed is not report.passed:
        raise ValueError("release installation outcome is inconsistent")
    if persisted_checksum is not None and persisted_checksum != report.report_checksum:
        raise ValueError("release installation report checksum is inconsistent")
    return report


def _checksum(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
