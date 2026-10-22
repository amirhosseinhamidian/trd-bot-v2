"""Add immutable market-data window finalization evidence.

Revision ID: 20261014_0022
Revises: 20261014_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0022"
down_revision: str | None = "20261014_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_window_finalizations",
        sa.Column("finalization_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("window_id", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("provisional_version", sa.Integer(), nullable=False),
        sa.Column("finalized_version", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("watermark_id", sa.String(length=100), nullable=False),
        sa.Column("watermark_version", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("watermark_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_seconds", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("freshness_target_seconds", sa.Integer(), nullable=False),
        sa.Column("freshness_outcome", sa.String(length=30), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "finalized_at >= window_end",
            name=op.f("ck_market_data_window_finalizations_finalized_after_window_end"),
        ),
        sa.CheckConstraint(
            "freshness_outcome IN ('within_target', 'missed_target')",
            name=op.f("ck_market_data_window_finalizations_freshness_outcome_supported"),
        ),
        sa.CheckConstraint(
            "freshness_seconds >= 0 AND freshness_target_seconds >= 1",
            name=op.f("ck_market_data_window_finalizations_freshness_values_valid"),
        ),
        sa.CheckConstraint(
            "finalized_version = provisional_version + 1",
            name=op.f("ck_market_data_window_finalizations_version_transition_valid"),
        ),
        sa.CheckConstraint(
            "watermark_time >= window_end",
            name=op.f("ck_market_data_window_finalizations_window_passed_watermark"),
        ),
        sa.PrimaryKeyConstraint(
            "finalization_id",
            name=op.f("pk_market_data_window_finalizations"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_window_finalizations_event_id"),
        "market_data_window_finalizations",
        ["event_id"],
    )
    op.create_index(
        op.f("ix_market_data_window_finalizations_finalized_at"),
        "market_data_window_finalizations",
        ["finalized_at"],
    )
    op.create_index(
        op.f("ix_market_data_window_finalizations_freshness_outcome"),
        "market_data_window_finalizations",
        ["freshness_outcome"],
    )
    op.create_index(
        op.f("ix_market_data_window_finalizations_source"),
        "market_data_window_finalizations",
        ["source"],
    )
    op.create_index(
        op.f("ix_market_data_window_finalizations_timeframe"),
        "market_data_window_finalizations",
        ["timeframe"],
    )
    op.create_index(
        op.f("ix_market_data_window_finalizations_watermark_id"),
        "market_data_window_finalizations",
        ["watermark_id"],
    )
    op.create_index(
        op.f("ix_market_data_window_finalizations_window_end"),
        "market_data_window_finalizations",
        ["window_end"],
    )
    op.create_index(
        op.f("ix_market_data_window_finalizations_window_id"),
        "market_data_window_finalizations",
        ["window_id"],
    )
    op.create_index(
        "ix_market_data_window_finalizations_outcome_finalized_at",
        "market_data_window_finalizations",
        ["freshness_outcome", "finalized_at"],
    )
    op.create_index(
        "ix_market_data_window_finalizations_stream_finalized_at",
        "market_data_window_finalizations",
        [
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            "finalized_at",
        ],
    )
    op.create_index(
        "ux_market_data_window_finalizations_window_version",
        "market_data_window_finalizations",
        ["window_id", "finalized_version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_market_data_window_finalizations_window_version",
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        "ix_market_data_window_finalizations_stream_finalized_at",
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        "ix_market_data_window_finalizations_outcome_finalized_at",
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        op.f("ix_market_data_window_finalizations_window_id"),
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        op.f("ix_market_data_window_finalizations_window_end"),
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        op.f("ix_market_data_window_finalizations_watermark_id"),
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        op.f("ix_market_data_window_finalizations_timeframe"),
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        op.f("ix_market_data_window_finalizations_source"),
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        op.f("ix_market_data_window_finalizations_freshness_outcome"),
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        op.f("ix_market_data_window_finalizations_finalized_at"),
        table_name="market_data_window_finalizations",
    )
    op.drop_index(
        op.f("ix_market_data_window_finalizations_event_id"),
        table_name="market_data_window_finalizations",
    )
    op.drop_table("market_data_window_finalizations")
