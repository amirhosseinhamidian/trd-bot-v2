"""Add the durable Nexora event journal and replay cursors.

Revision ID: 20261107_0038
Revises: 20261106_0037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261107_0038"
down_revision: str | None = "20261106_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nexora_integration_events",
        sa.Column("global_sequence", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=68), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", sa.String(length=160), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("payload_schema_version", sa.String(length=120), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_checksum", sa.String(length=71), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "global_sequence >= 1",
            name=op.f("ck_nexora_integration_events_global_sequence_positive"),
        ),
        sa.CheckConstraint(
            "aggregate_version >= 1",
            name=op.f("ck_nexora_integration_events_aggregate_version_positive"),
        ),
        sa.CheckConstraint(
            "length(event_checksum) = 71",
            name=op.f("ck_nexora_integration_events_event_checksum_length"),
        ),
        sa.PrimaryKeyConstraint("global_sequence", name=op.f("pk_nexora_integration_events")),
        sa.UniqueConstraint(
            "event_checksum", name=op.f("uq_nexora_integration_events_event_checksum")
        ),
        sa.UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            name="uq_nexora_integration_events_aggregate_version",
        ),
    )
    for column in (
        "aggregate_id",
        "aggregate_type",
        "event_id",
        "event_type",
        "idempotency_key",
        "occurred_at",
        "published_at",
    ):
        op.create_index(
            op.f(f"ix_nexora_integration_events_{column}"),
            "nexora_integration_events",
            [column],
            unique=column in {"event_id", "idempotency_key"},
        )
    op.create_index(
        "ix_nexora_integration_events_aggregate_order",
        "nexora_integration_events",
        ["aggregate_type", "aggregate_id", "aggregate_version"],
    )

    op.create_table(
        "nexora_event_cursors",
        sa.Column("cursor", sa.String(length=68), nullable=False),
        sa.Column("after_sequence", sa.Integer(), nullable=False),
        sa.Column("page_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(cursor) = 68", name=op.f("ck_nexora_event_cursors_cursor_length")
        ),
        sa.CheckConstraint(
            "after_sequence >= 0", name=op.f("ck_nexora_event_cursors_after_sequence_nonnegative")
        ),
        sa.CheckConstraint(
            "page_limit >= 1 AND page_limit <= 500",
            name=op.f("ck_nexora_event_cursors_page_limit_bounded"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_nexora_event_cursors_expiry_after_create")
        ),
        sa.PrimaryKeyConstraint("cursor", name=op.f("pk_nexora_event_cursors")),
    )
    for column in ("after_sequence", "created_at", "expires_at"):
        op.create_index(op.f(f"ix_nexora_event_cursors_{column}"), "nexora_event_cursors", [column])


def downgrade() -> None:
    op.drop_table("nexora_event_cursors")
    op.drop_table("nexora_integration_events")
