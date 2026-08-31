"""Add persistent read-only market-data connection catalog.

Revision ID: 20260831_0011
Revises: 20260827_0010
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0011"
down_revision: str | None = "20260827_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_connections",
        sa.Column("connection_id", sa.String(length=100), nullable=False),
        sa.Column("provider_id", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("health_status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "state IN ('disabled', 'enabled')",
            name=op.f("ck_market_data_connections_state_supported"),
        ),
        sa.CheckConstraint(
            "health_status IN ('untested', 'healthy', 'unhealthy')",
            name=op.f("ck_market_data_connections_health_status_supported"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name=op.f("ck_market_data_connections_updated_after_created"),
        ),
        sa.CheckConstraint(
            "last_tested_at IS NULL OR "
            "(last_tested_at >= created_at AND last_tested_at <= updated_at)",
            name=op.f("ck_market_data_connections_last_tested_in_lifecycle"),
        ),
        sa.CheckConstraint(
            "(health_status = 'untested' AND last_tested_at IS NULL AND last_error IS NULL) "
            "OR (health_status = 'healthy' AND last_tested_at IS NOT NULL "
            "AND last_error IS NULL) "
            "OR (health_status = 'unhealthy' AND last_tested_at IS NOT NULL "
            "AND last_error IS NOT NULL)",
            name=op.f("ck_market_data_connections_health_details_consistent"),
        ),
        sa.CheckConstraint(
            "state = 'disabled' OR health_status = 'healthy'",
            name=op.f("ck_market_data_connections_enabled_requires_healthy"),
        ),
        sa.PrimaryKeyConstraint(
            "connection_id",
            name=op.f("pk_market_data_connections"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_connections_provider_id"),
        "market_data_connections",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_data_connections_state"),
        "market_data_connections",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_data_connections_health_status"),
        "market_data_connections",
        ["health_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_data_connections_created_at"),
        "market_data_connections",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_data_connections_updated_at"),
        "market_data_connections",
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_market_data_connections_provider_state",
        "market_data_connections",
        ["provider_id", "state"],
        unique=False,
    )
    op.create_index(
        "ix_market_data_connections_health_updated_at",
        "market_data_connections",
        ["health_status", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_data_connections_health_updated_at",
        table_name="market_data_connections",
    )
    op.drop_index(
        "ix_market_data_connections_provider_state",
        table_name="market_data_connections",
    )
    op.drop_index(
        op.f("ix_market_data_connections_updated_at"),
        table_name="market_data_connections",
    )
    op.drop_index(
        op.f("ix_market_data_connections_created_at"),
        table_name="market_data_connections",
    )
    op.drop_index(
        op.f("ix_market_data_connections_health_status"),
        table_name="market_data_connections",
    )
    op.drop_index(
        op.f("ix_market_data_connections_state"),
        table_name="market_data_connections",
    )
    op.drop_index(
        op.f("ix_market_data_connections_provider_id"),
        table_name="market_data_connections",
    )
    op.drop_table("market_data_connections")
