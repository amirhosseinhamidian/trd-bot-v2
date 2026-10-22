"""Add durable market-data ingestion decision evidence.

Revision ID: 20261014_0020
Revises: 20261014_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0020"
down_revision: str | None = "20261014_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_event_decisions",
        sa.Column("decision_id", sa.String(length=100), nullable=False),
        sa.Column("observation_id", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("watermark_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("window_id", sa.String(length=100), nullable=False),
        sa.Column("arrival", sa.String(length=20), nullable=False),
        sa.Column("disposition", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("existing_window_version", sa.Integer(), nullable=True),
        sa.Column("proposed_window_version", sa.Integer(), nullable=True),
        sa.Column("requires_replay", sa.Boolean(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "arrival IN ('on_time', 'late')",
            name=op.f("ck_market_data_event_decisions_arrival_supported"),
        ),
        sa.CheckConstraint(
            "(disposition = 'duplicate' AND proposed_window_version IS NULL "
            "AND requires_replay = false) OR "
            "(disposition = 'accepted' AND proposed_window_version IS NOT NULL "
            "AND requires_replay = false) OR "
            "(disposition = 'revision_required' AND proposed_window_version IS NOT NULL "
            "AND requires_replay = true)",
            name=op.f("ck_market_data_event_decisions_decision_consistent"),
        ),
        sa.CheckConstraint(
            "disposition IN ('accepted', 'duplicate', 'revision_required')",
            name=op.f("ck_market_data_event_decisions_disposition_supported"),
        ),
        sa.CheckConstraint(
            "existing_window_version IS NULL OR existing_window_version >= 1",
            name=op.f("ck_market_data_event_decisions_existing_version_positive"),
        ),
        sa.CheckConstraint(
            "proposed_window_version IS NULL OR proposed_window_version >= 1",
            name=op.f("ck_market_data_event_decisions_proposed_version_positive"),
        ),
        sa.CheckConstraint(
            "reason IN ('new_window', 'provisional_update', 'duplicate_payload', "
            "'late_arrival', 'finalized_window_conflict')",
            name=op.f("ck_market_data_event_decisions_reason_supported"),
        ),
        sa.PrimaryKeyConstraint(
            "decision_id",
            name=op.f("pk_market_data_event_decisions"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_event_decisions_decided_at"),
        "market_data_event_decisions",
        ["decided_at"],
    )
    op.create_index(
        op.f("ix_market_data_event_decisions_disposition"),
        "market_data_event_decisions",
        ["disposition"],
    )
    op.create_index(
        "ix_market_data_event_decisions_disposition_decided_at",
        "market_data_event_decisions",
        ["disposition", "decided_at"],
    )
    op.create_index(
        op.f("ix_market_data_event_decisions_event_id"),
        "market_data_event_decisions",
        ["event_id"],
    )
    op.create_index(
        op.f("ix_market_data_event_decisions_reason"),
        "market_data_event_decisions",
        ["reason"],
    )
    op.create_index(
        op.f("ix_market_data_event_decisions_watermark_id"),
        "market_data_event_decisions",
        ["watermark_id"],
    )
    op.create_index(
        op.f("ix_market_data_event_decisions_window_id"),
        "market_data_event_decisions",
        ["window_id"],
    )
    op.create_index(
        "ix_market_data_event_decisions_window_decided_at",
        "market_data_event_decisions",
        ["window_id", "decided_at"],
    )
    op.create_index(
        "ux_market_data_event_decisions_observation",
        "market_data_event_decisions",
        ["observation_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_market_data_event_decisions_observation",
        table_name="market_data_event_decisions",
    )
    op.drop_index(
        "ix_market_data_event_decisions_window_decided_at",
        table_name="market_data_event_decisions",
    )
    op.drop_index(
        op.f("ix_market_data_event_decisions_window_id"),
        table_name="market_data_event_decisions",
    )
    op.drop_index(
        op.f("ix_market_data_event_decisions_watermark_id"),
        table_name="market_data_event_decisions",
    )
    op.drop_index(
        op.f("ix_market_data_event_decisions_reason"),
        table_name="market_data_event_decisions",
    )
    op.drop_index(
        op.f("ix_market_data_event_decisions_event_id"),
        table_name="market_data_event_decisions",
    )
    op.drop_index(
        "ix_market_data_event_decisions_disposition_decided_at",
        table_name="market_data_event_decisions",
    )
    op.drop_index(
        op.f("ix_market_data_event_decisions_disposition"),
        table_name="market_data_event_decisions",
    )
    op.drop_index(
        op.f("ix_market_data_event_decisions_decided_at"),
        table_name="market_data_event_decisions",
    )
    op.drop_table("market_data_event_decisions")
