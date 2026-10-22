"""Add retention holds, serialized control, and immutable purge audit.

Revision ID: 20261015_0024
Revises: 20261014_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0024"
down_revision: str | None = "20261014_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_retention_control",
        sa.Column("control_id", sa.String(length=100), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "control_id = 'market-data-retention-control'",
            name=op.f("ck_market_data_retention_control_singleton_identity"),
        ),
        sa.PrimaryKeyConstraint(
            "control_id",
            name=op.f("pk_market_data_retention_control"),
        ),
    )
    op.execute(
        sa.insert(
            sa.table(
                "market_data_retention_control",
                sa.column("control_id", sa.String()),
            )
        ).values(control_id="market-data-retention-control")
    )

    op.create_table(
        "market_data_retention_holds",
        sa.Column("hold_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("placed_by", sa.String(length=100), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_by", sa.String(length=100), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('legal', 'incident')",
            name=op.f("ck_market_data_retention_holds_kind_supported"),
        ),
        sa.CheckConstraint(
            "(released_by IS NULL AND released_at IS NULL) OR "
            "(released_by IS NOT NULL AND released_at IS NOT NULL)",
            name=op.f("ck_market_data_retention_holds_release_consistent"),
        ),
        sa.CheckConstraint(
            "released_at IS NULL OR released_at >= placed_at",
            name=op.f("ck_market_data_retention_holds_release_after_placement"),
        ),
        sa.PrimaryKeyConstraint("hold_id", name=op.f("pk_market_data_retention_holds")),
    )
    for column in ("kind", "placed_at", "released_at"):
        op.create_index(
            op.f(f"ix_market_data_retention_holds_{column}"),
            "market_data_retention_holds",
            [column],
        )
    op.create_index(
        "ix_market_data_retention_holds_active",
        "market_data_retention_holds",
        ["released_at", "placed_at"],
    )

    op.create_table(
        "market_data_retention_runs",
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("requested_by", sa.String(length=100), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("batch_limit", sa.Integer(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("deleted_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "mode IN ('dry_run', 'execute')",
            name=op.f("ck_market_data_retention_runs_mode_supported"),
        ),
        sa.CheckConstraint(
            "outcome IN ('completed', 'blocked', 'failed')",
            name=op.f("ck_market_data_retention_runs_outcome_supported"),
        ),
        sa.CheckConstraint(
            "batch_limit >= 1 AND batch_limit <= 500",
            name=op.f("ck_market_data_retention_runs_batch_limit_bounded"),
        ),
        sa.CheckConstraint(
            "selected_count >= 0",
            name=op.f("ck_market_data_retention_runs_selected_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "deleted_count >= 0",
            name=op.f("ck_market_data_retention_runs_deleted_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "completed_at >= requested_at",
            name=op.f("ck_market_data_retention_runs_completion_after_request"),
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_market_data_retention_runs")),
    )
    for column in ("completed_at", "mode", "outcome", "requested_at"):
        op.create_index(
            op.f(f"ix_market_data_retention_runs_{column}"),
            "market_data_retention_runs",
            [column],
        )
    op.create_index(
        "ix_market_data_retention_runs_outcome_completed_at",
        "market_data_retention_runs",
        ["outcome", "completed_at"],
    )


def downgrade() -> None:
    op.drop_table("market_data_retention_runs")
    op.drop_table("market_data_retention_holds")
    op.drop_table("market_data_retention_control")
