"""Add immutable market-context lineage, features, and regime assessments.

Revision ID: 20261016_0025
Revises: 20261015_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0025"
down_revision: str | None = "20261015_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_context_input_manifests",
        sa.Column("manifest_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_checksum", sa.String(length=64), nullable=False),
        sa.Column("window_count", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(input_checksum) = 64",
            name=op.f("ck_market_context_input_manifests_checksum_length"),
        ),
        sa.CheckConstraint(
            "window_count >= 3",
            name=op.f("ck_market_context_input_manifests_window_count_minimum"),
        ),
        sa.CheckConstraint(
            "created_at >= as_of",
            name=op.f("ck_market_context_input_manifests_created_after_as_of"),
        ),
        sa.PrimaryKeyConstraint(
            "manifest_id",
            name=op.f("pk_market_context_input_manifests"),
        ),
        sa.UniqueConstraint(
            "input_checksum",
            name=op.f("uq_market_context_input_manifests_input_checksum"),
        ),
    )
    for column in ("as_of", "created_at", "policy_version", "source"):
        op.create_index(
            op.f(f"ix_market_context_input_manifests_{column}"),
            "market_context_input_manifests",
            [column],
        )
    op.create_index(
        "ix_market_context_input_manifests_stream_as_of",
        "market_context_input_manifests",
        ["source", "base_asset", "quote_asset", "market_type", "as_of"],
    )

    op.create_table(
        "market_context_input_windows",
        sa.Column("manifest_id", sa.String(length=100), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("window_id", sa.String(length=100), nullable=False),
        sa.Column("window_version", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_checksum", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 1",
            name=op.f("ck_market_context_input_windows_ordinal_positive"),
        ),
        sa.CheckConstraint(
            "window_version >= 2",
            name=op.f("ck_market_context_input_windows_window_version_finalized"),
        ),
        sa.CheckConstraint(
            "window_end > window_start",
            name=op.f("ck_market_context_input_windows_window_range_valid"),
        ),
        sa.CheckConstraint(
            "length(reference_checksum) = 64",
            name=op.f("ck_market_context_input_windows_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["manifest_id"],
            ["market_context_input_manifests.manifest_id"],
            name=op.f("fk_market_context_input_windows_manifest_id_market_context_input_manifests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["window_id", "window_version"],
            ["market_data_window_versions.window_id", "market_data_window_versions.version"],
            name=op.f("fk_market_context_input_windows_window_id_market_data_window_versions"),
        ),
        sa.PrimaryKeyConstraint(
            "manifest_id",
            "ordinal",
            name=op.f("pk_market_context_input_windows"),
        ),
        sa.UniqueConstraint(
            "manifest_id",
            "window_id",
            "window_version",
            name="uq_market_context_input_windows_window_version",
        ),
    )
    for column in ("reference_checksum", "timeframe", "window_end", "window_id"):
        op.create_index(
            op.f(f"ix_market_context_input_windows_{column}"),
            "market_context_input_windows",
            [column],
        )
    op.create_index(
        "ix_market_context_input_windows_manifest_timeframe_ordinal",
        "market_context_input_windows",
        ["manifest_id", "timeframe", "ordinal"],
    )

    op.create_table(
        "market_context_feature_snapshots",
        sa.Column("snapshot_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("manifest_id", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_checksum", sa.String(length=64), nullable=False),
        sa.Column("feature_set_version", sa.String(length=100), nullable=False),
        sa.Column("feature_set_checksum", sa.String(length=64), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(input_checksum) = 64",
            name=op.f("ck_market_context_feature_snapshots_input_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(feature_set_checksum) = 64",
            name=op.f("ck_market_context_feature_snapshots_feature_set_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(snapshot_checksum) = 64",
            name=op.f("ck_market_context_feature_snapshots_snapshot_checksum_length"),
        ),
        sa.CheckConstraint(
            "feature_count >= 1",
            name=op.f("ck_market_context_feature_snapshots_feature_count_positive"),
        ),
        sa.CheckConstraint(
            "calculated_at >= as_of",
            name=op.f("ck_market_context_feature_snapshots_calculated_after_as_of"),
        ),
        sa.ForeignKeyConstraint(
            ["manifest_id"],
            ["market_context_input_manifests.manifest_id"],
            name=op.f(
                "fk_market_context_feature_snapshots_manifest_id_market_context_input_manifests"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "snapshot_id",
            name=op.f("pk_market_context_feature_snapshots"),
        ),
        sa.UniqueConstraint(
            "manifest_id",
            "feature_set_version",
            name="uq_market_context_feature_snapshots_manifest_feature_set",
        ),
        sa.UniqueConstraint(
            "snapshot_checksum",
            name=op.f("uq_market_context_feature_snapshots_snapshot_checksum"),
        ),
    )
    for column in ("as_of", "calculated_at", "feature_set_version", "manifest_id", "source"):
        op.create_index(
            op.f(f"ix_market_context_feature_snapshots_{column}"),
            "market_context_feature_snapshots",
            [column],
        )
    op.create_index(
        "ix_market_context_feature_snapshots_stream_as_of",
        "market_context_feature_snapshots",
        ["source", "base_asset", "quote_asset", "market_type", "as_of"],
    )

    op.create_table(
        "market_regime_assessments",
        sa.Column("assessment_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("manifest_id", sa.String(length=100), nullable=False),
        sa.Column("feature_snapshot_id", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_checksum", sa.String(length=64), nullable=False),
        sa.Column("feature_set_version", sa.String(length=100), nullable=False),
        sa.Column("feature_set_checksum", sa.String(length=64), nullable=False),
        sa.Column("feature_snapshot_checksum", sa.String(length=64), nullable=True),
        sa.Column("algorithm_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("trend", sa.String(length=30), nullable=False),
        sa.Column("volatility", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=18, scale=10), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("issue_count", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ready', 'insufficient_data', 'stale')",
            name=op.f("ck_market_regime_assessments_status_supported"),
        ),
        sa.CheckConstraint(
            "trend IN ('trending_up', 'trending_down', 'ranging', 'undetermined')",
            name=op.f("ck_market_regime_assessments_trend_supported"),
        ),
        sa.CheckConstraint(
            "volatility IN ('low', 'normal', 'high', 'undetermined')",
            name=op.f("ck_market_regime_assessments_volatility_supported"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_market_regime_assessments_confidence_range"),
        ),
        sa.CheckConstraint(
            "length(input_checksum) = 64",
            name=op.f("ck_market_regime_assessments_input_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(feature_set_checksum) = 64",
            name=op.f("ck_market_regime_assessments_feature_set_checksum_length"),
        ),
        sa.CheckConstraint(
            "feature_snapshot_checksum IS NULL OR length(feature_snapshot_checksum) = 64",
            name=op.f("ck_market_regime_assessments_feature_snapshot_checksum_length"),
        ),
        sa.CheckConstraint(
            "assessed_at >= as_of",
            name=op.f("ck_market_regime_assessments_assessed_after_as_of"),
        ),
        sa.CheckConstraint(
            "(status = 'ready' AND trend != 'undetermined' "
            "AND volatility != 'undetermined' AND confidence > 0 "
            "AND feature_snapshot_id IS NOT NULL "
            "AND feature_snapshot_checksum IS NOT NULL AND expires_at > assessed_at) OR "
            "(status != 'ready' AND trend = 'undetermined' "
            "AND volatility = 'undetermined' AND confidence = 0 "
            "AND feature_snapshot_id IS NULL "
            "AND feature_snapshot_checksum IS NULL AND expires_at = assessed_at)",
            name=op.f("ck_market_regime_assessments_outcome_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_id"],
            ["market_context_feature_snapshots.snapshot_id"],
            name=op.f(
                "fk_market_regime_assessments_feature_snapshot_id_market_context_feature_snapshots"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["manifest_id"],
            ["market_context_input_manifests.manifest_id"],
            name=op.f("fk_market_regime_assessments_manifest_id_market_context_input_manifests"),
        ),
        sa.PrimaryKeyConstraint(
            "assessment_id",
            name=op.f("pk_market_regime_assessments"),
        ),
        sa.UniqueConstraint(
            "manifest_id",
            "feature_set_version",
            "algorithm_version",
            name="uq_market_regime_assessments_manifest_algorithm",
        ),
    )
    for column in (
        "algorithm_version",
        "as_of",
        "assessed_at",
        "expires_at",
        "feature_set_version",
        "feature_snapshot_id",
        "manifest_id",
        "source",
        "status",
    ):
        op.create_index(
            op.f(f"ix_market_regime_assessments_{column}"),
            "market_regime_assessments",
            [column],
        )
    op.create_index(
        "ix_market_regime_assessments_stream_as_of",
        "market_regime_assessments",
        ["source", "base_asset", "quote_asset", "market_type", "as_of"],
    )
    op.create_index(
        "ix_market_regime_assessments_status_assessed_at",
        "market_regime_assessments",
        ["status", "assessed_at"],
    )


def downgrade() -> None:
    op.drop_table("market_regime_assessments")
    op.drop_table("market_context_feature_snapshots")
    op.drop_table("market_context_input_windows")
    op.drop_table("market_context_input_manifests")
