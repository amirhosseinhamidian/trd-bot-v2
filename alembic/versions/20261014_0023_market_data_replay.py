"""Add durable late-data replay and immutable revision evidence.

Revision ID: 20261014_0023
Revises: 20261014_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0023"
down_revision: str | None = "20261014_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_replay_requests",
        sa.Column("replay_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("decision_id", sa.String(length=100), nullable=False),
        sa.Column("observation_id", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("window_id", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("requested_by", sa.String(length=100), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "reason IN ('late_arrival', 'finalized_window_conflict')",
            name=op.f("ck_market_data_replay_requests_reason_supported"),
        ),
        sa.PrimaryKeyConstraint("replay_id", name=op.f("pk_market_data_replay_requests")),
    )
    for column in (
        "decision_id",
        "event_id",
        "observation_id",
        "reason",
        "requested_at",
        "window_id",
    ):
        op.create_index(
            op.f(f"ix_market_data_replay_requests_{column}"),
            "market_data_replay_requests",
            [column],
        )
    op.create_index(
        "ix_market_data_replay_requests_window_requested_at",
        "market_data_replay_requests",
        ["window_id", "requested_at"],
    )
    op.create_index(
        "ux_market_data_replay_requests_decision",
        "market_data_replay_requests",
        ["decision_id"],
        unique=True,
    )

    op.create_table(
        "market_data_window_revisions",
        sa.Column("revision_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("replay_id", sa.String(length=100), nullable=False),
        sa.Column("decision_id", sa.String(length=100), nullable=False),
        sa.Column("observation_id", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("window_id", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("previous_version", sa.Integer(), nullable=True),
        sa.Column("previous_event_id", sa.String(length=100), nullable=True),
        sa.Column("previous_payload_checksum", sa.String(length=64), nullable=True),
        sa.Column("revised_version", sa.Integer(), nullable=False),
        sa.Column("revised_payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("watermark_id", sa.String(length=100), nullable=False),
        sa.Column("watermark_version", sa.Integer(), nullable=False),
        sa.Column("watermark_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('late_insert', 'correction')",
            name=op.f("ck_market_data_window_revisions_kind_supported"),
        ),
        sa.CheckConstraint(
            "reason IN ('late_arrival', 'finalized_window_conflict')",
            name=op.f("ck_market_data_window_revisions_reason_supported"),
        ),
        sa.CheckConstraint(
            "(kind = 'late_insert' AND previous_version IS NULL "
            "AND previous_event_id IS NULL AND previous_payload_checksum IS NULL "
            "AND revised_version = 1) OR "
            "(kind = 'correction' AND previous_version IS NOT NULL "
            "AND previous_event_id IS NOT NULL AND previous_payload_checksum IS NOT NULL "
            "AND revised_version = previous_version + 1)",
            name=op.f("ck_market_data_window_revisions_version_transition_valid"),
        ),
        sa.PrimaryKeyConstraint("revision_id", name=op.f("pk_market_data_window_revisions")),
    )
    for column in (
        "applied_at",
        "decision_id",
        "event_id",
        "kind",
        "observation_id",
        "reason",
        "replay_id",
        "watermark_id",
        "window_id",
    ):
        op.create_index(
            op.f(f"ix_market_data_window_revisions_{column}"),
            "market_data_window_revisions",
            [column],
        )
    op.create_index(
        "ix_market_data_window_revisions_window_applied_at",
        "market_data_window_revisions",
        ["window_id", "applied_at"],
    )
    op.create_index(
        "ux_market_data_window_revisions_replay",
        "market_data_window_revisions",
        ["replay_id"],
        unique=True,
    )
    op.create_index(
        "ux_market_data_window_revisions_window_version",
        "market_data_window_revisions",
        ["window_id", "revised_version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("market_data_window_revisions")
    op.drop_table("market_data_replay_requests")
