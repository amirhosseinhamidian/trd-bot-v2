"""Add durable alert publication policies, decisions, and expiry evidence.

Revision ID: 20261018_0028
Revises: 20261018_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0028"
down_revision: str | None = "20261018_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_publication_policies",
        sa.Column("policy_id", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False),
        sa.Column("quiet_hours_start_minute", sa.Integer(), nullable=False),
        sa.Column("quiet_hours_end_minute", sa.Integer(), nullable=False),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.Column("critical_bypass_quiet_hours", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "policy_version >= 1",
            name=op.f("ck_alert_publication_policies_policy_version_positive"),
        ),
        sa.CheckConstraint(
            "quiet_hours_start_minute >= 0 AND quiet_hours_start_minute <= 1439",
            name=op.f("ck_alert_publication_policies_quiet_hours_start_minute_range"),
        ),
        sa.CheckConstraint(
            "quiet_hours_end_minute >= 0 AND quiet_hours_end_minute <= 1439",
            name=op.f("ck_alert_publication_policies_quiet_hours_end_minute_range"),
        ),
        sa.CheckConstraint(
            "quiet_hours_enabled = 0 OR quiet_hours_start_minute != quiet_hours_end_minute",
            name=op.f("ck_alert_publication_policies_quiet_hours_window_nonempty"),
        ),
        sa.CheckConstraint(
            "length(policy_checksum) = 64",
            name=op.f("ck_alert_publication_policies_checksum_length"),
        ),
        sa.PrimaryKeyConstraint(
            "policy_id",
            "policy_version",
            name=op.f("pk_alert_publication_policies"),
        ),
        sa.UniqueConstraint(
            "policy_checksum",
            name=op.f("uq_alert_publication_policies_policy_checksum"),
        ),
    )
    op.create_index(
        op.f("ix_alert_publication_policies_updated_at"),
        "alert_publication_policies",
        ["updated_at"],
    )

    op.create_table(
        "alert_publication_decisions",
        sa.Column("decision_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("policy_id", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("policy_checksum", sa.String(length=64), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("suppression_reason_count", sa.Integer(), nullable=False),
        sa.Column("previous_alert_id", sa.String(length=100), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "policy_version >= 0",
            name=op.f("ck_alert_publication_decisions_policy_version_nonnegative"),
        ),
        sa.CheckConstraint(
            "suppression_reason_count >= 0",
            name=op.f("ck_alert_publication_decisions_reason_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "(allowed = 1 AND suppression_reason_count = 0) OR "
            "(allowed = 0 AND suppression_reason_count >= 1)",
            name=op.f("ck_alert_publication_decisions_outcome_consistent"),
        ),
        sa.CheckConstraint(
            "length(policy_checksum) = 64",
            name=op.f("ck_alert_publication_decisions_policy_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(decision_checksum) = 64",
            name=op.f("ck_alert_publication_decisions_decision_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["alert_evaluations.evaluation_id"],
            name=op.f("fk_alert_publication_decisions_evaluation_id_alert_evaluations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["previous_alert_id"],
            ["alerts.alert_id"],
            name=op.f("fk_alert_publication_decisions_previous_alert_id_alerts"),
        ),
        sa.PrimaryKeyConstraint("decision_id", name=op.f("pk_alert_publication_decisions")),
        sa.UniqueConstraint(
            "decision_checksum",
            name=op.f("uq_alert_publication_decisions_decision_checksum"),
        ),
    )
    for column in ("allowed", "evaluated_at", "policy_id"):
        op.create_index(
            op.f(f"ix_alert_publication_decisions_{column}"),
            "alert_publication_decisions",
            [column],
        )
    op.create_index(
        op.f("ix_alert_publication_decisions_evaluation_id"),
        "alert_publication_decisions",
        ["evaluation_id"],
        unique=True,
    )
    op.create_index(
        "ix_alert_publication_decisions_allowed_evaluated_at",
        "alert_publication_decisions",
        ["allowed", "evaluated_at"],
    )

    op.create_table(
        "alert_expiry_records",
        sa.Column("expiry_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("alert_id", sa.String(length=100), nullable=False),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(length=100), nullable=False),
        sa.Column("record_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "recorded_at >= expired_at",
            name=op.f("ck_alert_expiry_records_recorded_after_expiry"),
        ),
        sa.CheckConstraint(
            "length(record_checksum) = 64",
            name=op.f("ck_alert_expiry_records_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.alert_id"],
            name=op.f("fk_alert_expiry_records_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("expiry_id", name=op.f("pk_alert_expiry_records")),
        sa.UniqueConstraint(
            "record_checksum",
            name=op.f("uq_alert_expiry_records_record_checksum"),
        ),
    )
    for column in ("expired_at", "recorded_at"):
        op.create_index(
            op.f(f"ix_alert_expiry_records_{column}"),
            "alert_expiry_records",
            [column],
        )
    op.create_index(
        op.f("ix_alert_expiry_records_alert_id"),
        "alert_expiry_records",
        ["alert_id"],
        unique=True,
    )
    op.create_index(
        "ix_alert_expiry_records_expired_recorded",
        "alert_expiry_records",
        ["expired_at", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_table("alert_expiry_records")
    op.drop_table("alert_publication_decisions")
    op.drop_table("alert_publication_policies")
