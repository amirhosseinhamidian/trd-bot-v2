"""Create initial offline research storage tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_snapshots",
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("dataset_id", name="pk_dataset_snapshots"),
        sa.UniqueConstraint("checksum", name="uq_dataset_snapshots_checksum"),
    )
    op.create_index(
        "ix_dataset_snapshots_base_asset",
        "dataset_snapshots",
        ["base_asset"],
    )
    op.create_index(
        "ix_dataset_snapshots_created_at",
        "dataset_snapshots",
        ["created_at"],
    )
    op.create_index(
        "ix_dataset_snapshots_quote_asset",
        "dataset_snapshots",
        ["quote_asset"],
    )
    op.create_index(
        "ix_dataset_snapshots_source",
        "dataset_snapshots",
        ["source"],
    )

    op.create_table(
        "research_experiments",
        sa.Column("experiment_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=30), nullable=False),
        sa.Column("horizon_candles", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("experiment_id", name="pk_research_experiments"),
    )
    op.create_index(
        "ix_research_experiments_created_at",
        "research_experiments",
        ["created_at"],
    )
    op.create_index(
        "ix_research_experiments_dataset_id",
        "research_experiments",
        ["dataset_id"],
    )
    op.create_index(
        "ix_research_experiments_strategy_name",
        "research_experiments",
        ["strategy_name"],
    )

    op.create_table(
        "walk_forward_runs",
        sa.Column("execution_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_dataset_id", sa.String(length=100), nullable=False),
        sa.Column("plan_id", sa.String(length=100), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=30), nullable=False),
        sa.Column("horizon_candles", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("execution_id", name="pk_walk_forward_runs"),
    )
    op.create_index(
        "ix_walk_forward_runs_created_at",
        "walk_forward_runs",
        ["created_at"],
    )
    op.create_index(
        "ix_walk_forward_runs_plan_id",
        "walk_forward_runs",
        ["plan_id"],
    )
    op.create_index(
        "ix_walk_forward_runs_source_dataset_id",
        "walk_forward_runs",
        ["source_dataset_id"],
    )
    op.create_index(
        "ix_walk_forward_runs_strategy_name",
        "walk_forward_runs",
        ["strategy_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_walk_forward_runs_strategy_name", table_name="walk_forward_runs")
    op.drop_index("ix_walk_forward_runs_source_dataset_id", table_name="walk_forward_runs")
    op.drop_index("ix_walk_forward_runs_plan_id", table_name="walk_forward_runs")
    op.drop_index("ix_walk_forward_runs_created_at", table_name="walk_forward_runs")
    op.drop_table("walk_forward_runs")

    op.drop_index(
        "ix_research_experiments_strategy_name",
        table_name="research_experiments",
    )
    op.drop_index(
        "ix_research_experiments_dataset_id",
        table_name="research_experiments",
    )
    op.drop_index(
        "ix_research_experiments_created_at",
        table_name="research_experiments",
    )
    op.drop_table("research_experiments")

    op.drop_index("ix_dataset_snapshots_source", table_name="dataset_snapshots")
    op.drop_index("ix_dataset_snapshots_quote_asset", table_name="dataset_snapshots")
    op.drop_index("ix_dataset_snapshots_created_at", table_name="dataset_snapshots")
    op.drop_index("ix_dataset_snapshots_base_asset", table_name="dataset_snapshots")
    op.drop_table("dataset_snapshots")
