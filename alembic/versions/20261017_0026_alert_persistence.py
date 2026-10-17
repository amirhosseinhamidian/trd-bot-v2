"""Add immutable alert rules, evaluations, and published alerts.

Revision ID: 20261017_0026
Revises: 20261016_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0026"
down_revision: str | None = "20261016_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_rule_definitions",
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("definition_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rule_version >= 1",
            name=op.f("ck_alert_rule_definitions_rule_version_positive"),
        ),
        sa.CheckConstraint(
            "source_kind IN ('market_context')",
            name=op.f("ck_alert_rule_definitions_source_kind_supported"),
        ),
        sa.CheckConstraint(
            "state IN ('enabled', 'disabled')",
            name=op.f("ck_alert_rule_definitions_state_supported"),
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name=op.f("ck_alert_rule_definitions_severity_supported"),
        ),
        sa.CheckConstraint(
            "length(definition_checksum) = 64",
            name=op.f("ck_alert_rule_definitions_checksum_length"),
        ),
        sa.PrimaryKeyConstraint(
            "rule_id",
            "rule_version",
            name=op.f("pk_alert_rule_definitions"),
        ),
        sa.UniqueConstraint(
            "definition_checksum",
            name=op.f("uq_alert_rule_definitions_definition_checksum"),
        ),
        sa.UniqueConstraint(
            "rule_key",
            "rule_version",
            name="uq_alert_rule_definitions_key_version",
        ),
    )
    for column in ("created_at", "rule_key", "severity", "source_kind", "state"):
        op.create_index(
            op.f(f"ix_alert_rule_definitions_{column}"),
            "alert_rule_definitions",
            [column],
        )
    op.create_index(
        "ix_alert_rule_definitions_state_created_at",
        "alert_rule_definitions",
        ["state", "created_at"],
    )

    op.create_table(
        "alert_evaluations",
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_reference_id", sa.String(length=100), nullable=False),
        sa.Column("source_event_id", sa.String(length=100), nullable=False),
        sa.Column("source_event_checksum", sa.String(length=64), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=False),
        sa.Column("suppression_reason_count", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.String(length=100), nullable=True),
        sa.Column("evaluation_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_kind IN ('market_context')",
            name=op.f("ck_alert_evaluations_source_kind_supported"),
        ),
        sa.CheckConstraint(
            "disposition IN ('published', 'suppressed')",
            name=op.f("ck_alert_evaluations_disposition_supported"),
        ),
        sa.CheckConstraint(
            "suppression_reason_count >= 0",
            name=op.f("ck_alert_evaluations_suppression_reason_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(source_event_checksum) = 64",
            name=op.f("ck_alert_evaluations_source_event_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(evaluation_checksum) = 64",
            name=op.f("ck_alert_evaluations_evaluation_checksum_length"),
        ),
        sa.CheckConstraint(
            "(disposition = 'published' AND alert_id IS NOT NULL "
            "AND suppression_reason_count = 0) OR "
            "(disposition = 'suppressed' AND alert_id IS NULL "
            "AND suppression_reason_count >= 1)",
            name=op.f("ck_alert_evaluations_outcome_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id", "rule_version"],
            ["alert_rule_definitions.rule_id", "alert_rule_definitions.rule_version"],
            name=op.f("fk_alert_evaluations_rule_id_alert_rule_definitions"),
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["market_regime_assessments.assessment_id"],
            name=op.f("fk_alert_evaluations_source_event_id_market_regime_assessments"),
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_id",
            name=op.f("pk_alert_evaluations"),
        ),
        sa.UniqueConstraint(
            "evaluation_checksum",
            name=op.f("uq_alert_evaluations_evaluation_checksum"),
        ),
        sa.UniqueConstraint(
            "rule_id",
            "rule_version",
            "source_kind",
            "source_event_id",
            name="uq_alert_evaluations_rule_source",
        ),
    )
    for column in (
        "alert_id",
        "disposition",
        "evaluated_at",
        "rule_id",
        "source_event_id",
        "source_kind",
        "source_reference_id",
    ):
        op.create_index(
            op.f(f"ix_alert_evaluations_{column}"),
            "alert_evaluations",
            [column],
        )
    op.create_index(
        "ix_alert_evaluations_disposition_evaluated_at",
        "alert_evaluations",
        ["disposition", "evaluated_at"],
    )

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("deduplication_key", sa.String(length=100), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_event_id", sa.String(length=100), nullable=False),
        sa.Column("delivery_channel", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("draft_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_kind IN ('market_context')",
            name=op.f("ck_alerts_source_kind_supported"),
        ),
        sa.CheckConstraint(
            "delivery_channel IN ('in_app')",
            name=op.f("ck_alerts_delivery_channel_supported"),
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name=op.f("ck_alerts_severity_supported"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_alerts_expiry_after_creation"),
        ),
        sa.CheckConstraint(
            "length(draft_checksum) = 64",
            name=op.f("ck_alerts_draft_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["alert_evaluations.evaluation_id"],
            name=op.f("fk_alerts_evaluation_id_alert_evaluations"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id", "rule_version"],
            ["alert_rule_definitions.rule_id", "alert_rule_definitions.rule_version"],
            name=op.f("fk_alerts_rule_id_alert_rule_definitions"),
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["market_regime_assessments.assessment_id"],
            name=op.f("fk_alerts_source_event_id_market_regime_assessments"),
        ),
        sa.PrimaryKeyConstraint("alert_id", name=op.f("pk_alerts")),
        sa.UniqueConstraint(
            "deduplication_key",
            name=op.f("uq_alerts_deduplication_key"),
        ),
        sa.UniqueConstraint(
            "draft_checksum",
            name=op.f("uq_alerts_draft_checksum"),
        ),
        sa.UniqueConstraint(
            "evaluation_id",
            name=op.f("uq_alerts_evaluation_id"),
        ),
    )
    for column in (
        "created_at",
        "expires_at",
        "rule_id",
        "severity",
        "source_event_id",
        "source_kind",
    ):
        op.create_index(op.f(f"ix_alerts_{column}"), "alerts", [column])
    op.create_index(
        "ix_alerts_expires_at_created_at",
        "alerts",
        ["expires_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("alert_evaluations")
    op.drop_table("alert_rule_definitions")
