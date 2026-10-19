"""Persist context-aware strategy evaluation evidence.

Revision ID: 20261019_0032
Revises: 20261019_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_0032"
down_revision: str | None = "20261019_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_strategy_evaluations",
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("outcome_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("compatibility_policy_version", sa.String(length=50), nullable=False),
        sa.Column("compatibility_policy_checksum", sa.String(length=64), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False),
        sa.Column("latest_signal_id", sa.String(length=100), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("record_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "disposition IN ('accepted', 'rejected', 'deferred', 'unavailable')",
            name=op.f("ck_decision_strategy_evaluations_disposition_supported"),
        ),
        sa.CheckConstraint(
            "signal_count >= 0",
            name=op.f("ck_decision_strategy_evaluations_signal_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "(disposition = 'accepted' AND signal_count > 0 "
            "AND latest_signal_id IS NOT NULL) OR "
            "(disposition != 'accepted' AND signal_count = 0 "
            "AND latest_signal_id IS NULL)",
            name=op.f("ck_decision_strategy_evaluations_signals_consistent"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_decision_strategy_evaluations_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_decision_strategy_evaluations_external_order_submission_forbidden"),
        ),
        sa.CheckConstraint(
            "length(compatibility_policy_checksum) = 64",
            name=op.f("ck_decision_strategy_evaluations_policy_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(record_checksum) = 64",
            name=op.f("ck_decision_strategy_evaluations_record_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["decision_evaluation_intents.evaluation_id"],
            name=op.f("fk_decision_strategy_evaluations_evaluation_id_decision_evaluation_intents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_id"],
            ["decision_stage_outcomes.outcome_id"],
            name=op.f("fk_decision_strategy_evaluations_outcome_id_decision_stage_outcomes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_id",
            name=op.f("pk_decision_strategy_evaluations"),
        ),
        sa.UniqueConstraint(
            "outcome_id",
            name=op.f("uq_decision_strategy_evaluations_outcome_id"),
        ),
        sa.UniqueConstraint(
            "record_checksum",
            name=op.f("uq_decision_strategy_evaluations_record_checksum"),
        ),
    )
    for column in (
        "compatibility_policy_checksum",
        "disposition",
        "evaluated_at",
        "latest_signal_id",
    ):
        op.create_index(
            op.f(f"ix_decision_strategy_evaluations_{column}"),
            "decision_strategy_evaluations",
            [column],
        )
    op.create_index(
        "ix_decision_strategy_evaluations_disposition_evaluated_at",
        "decision_strategy_evaluations",
        ["disposition", "evaluated_at"],
    )


def downgrade() -> None:
    op.drop_table("decision_strategy_evaluations")
