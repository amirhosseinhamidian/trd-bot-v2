"""Add immutable offline Alert Paper/Shadow simulations.

Revision ID: 20261018_0029
Revises: 20261018_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0029"
down_revision: str | None = "20261018_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_simulations",
        sa.Column("simulation_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("alert_id", sa.String(length=100), nullable=False),
        sa.Column("alert_checksum", sa.String(length=64), nullable=False),
        sa.Column("source_reference_id", sa.String(length=100), nullable=False),
        sa.Column("source_reference_checksum", sa.String(length=64), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("rule_definition_checksum", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("expected_trend", sa.String(length=30), nullable=False),
        sa.Column("horizon_seconds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_by", sa.String(length=100), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("record_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "mode IN ('paper', 'shadow')",
            name=op.f("ck_alert_simulations_mode_supported"),
        ),
        sa.CheckConstraint(
            "horizon_seconds >= 900 AND horizon_seconds <= 2592000",
            name=op.f("ck_alert_simulations_horizon_bounded"),
        ),
        sa.CheckConstraint(
            "ends_at > started_at",
            name=op.f("ck_alert_simulations_ends_after_started"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_alert_simulations_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_alert_simulations_external_order_submission_forbidden"),
        ),
        sa.CheckConstraint(
            "length(record_checksum) = 64",
            name=op.f("ck_alert_simulations_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.alert_id"],
            name=op.f("fk_alert_simulations_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("simulation_id", name=op.f("pk_alert_simulations")),
        sa.UniqueConstraint(
            "record_checksum",
            name=op.f("uq_alert_simulations_record_checksum"),
        ),
    )
    for column in (
        "alert_id",
        "ends_at",
        "mode",
        "rule_id",
        "source_reference_id",
        "started_at",
    ):
        op.create_index(
            op.f(f"ix_alert_simulations_{column}"),
            "alert_simulations",
            [column],
        )
    op.create_index(
        "ix_alert_simulations_alert_started_at",
        "alert_simulations",
        ["alert_id", "started_at"],
    )
    op.create_index(
        "ix_alert_simulations_mode_ends_at",
        "alert_simulations",
        ["mode", "ends_at"],
    )


def downgrade() -> None:
    op.drop_table("alert_simulations")
