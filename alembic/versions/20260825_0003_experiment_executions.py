"""Create persistent experiment execution table.

Revision ID: 20260825_0003
Revises: 20260824_0002
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0003"
down_revision: str | None = "20260824_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_executions",
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
            "experiment_id",
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
            name=op.f("pk_experiment_executions"),
        ),
    )

    op.create_index(
        op.f("ix_experiment_executions_created_at"),
        "experiment_executions",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        op.f("ix_experiment_executions_updated_at"),
        "experiment_executions",
        ["updated_at"],
        unique=False,
    )

    op.create_index(
        op.f("ix_experiment_executions_status"),
        "experiment_executions",
        ["status"],
        unique=False,
    )

    op.create_index(
        op.f("ix_experiment_executions_dataset_id"),
        "experiment_executions",
        ["dataset_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_experiment_executions_strategy_name"),
        "experiment_executions",
        ["strategy_name"],
        unique=False,
    )

    op.create_index(
        op.f("ix_experiment_executions_experiment_id"),
        "experiment_executions",
        ["experiment_id"],
        unique=False,
    )

    op.create_index(
        "ix_experiment_executions_status_updated_at",
        "experiment_executions",
        ["status", "updated_at"],
        unique=False,
    )

    op.create_index(
        "ix_experiment_executions_dataset_created_at",
        "experiment_executions",
        ["dataset_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_experiment_executions_dataset_created_at",
        table_name="experiment_executions",
    )

    op.drop_index(
        "ix_experiment_executions_status_updated_at",
        table_name="experiment_executions",
    )

    op.drop_index(
        op.f("ix_experiment_executions_experiment_id"),
        table_name="experiment_executions",
    )

    op.drop_index(
        op.f("ix_experiment_executions_strategy_name"),
        table_name="experiment_executions",
    )

    op.drop_index(
        op.f("ix_experiment_executions_dataset_id"),
        table_name="experiment_executions",
    )

    op.drop_index(
        op.f("ix_experiment_executions_status"),
        table_name="experiment_executions",
    )

    op.drop_index(
        op.f("ix_experiment_executions_updated_at"),
        table_name="experiment_executions",
    )

    op.drop_index(
        op.f("ix_experiment_executions_created_at"),
        table_name="experiment_executions",
    )

    op.drop_table("experiment_executions")
