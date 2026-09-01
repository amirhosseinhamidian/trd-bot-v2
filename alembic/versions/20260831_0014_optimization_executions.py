"""Create persistent optimization executions.

Revision ID: 20260831_0014
Revises: 20260831_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0014"
down_revision: str | None = "20260831_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "optimization_executions",
        sa.Column("execution_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=30), nullable=False),
        sa.Column("objective", sa.String(length=50), nullable=False),
        sa.Column("total_trials", sa.Integer(), nullable=False),
        sa.Column("completed_trials", sa.Integer(), nullable=False),
        sa.Column("best_experiment_id", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="optimization_execution_status_supported",
        ),
        sa.CheckConstraint(
            "total_trials > 0",
            name="optimization_execution_total_trials_positive",
        ),
        sa.CheckConstraint(
            "completed_trials >= 0 AND completed_trials <= total_trials",
            name="optimization_execution_progress_range",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="optimization_execution_updated_after_created",
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="optimization_execution_started_after_created",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR "
            "(started_at IS NOT NULL AND finished_at >= started_at)",
            name="optimization_execution_finished_after_started",
        ),
        sa.PrimaryKeyConstraint("execution_id"),
    )

    op.create_index(
        "ix_optimization_executions_created_at",
        "optimization_executions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_executions_updated_at",
        "optimization_executions",
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_executions_status",
        "optimization_executions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_executions_dataset_id",
        "optimization_executions",
        ["dataset_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_executions_strategy_name",
        "optimization_executions",
        ["strategy_name"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_executions_best_experiment_id",
        "optimization_executions",
        ["best_experiment_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_executions_status_created_at",
        "optimization_executions",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_executions_dataset_created_at",
        "optimization_executions",
        ["dataset_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_optimization_executions_dataset_created_at",
        table_name="optimization_executions",
    )
    op.drop_index(
        "ix_optimization_executions_status_created_at",
        table_name="optimization_executions",
    )
    op.drop_index(
        "ix_optimization_executions_best_experiment_id",
        table_name="optimization_executions",
    )
    op.drop_index(
        "ix_optimization_executions_strategy_name",
        table_name="optimization_executions",
    )
    op.drop_index(
        "ix_optimization_executions_dataset_id",
        table_name="optimization_executions",
    )
    op.drop_index(
        "ix_optimization_executions_status",
        table_name="optimization_executions",
    )
    op.drop_index(
        "ix_optimization_executions_updated_at",
        table_name="optimization_executions",
    )
    op.drop_index(
        "ix_optimization_executions_created_at",
        table_name="optimization_executions",
    )
    op.drop_table("optimization_executions")
