"""Create persistent walk-forward execution table.

Revision ID: 20260825_0004
Revises: 20260825_0003
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0004"
down_revision: str | None = "20260825_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "walk_forward_executions",
        sa.Column(
            "execution_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "progress_percent",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "dataset_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "strategy_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "strategy_version",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "total_folds",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "completed_folds",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "walk_forward_run_id",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "payload_json",
            sa.Text(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="status_supported",
        ),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="progress_percent_range",
        ),
        sa.CheckConstraint(
            "total_folds > 0",
            name="total_folds_positive",
        ),
        sa.CheckConstraint(
            "completed_folds >= 0 AND completed_folds <= total_folds",
            name="completed_folds_range",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="updated_after_created",
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="started_after_created",
        ),
        sa.CheckConstraint(
            ("finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)"),
            name="finished_after_started",
        ),
        sa.PrimaryKeyConstraint(
            "execution_id",
            name=op.f("pk_walk_forward_executions"),
        ),
    )

    op.create_index(
        op.f("ix_walk_forward_executions_created_at"),
        "walk_forward_executions",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        op.f("ix_walk_forward_executions_updated_at"),
        "walk_forward_executions",
        ["updated_at"],
        unique=False,
    )

    op.create_index(
        op.f("ix_walk_forward_executions_status"),
        "walk_forward_executions",
        ["status"],
        unique=False,
    )

    op.create_index(
        op.f("ix_walk_forward_executions_dataset_id"),
        "walk_forward_executions",
        ["dataset_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_walk_forward_executions_strategy_name"),
        "walk_forward_executions",
        ["strategy_name"],
        unique=False,
    )

    op.create_index(
        op.f("ix_walk_forward_executions_walk_forward_run_id"),
        "walk_forward_executions",
        ["walk_forward_run_id"],
        unique=False,
    )

    op.create_index(
        "ix_walk_forward_executions_status_updated_at",
        "walk_forward_executions",
        ["status", "updated_at"],
        unique=False,
    )

    op.create_index(
        "ix_walk_forward_executions_dataset_created_at",
        "walk_forward_executions",
        ["dataset_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_walk_forward_executions_dataset_created_at",
        table_name="walk_forward_executions",
    )

    op.drop_index(
        "ix_walk_forward_executions_status_updated_at",
        table_name="walk_forward_executions",
    )

    op.drop_index(
        op.f("ix_walk_forward_executions_walk_forward_run_id"),
        table_name="walk_forward_executions",
    )

    op.drop_index(
        op.f("ix_walk_forward_executions_strategy_name"),
        table_name="walk_forward_executions",
    )

    op.drop_index(
        op.f("ix_walk_forward_executions_dataset_id"),
        table_name="walk_forward_executions",
    )

    op.drop_index(
        op.f("ix_walk_forward_executions_status"),
        table_name="walk_forward_executions",
    )

    op.drop_index(
        op.f("ix_walk_forward_executions_updated_at"),
        table_name="walk_forward_executions",
    )

    op.drop_index(
        op.f("ix_walk_forward_executions_created_at"),
        table_name="walk_forward_executions",
    )

    op.drop_table("walk_forward_executions")
