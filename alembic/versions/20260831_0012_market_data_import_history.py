"""Persist historical market-data import history.

Revision ID: 20260831_0012
Revises: 20260831_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0012"
down_revision: str | None = "20260831_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_imports",
        sa.Column("import_id", sa.String(length=100), nullable=False),
        sa.Column("connection_id", sa.String(length=100), nullable=False),
        sa.Column("provider_id", sa.String(length=100), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("requested_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name=op.f("ck_market_data_imports_status_supported"),
        ),
        sa.CheckConstraint(
            "requested_end_time > requested_start_time",
            name=op.f("ck_market_data_imports_requested_range_valid"),
        ),
        sa.CheckConstraint(
            "completed_at >= created_at",
            name=op.f("ck_market_data_imports_completed_after_created"),
        ),
        sa.CheckConstraint(
            "candle_count >= 0",
            name=op.f("ck_market_data_imports_candle_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND dataset_id IS NOT NULL AND candle_count > 0 "
            "AND error_code IS NULL AND error_message IS NULL) OR "
            "(status = 'failed' AND dataset_id IS NULL "
            "AND error_code IS NOT NULL AND error_message IS NOT NULL)",
            name=op.f("ck_market_data_imports_outcome_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["market_data_connections.connection_id"],
            name=op.f("fk_market_data_imports_connection_id_market_data_connections"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["dataset_snapshots.dataset_id"],
            name=op.f("fk_market_data_imports_dataset_id_dataset_snapshots"),
        ),
        sa.PrimaryKeyConstraint("import_id", name=op.f("pk_market_data_imports")),
    )
    op.create_index(
        op.f("ix_market_data_imports_provider_id"),
        "market_data_imports",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_data_imports_status"),
        "market_data_imports",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_data_imports_created_at"),
        "market_data_imports",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_data_imports_dataset_id"),
        "market_data_imports",
        ["dataset_id"],
        unique=False,
    )
    op.create_index(
        "ix_market_data_imports_connection_created_at",
        "market_data_imports",
        ["connection_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_market_data_imports_status_created_at",
        "market_data_imports",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_data_imports_status_created_at", table_name="market_data_imports")
    op.drop_index("ix_market_data_imports_connection_created_at", table_name="market_data_imports")
    op.drop_index(op.f("ix_market_data_imports_dataset_id"), table_name="market_data_imports")
    op.drop_index(op.f("ix_market_data_imports_created_at"), table_name="market_data_imports")
    op.drop_index(op.f("ix_market_data_imports_status"), table_name="market_data_imports")
    op.drop_index(op.f("ix_market_data_imports_provider_id"), table_name="market_data_imports")
    op.drop_table("market_data_imports")
