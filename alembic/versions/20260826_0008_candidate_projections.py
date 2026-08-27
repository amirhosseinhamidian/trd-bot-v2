"""Persist rebuildable candidate projection read models.

Revision ID: 20260826_0008
Revises: 20260826_0007
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0008"
down_revision: str | None = "20260826_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_projections",
        sa.Column("candidate_id", sa.String(length=100), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("experiment_id", sa.String(length=100), nullable=False),
        sa.Column("signal_id", sa.String(length=100), nullable=False),
        sa.Column("latest_journal_id", sa.String(length=100), nullable=False),
        sa.Column(
            "latest_recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Numeric(18, 10), nullable=False),
        sa.Column("signal_score", sa.Numeric(18, 10), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("latest_rank", sa.Integer(), nullable=False),
        sa.Column(
            "latest_ranking_score",
            sa.Numeric(18, 10),
            nullable=False,
        ),
        sa.Column(
            "latest_replay_status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "latest_risk_decision",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column("selected", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.String(length=100), nullable=True),
        sa.Column("exit_reason", sa.String(length=40), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "occurrence_count > 0",
            name=op.f("ck_candidate_projections_occurrence_count_positive"),
        ),
        sa.CheckConstraint(
            "latest_rank > 0",
            name=op.f("ck_candidate_projections_latest_rank_positive"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_candidate_projections_confidence_supported"),
        ),
        sa.CheckConstraint(
            "signal_score >= -1 AND signal_score <= 1",
            name=op.f("ck_candidate_projections_signal_score_supported"),
        ),
        sa.CheckConstraint(
            "latest_ranking_score >= 0 AND latest_ranking_score <= 1",
            name=op.f("ck_candidate_projections_latest_ranking_score_supported"),
        ),
        sa.CheckConstraint(
            "status IN ('candidate', 'selected', 'stale', 'invalidated')",
            name=op.f("ck_candidate_projections_status_supported"),
        ),
        sa.CheckConstraint(
            "action IN ('long', 'short', 'neutral', 'no_trade')",
            name=op.f("ck_candidate_projections_action_supported"),
        ),
        sa.CheckConstraint(
            "latest_replay_status IN ('opened', 'risk_rejected', 'no_fill')",
            name=op.f("ck_candidate_projections_latest_replay_status_supported"),
        ),
        sa.CheckConstraint(
            "latest_risk_decision IN ('approved', 'rejected')",
            name=op.f("ck_candidate_projections_latest_risk_decision_supported"),
        ),
        sa.CheckConstraint(
            "selected IN (0, 1)",
            name=op.f("ck_candidate_projections_selected_boolean"),
        ),
        sa.CheckConstraint(
            "exit_reason IS NULL OR exit_reason IN "
            "('invalidation', 'target', 'time_expiry', 'end_of_data')",
            name=op.f("ck_candidate_projections_exit_reason_supported"),
        ),
        sa.CheckConstraint(
            "(selected = 1 "
            "AND latest_replay_status = 'opened' "
            "AND position_id IS NOT NULL "
            "AND exit_reason IS NOT NULL) "
            "OR "
            "(selected = 0 "
            "AND latest_replay_status <> 'opened' "
            "AND position_id IS NULL "
            "AND exit_reason IS NULL)",
            name=op.f("ck_candidate_projections_selection_lineage_consistent"),
        ),
        sa.PrimaryKeyConstraint(
            "candidate_id",
            name=op.f("pk_candidate_projections"),
        ),
    )

    for column in (
        "action",
        "dataset_id",
        "exit_reason",
        "experiment_id",
        "latest_journal_id",
        "latest_recorded_at",
        "latest_replay_status",
        "latest_risk_decision",
        "position_id",
        "selected",
        "signal_id",
        "status",
        "strategy_name",
    ):
        op.create_index(
            op.f(f"ix_candidate_projections_{column}"),
            "candidate_projections",
            [column],
            unique=False,
        )

    op.create_index(
        "ix_candidate_projections_dataset_latest_recorded_at",
        "candidate_projections",
        ["dataset_id", "latest_recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_projections_pair_timeframe",
        "candidate_projections",
        ["base_asset", "quote_asset", "market_type", "timeframe"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_projections_strategy_latest_recorded_at",
        "candidate_projections",
        ["strategy_name", "strategy_version", "latest_recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_projections_strategy_latest_recorded_at",
        table_name="candidate_projections",
    )
    op.drop_index(
        "ix_candidate_projections_pair_timeframe",
        table_name="candidate_projections",
    )
    op.drop_index(
        "ix_candidate_projections_dataset_latest_recorded_at",
        table_name="candidate_projections",
    )

    for column in reversed(
        (
            "action",
            "dataset_id",
            "exit_reason",
            "experiment_id",
            "latest_journal_id",
            "latest_recorded_at",
            "latest_replay_status",
            "latest_risk_decision",
            "position_id",
            "selected",
            "signal_id",
            "status",
            "strategy_name",
        )
    ):
        op.drop_index(
            op.f(f"ix_candidate_projections_{column}"),
            table_name="candidate_projections",
        )

    op.drop_table("candidate_projections")
