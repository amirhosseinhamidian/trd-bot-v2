"""Persist immutable candidate lifecycle journals.

Revision ID: 20260826_0007
Revises: 20260826_0006
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0007"
down_revision: str | None = "20260826_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_journals",
        sa.Column("journal_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("portfolio_id", sa.String(length=100), nullable=False),
        sa.Column("attempted_count", sa.Integer(), nullable=False),
        sa.Column(
            "selected_candidate_id",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column("signal_id", sa.String(length=100), nullable=True),
        sa.Column("experiment_id", sa.String(length=100), nullable=True),
        sa.Column("position_id", sa.String(length=100), nullable=True),
        sa.Column("exit_reason", sa.String(length=40), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "schema_version > 0",
            name=op.f("ck_candidate_journals_schema_version_positive"),
        ),
        sa.CheckConstraint(
            "recorded_at >= evaluated_at",
            name=op.f("ck_candidate_journals_recorded_after_evaluated"),
        ),
        sa.CheckConstraint(
            "attempted_count >= 0",
            name=op.f("ck_candidate_journals_attempted_count_non_negative"),
        ),
        sa.CheckConstraint(
            "status IN ('no_position', 'closed')",
            name=op.f("ck_candidate_journals_status_supported"),
        ),
        sa.CheckConstraint(
            "exit_reason IS NULL OR exit_reason IN "
            "('invalidation', 'target', 'time_expiry', 'end_of_data')",
            name=op.f("ck_candidate_journals_exit_reason_supported"),
        ),
        sa.CheckConstraint(
            "(status = 'no_position' "
            "AND selected_candidate_id IS NULL "
            "AND signal_id IS NULL "
            "AND experiment_id IS NULL "
            "AND position_id IS NULL "
            "AND exit_reason IS NULL) "
            "OR "
            "(status = 'closed' "
            "AND selected_candidate_id IS NOT NULL "
            "AND signal_id IS NOT NULL "
            "AND experiment_id IS NOT NULL "
            "AND position_id IS NOT NULL "
            "AND exit_reason IS NOT NULL)",
            name=op.f("ck_candidate_journals_status_lineage_consistent"),
        ),
        sa.PrimaryKeyConstraint(
            "journal_id",
            name=op.f("pk_candidate_journals"),
        ),
    )

    for column in (
        "dataset_id",
        "exit_reason",
        "experiment_id",
        "portfolio_id",
        "position_id",
        "recorded_at",
        "selected_candidate_id",
        "signal_id",
        "status",
    ):
        op.create_index(
            op.f(f"ix_candidate_journals_{column}"),
            "candidate_journals",
            [column],
            unique=False,
        )

    op.create_index(
        "ix_candidate_journals_dataset_recorded_at",
        "candidate_journals",
        ["dataset_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_journals_portfolio_recorded_at",
        "candidate_journals",
        ["portfolio_id", "recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_journals_portfolio_recorded_at",
        table_name="candidate_journals",
    )
    op.drop_index(
        "ix_candidate_journals_dataset_recorded_at",
        table_name="candidate_journals",
    )

    for column in reversed(
        (
            "dataset_id",
            "exit_reason",
            "experiment_id",
            "portfolio_id",
            "position_id",
            "recorded_at",
            "selected_candidate_id",
            "signal_id",
            "status",
        )
    ):
        op.drop_index(
            op.f(f"ix_candidate_journals_{column}"),
            table_name="candidate_journals",
        )

    op.drop_table("candidate_journals")
