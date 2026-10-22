"""Add version lineage metadata to historical market-data imports.

Revision ID: 20260831_0013
Revises: 20260831_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0013"
down_revision: str | None = "20260831_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_data_imports",
        sa.Column(
            "operation",
            sa.String(length=20),
            nullable=False,
            server_default="import",
        ),
    )
    op.add_column(
        "market_data_imports",
        sa.Column("source_dataset_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "market_data_imports",
        sa.Column("root_import_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "market_data_imports",
        sa.Column("parent_import_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "market_data_imports",
        sa.Column("version_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "market_data_imports",
        sa.Column("content_changed", sa.Boolean(), nullable=True),
    )

    op.execute(
        sa.text(
            "UPDATE market_data_imports "
            "SET root_import_id = import_id, version_number = 1 "
            "WHERE status = 'succeeded'"
        )
    )

    op.create_index(
        op.f("ix_market_data_imports_source_dataset_id"),
        "market_data_imports",
        ["source_dataset_id"],
        unique=False,
    )
    op.create_index(
        "ux_market_data_imports_root_version",
        "market_data_imports",
        ["root_import_id", "version_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_market_data_imports_root_version",
        table_name="market_data_imports",
    )
    op.drop_index(
        op.f("ix_market_data_imports_source_dataset_id"),
        table_name="market_data_imports",
    )
    op.drop_column("market_data_imports", "content_changed")
    op.drop_column("market_data_imports", "version_number")
    op.drop_column("market_data_imports", "parent_import_id")
    op.drop_column("market_data_imports", "root_import_id")
    op.drop_column("market_data_imports", "source_dataset_id")
    op.drop_column("market_data_imports", "operation")
