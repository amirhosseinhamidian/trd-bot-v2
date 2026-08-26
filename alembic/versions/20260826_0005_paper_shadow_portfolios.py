"""Create offline paper and shadow portfolio tables.

Revision ID: 20260826_0005
Revises: 20260825_0004
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0005"
down_revision: str | None = "20260825_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulated_portfolios",
        sa.Column("portfolio_id", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("starting_cash", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("cash", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("equity", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("fee_rate", sa.Numeric(precision=18, scale=10), nullable=False),
        sa.Column("fees_paid", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "mode IN ('paper', 'shadow')",
            name="mode_supported",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'completed')",
            name="status_supported",
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name="updated_after_created",
        ),
        sa.CheckConstraint(
            "starting_cash > 0",
            name="starting_cash_positive",
        ),
        sa.CheckConstraint(
            "cash >= 0",
            name="cash_non_negative",
        ),
        sa.CheckConstraint(
            "fee_rate >= 0 AND fee_rate < 1",
            name="fee_rate_range",
        ),
        sa.CheckConstraint(
            "fees_paid >= 0",
            name="fees_paid_non_negative",
        ),
        sa.PrimaryKeyConstraint(
            "portfolio_id",
            name=op.f("pk_simulated_portfolios"),
        ),
    )
    op.create_index(
        op.f("ix_simulated_portfolios_mode"),
        "simulated_portfolios",
        ["mode"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulated_portfolios_status"),
        "simulated_portfolios",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulated_portfolios_dataset_id"),
        "simulated_portfolios",
        ["dataset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulated_portfolios_created_at"),
        "simulated_portfolios",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulated_portfolios_updated_at"),
        "simulated_portfolios",
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_simulated_portfolios_status_updated_at",
        "simulated_portfolios",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_simulated_portfolios_dataset_created_at",
        "simulated_portfolios",
        ["dataset_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_simulated_portfolios_mode_status",
        "simulated_portfolios",
        ["mode", "status"],
        unique=False,
    )

    op.create_table(
        "simulated_positions",
        sa.Column("position_id", sa.String(length=100), nullable=False),
        sa.Column("portfolio_id", sa.String(length=100), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("side", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=30, scale=10), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=30, scale=10), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_price", sa.Numeric(precision=30, scale=10), nullable=False),
        sa.Column("current_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reserved_notional", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("entry_fee", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_fee", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("gross_realized_pnl", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "side IN ('long', 'short')",
            name="side_supported",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'closed')",
            name="status_supported",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="quantity_positive",
        ),
        sa.CheckConstraint(
            "entry_price > 0 AND current_price > 0",
            name="prices_positive",
        ),
        sa.CheckConstraint(
            "reserved_notional > 0",
            name="reserved_notional_positive",
        ),
        sa.CheckConstraint(
            "entry_fee >= 0 AND exit_fee >= 0",
            name="fees_non_negative",
        ),
        sa.CheckConstraint(
            "current_at >= opened_at",
            name="current_after_opened",
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at > opened_at",
            name="closed_after_opened",
        ),
        sa.CheckConstraint(
            "(status = 'open' AND exit_price IS NULL AND closed_at IS NULL) "
            "OR (status = 'closed' AND exit_price IS NOT NULL AND closed_at IS NOT NULL)",
            name="status_exit_details_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["simulated_portfolios.portfolio_id"],
            name=op.f("fk_simulated_positions_portfolio_id_simulated_portfolios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "position_id",
            name=op.f("pk_simulated_positions"),
        ),
    )
    op.create_index(
        op.f("ix_simulated_positions_portfolio_id"),
        "simulated_positions",
        ["portfolio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulated_positions_side"),
        "simulated_positions",
        ["side"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulated_positions_status"),
        "simulated_positions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulated_positions_opened_at"),
        "simulated_positions",
        ["opened_at"],
        unique=False,
    )
    op.create_index(
        "ix_simulated_positions_portfolio_status",
        "simulated_positions",
        ["portfolio_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_simulated_positions_pair_opened_at",
        "simulated_positions",
        ["base_asset", "quote_asset", "opened_at"],
        unique=False,
    )

    op.create_table(
        "portfolio_timeline_events",
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("portfolio_id", sa.String(length=100), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("equity", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("position_id", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "sequence_number > 0",
            name="sequence_number_positive",
        ),
        sa.CheckConstraint(
            "event_type IN ('portfolio_created', 'position_opened', 'position_marked', "
            "'position_closed', 'portfolio_completed')",
            name="event_type_supported",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["simulated_portfolios.portfolio_id"],
            name=op.f("fk_portfolio_timeline_events_portfolio_id_simulated_portfolios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "event_id",
            name=op.f("pk_portfolio_timeline_events"),
        ),
        sa.UniqueConstraint(
            "portfolio_id",
            "sequence_number",
            name="portfolio_sequence_unique",
        ),
    )
    op.create_index(
        op.f("ix_portfolio_timeline_events_portfolio_id"),
        "portfolio_timeline_events",
        ["portfolio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_portfolio_timeline_events_event_type"),
        "portfolio_timeline_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_portfolio_timeline_events_occurred_at"),
        "portfolio_timeline_events",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_portfolio_timeline_events_position_id"),
        "portfolio_timeline_events",
        ["position_id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_timeline_events_portfolio_occurred_at",
        "portfolio_timeline_events",
        ["portfolio_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_timeline_events_portfolio_event_type",
        "portfolio_timeline_events",
        ["portfolio_id", "event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_timeline_events_portfolio_event_type",
        table_name="portfolio_timeline_events",
    )
    op.drop_index(
        "ix_portfolio_timeline_events_portfolio_occurred_at",
        table_name="portfolio_timeline_events",
    )
    op.drop_index(
        op.f("ix_portfolio_timeline_events_position_id"),
        table_name="portfolio_timeline_events",
    )
    op.drop_index(
        op.f("ix_portfolio_timeline_events_occurred_at"),
        table_name="portfolio_timeline_events",
    )
    op.drop_index(
        op.f("ix_portfolio_timeline_events_event_type"),
        table_name="portfolio_timeline_events",
    )
    op.drop_index(
        op.f("ix_portfolio_timeline_events_portfolio_id"),
        table_name="portfolio_timeline_events",
    )
    op.drop_table("portfolio_timeline_events")

    op.drop_index(
        "ix_simulated_positions_pair_opened_at",
        table_name="simulated_positions",
    )
    op.drop_index(
        "ix_simulated_positions_portfolio_status",
        table_name="simulated_positions",
    )
    op.drop_index(
        op.f("ix_simulated_positions_opened_at"),
        table_name="simulated_positions",
    )
    op.drop_index(
        op.f("ix_simulated_positions_status"),
        table_name="simulated_positions",
    )
    op.drop_index(
        op.f("ix_simulated_positions_side"),
        table_name="simulated_positions",
    )
    op.drop_index(
        op.f("ix_simulated_positions_portfolio_id"),
        table_name="simulated_positions",
    )
    op.drop_table("simulated_positions")

    op.drop_index(
        "ix_simulated_portfolios_mode_status",
        table_name="simulated_portfolios",
    )
    op.drop_index(
        "ix_simulated_portfolios_dataset_created_at",
        table_name="simulated_portfolios",
    )
    op.drop_index(
        "ix_simulated_portfolios_status_updated_at",
        table_name="simulated_portfolios",
    )
    op.drop_index(
        op.f("ix_simulated_portfolios_updated_at"),
        table_name="simulated_portfolios",
    )
    op.drop_index(
        op.f("ix_simulated_portfolios_created_at"),
        table_name="simulated_portfolios",
    )
    op.drop_index(
        op.f("ix_simulated_portfolios_dataset_id"),
        table_name="simulated_portfolios",
    )
    op.drop_index(
        op.f("ix_simulated_portfolios_status"),
        table_name="simulated_portfolios",
    )
    op.drop_index(
        op.f("ix_simulated_portfolios_mode"),
        table_name="simulated_portfolios",
    )
    op.drop_table("simulated_portfolios")
