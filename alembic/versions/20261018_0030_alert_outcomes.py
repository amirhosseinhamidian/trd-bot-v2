"""Add immutable offline alert outcome journal.

Revision ID: 20261018_0030
Revises: 20261018_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0030"
down_revision: str | None = "20261018_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_outcomes",
        sa.Column("outcome_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("simulation_id", sa.String(length=100), nullable=False),
        sa.Column("simulation_checksum", sa.String(length=64), nullable=False),
        sa.Column("alert_id", sa.String(length=100), nullable=False),
        sa.Column("alert_checksum", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("expected_trend", sa.String(length=30), nullable=False),
        sa.Column("observed_trend", sa.String(length=30), nullable=False),
        sa.Column("reference_price", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("end_price", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("high_price", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("low_price", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("raw_return", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("directional_return", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("max_favorable_excursion", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("max_adverse_excursion", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("classification", sa.String(length=30), nullable=False),
        sa.Column("false_positive", sa.Boolean(), nullable=False),
        sa.Column("drifted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("policy_checksum", sa.String(length=64), nullable=False),
        sa.Column("classification_threshold", sa.Numeric(precision=8, scale=6), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(length=100), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("record_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "classification IN ('confirmed', 'neutral', 'false_positive')",
            name=op.f("ck_alert_outcomes_classification_supported"),
        ),
        sa.CheckConstraint(
            "mode IN ('paper', 'shadow')", name=op.f("ck_alert_outcomes_mode_supported")
        ),
        sa.CheckConstraint(
            "reference_price > 0", name=op.f("ck_alert_outcomes_reference_price_positive")
        ),
        sa.CheckConstraint("end_price > 0", name=op.f("ck_alert_outcomes_end_price_positive")),
        sa.CheckConstraint("high_price > 0", name=op.f("ck_alert_outcomes_high_price_positive")),
        sa.CheckConstraint("low_price > 0", name=op.f("ck_alert_outcomes_low_price_positive")),
        sa.CheckConstraint(
            "high_price >= reference_price AND high_price >= end_price",
            name=op.f("ck_alert_outcomes_high_price_valid"),
        ),
        sa.CheckConstraint(
            "low_price <= reference_price AND low_price <= end_price",
            name=op.f("ck_alert_outcomes_low_price_valid"),
        ),
        sa.CheckConstraint(
            "recorded_at >= observed_at",
            name=op.f("ck_alert_outcomes_recorded_after_observation"),
        ),
        sa.CheckConstraint(
            "false_positive = (classification = 'false_positive')",
            name=op.f("ck_alert_outcomes_false_positive_consistent"),
        ),
        sa.CheckConstraint(
            "policy_version = 'alert-outcome-policy-v1'",
            name=op.f("ck_alert_outcomes_policy_version_supported"),
        ),
        sa.CheckConstraint(
            "classification_threshold = 0.005",
            name=op.f("ck_alert_outcomes_classification_threshold_supported"),
        ),
        sa.CheckConstraint("offline_only", name=op.f("ck_alert_outcomes_offline_only_required")),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_alert_outcomes_external_order_submission_forbidden"),
        ),
        sa.CheckConstraint(
            "length(record_checksum) = 64",
            name=op.f("ck_alert_outcomes_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["alert_simulations.simulation_id"],
            name=op.f("fk_alert_outcomes_simulation_id_alert_simulations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.alert_id"],
            name=op.f("fk_alert_outcomes_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("outcome_id", name=op.f("pk_alert_outcomes")),
        sa.UniqueConstraint("record_checksum", name=op.f("uq_alert_outcomes_record_checksum")),
    )
    for column in (
        "alert_id",
        "classification",
        "drifted",
        "false_positive",
        "mode",
        "observed_at",
        "recorded_at",
    ):
        op.create_index(op.f(f"ix_alert_outcomes_{column}"), "alert_outcomes", [column])
    op.create_index(
        op.f("ix_alert_outcomes_simulation_id"),
        "alert_outcomes",
        ["simulation_id"],
        unique=True,
    )
    op.create_index(
        "ix_alert_outcomes_classification_recorded",
        "alert_outcomes",
        ["classification", "recorded_at"],
    )
    op.create_index(
        "ix_alert_outcomes_mode_recorded",
        "alert_outcomes",
        ["mode", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_table("alert_outcomes")
