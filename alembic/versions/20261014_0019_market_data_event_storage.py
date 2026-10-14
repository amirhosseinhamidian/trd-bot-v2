"""Add durable market-data event and window storage.

Revision ID: 20261014_0019
Revises: 20261010_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0019"
down_revision: str | None = "20261010_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_raw_observations",
        sa.Column("observation_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(payload_checksum) = 64",
            name=op.f("ck_market_data_raw_observations_checksum_length"),
        ),
        sa.CheckConstraint(
            "window_end > window_start",
            name=op.f("ck_market_data_raw_observations_window_range_valid"),
        ),
        sa.PrimaryKeyConstraint(
            "observation_id",
            name=op.f("pk_market_data_raw_observations"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_raw_observations_created_at"),
        "market_data_raw_observations",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_market_data_raw_observations_observed_at"),
        "market_data_raw_observations",
        ["observed_at"],
    )
    op.create_index(
        op.f("ix_market_data_raw_observations_payload_checksum"),
        "market_data_raw_observations",
        ["payload_checksum"],
    )
    op.create_index(
        op.f("ix_market_data_raw_observations_source"),
        "market_data_raw_observations",
        ["source"],
    )
    op.create_index(
        "ix_market_data_raw_observations_stream_observed_at",
        "market_data_raw_observations",
        [
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            "observed_at",
        ],
    )
    op.create_index(
        "ix_market_data_raw_observations_window_end",
        "market_data_raw_observations",
        ["window_end"],
    )

    op.create_table(
        "market_data_events",
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("raw_observation_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_id", sa.String(length=100), nullable=False),
        sa.Column("payload_version", sa.String(length=50), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("persisted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(payload_checksum) = 64",
            name=op.f("ck_market_data_events_checksum_length"),
        ),
        sa.CheckConstraint(
            "kind = 'candle_observed'",
            name=op.f("ck_market_data_events_kind_supported"),
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_market_data_events")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_market_data_events_idempotency_key"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_events_event_time"),
        "market_data_events",
        ["event_time"],
    )
    op.create_index(
        op.f("ix_market_data_events_payload_checksum"),
        "market_data_events",
        ["payload_checksum"],
    )
    op.create_index(
        op.f("ix_market_data_events_persisted_at"),
        "market_data_events",
        ["persisted_at"],
    )
    op.create_index(
        op.f("ix_market_data_events_raw_observation_id"),
        "market_data_events",
        ["raw_observation_id"],
    )
    op.create_index(
        op.f("ix_market_data_events_source"),
        "market_data_events",
        ["source"],
    )
    op.create_index(
        "ix_market_data_events_stream_event_time",
        "market_data_events",
        ["source", "base_asset", "quote_asset", "market_type", "timeframe", "event_time"],
    )
    op.create_index(
        op.f("ix_market_data_events_window_id"),
        "market_data_events",
        ["window_id"],
    )
    op.create_index(
        "ix_market_data_events_window_event_time",
        "market_data_events",
        ["window_id", "event_time"],
    )

    op.create_table(
        "market_data_event_inbox",
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_count", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "delivery_count >= 1",
            name=op.f("ck_market_data_event_inbox_delivery_count_positive"),
        ),
        sa.CheckConstraint(
            "length(payload_checksum) = 64",
            name=op.f("ck_market_data_event_inbox_checksum_length"),
        ),
        sa.CheckConstraint(
            "last_seen_at >= first_seen_at",
            name=op.f("ck_market_data_event_inbox_seen_range_valid"),
        ),
        sa.PrimaryKeyConstraint(
            "idempotency_key",
            name=op.f("pk_market_data_event_inbox"),
        ),
        sa.UniqueConstraint(
            "event_id",
            name=op.f("uq_market_data_event_inbox_event_id"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_event_inbox_first_seen_at"),
        "market_data_event_inbox",
        ["first_seen_at"],
    )
    op.create_index(
        "ix_market_data_event_inbox_last_seen_at",
        "market_data_event_inbox",
        ["last_seen_at"],
    )
    op.create_index(
        op.f("ix_market_data_event_inbox_payload_checksum"),
        "market_data_event_inbox",
        ["payload_checksum"],
    )

    op.create_table(
        "market_data_outbox",
        sa.Column("outbox_id", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("payload_version", sa.String(length=50), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 20",
            name=op.f("ck_market_data_outbox_attempt_count_range"),
        ),
        sa.CheckConstraint(
            "available_at >= created_at",
            name=op.f("ck_market_data_outbox_available_after_created"),
        ),
        sa.CheckConstraint(
            "delivered_at IS NULL OR delivered_at >= created_at",
            name=op.f("ck_market_data_outbox_delivered_after_created"),
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND delivered_at IS NULL "
            "AND error_code IS NULL AND error_message IS NULL) OR "
            "(status = 'delivered' AND delivered_at IS NOT NULL "
            "AND error_code IS NULL AND error_message IS NULL) OR "
            "(status = 'failed' AND delivered_at IS NULL "
            "AND error_code IS NOT NULL AND error_message IS NOT NULL)",
            name=op.f("ck_market_data_outbox_outcome_consistent"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name=op.f("ck_market_data_outbox_status_supported"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name=op.f("ck_market_data_outbox_updated_after_created"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["market_data_events.event_id"],
            name=op.f("fk_market_data_outbox_event_id_market_data_events"),
        ),
        sa.PrimaryKeyConstraint("outbox_id", name=op.f("pk_market_data_outbox")),
    )
    op.create_index(
        op.f("ix_market_data_outbox_available_at"),
        "market_data_outbox",
        ["available_at"],
    )
    op.create_index(
        op.f("ix_market_data_outbox_created_at"),
        "market_data_outbox",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_market_data_outbox_event_id"),
        "market_data_outbox",
        ["event_id"],
    )
    op.create_index(
        op.f("ix_market_data_outbox_status"),
        "market_data_outbox",
        ["status"],
    )
    op.create_index(
        "ix_market_data_outbox_status_available_at",
        "market_data_outbox",
        ["status", "available_at"],
    )
    op.create_index(
        "ux_market_data_outbox_event_topic_version",
        "market_data_outbox",
        ["event_id", "topic", "payload_version"],
        unique=True,
    )

    op.create_table(
        "market_data_window_versions",
        sa.Column("window_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(payload_checksum) = 64",
            name=op.f("ck_market_data_window_versions_checksum_length"),
        ),
        sa.CheckConstraint(
            "finalized_at IS NULL OR finalized_at >= created_at",
            name=op.f("ck_market_data_window_versions_finalized_after_created"),
        ),
        sa.CheckConstraint(
            "(state = 'provisional' AND finalized_at IS NULL) OR "
            "(state = 'finalized' AND finalized_at IS NOT NULL)",
            name=op.f("ck_market_data_window_versions_finalization_consistent"),
        ),
        sa.CheckConstraint(
            "state IN ('provisional', 'finalized')",
            name=op.f("ck_market_data_window_versions_state_supported"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_market_data_window_versions_version_positive"),
        ),
        sa.CheckConstraint(
            "window_end > window_start",
            name=op.f("ck_market_data_window_versions_window_range_valid"),
        ),
        sa.PrimaryKeyConstraint(
            "window_id",
            "version",
            name=op.f("pk_market_data_window_versions"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_window_versions_created_at"),
        "market_data_window_versions",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_market_data_window_versions_event_id"),
        "market_data_window_versions",
        ["event_id"],
    )
    op.create_index(
        op.f("ix_market_data_window_versions_payload_checksum"),
        "market_data_window_versions",
        ["payload_checksum"],
    )
    op.create_index(
        op.f("ix_market_data_window_versions_source"),
        "market_data_window_versions",
        ["source"],
    )
    op.create_index(
        op.f("ix_market_data_window_versions_state"),
        "market_data_window_versions",
        ["state"],
    )
    op.create_index(
        "ix_market_data_window_versions_state_window_end",
        "market_data_window_versions",
        ["state", "window_end"],
    )
    op.create_index(
        "ix_market_data_window_versions_stream_window_end",
        "market_data_window_versions",
        ["source", "base_asset", "quote_asset", "market_type", "timeframe", "window_end"],
    )
    op.create_index(
        op.f("ix_market_data_window_versions_window_end"),
        "market_data_window_versions",
        ["window_end"],
    )

    op.create_table(
        "market_data_watermarks",
        sa.Column("watermark_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("high_water_event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("allowed_lateness_seconds", sa.Integer(), nullable=False),
        sa.Column("watermark_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "allowed_lateness_seconds >= 0",
            name=op.f("ck_market_data_watermarks_allowed_lateness_nonnegative"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_market_data_watermarks_version_positive"),
        ),
        sa.CheckConstraint(
            "watermark_time <= high_water_event_time",
            name=op.f("ck_market_data_watermarks_watermark_not_after_high_water"),
        ),
        sa.PrimaryKeyConstraint(
            "watermark_id",
            name=op.f("pk_market_data_watermarks"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_watermarks_calculated_at"),
        "market_data_watermarks",
        ["calculated_at"],
    )
    op.create_index(
        op.f("ix_market_data_watermarks_source"),
        "market_data_watermarks",
        ["source"],
    )
    op.create_index(
        "ix_market_data_watermarks_stream_calculated_at",
        "market_data_watermarks",
        ["source", "base_asset", "quote_asset", "market_type", "timeframe", "calculated_at"],
    )
    op.create_index(
        op.f("ix_market_data_watermarks_watermark_time"),
        "market_data_watermarks",
        ["watermark_time"],
    )
    op.create_index(
        "ux_market_data_watermarks_stream_version",
        "market_data_watermarks",
        ["source", "base_asset", "quote_asset", "market_type", "timeframe", "version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_market_data_watermarks_stream_version",
        table_name="market_data_watermarks",
    )
    op.drop_index(
        op.f("ix_market_data_watermarks_watermark_time"),
        table_name="market_data_watermarks",
    )
    op.drop_index(
        "ix_market_data_watermarks_stream_calculated_at",
        table_name="market_data_watermarks",
    )
    op.drop_index(
        op.f("ix_market_data_watermarks_source"),
        table_name="market_data_watermarks",
    )
    op.drop_index(
        op.f("ix_market_data_watermarks_calculated_at"),
        table_name="market_data_watermarks",
    )
    op.drop_table("market_data_watermarks")

    op.drop_index(
        op.f("ix_market_data_window_versions_window_end"),
        table_name="market_data_window_versions",
    )
    op.drop_index(
        "ix_market_data_window_versions_stream_window_end",
        table_name="market_data_window_versions",
    )
    op.drop_index(
        "ix_market_data_window_versions_state_window_end",
        table_name="market_data_window_versions",
    )
    op.drop_index(
        op.f("ix_market_data_window_versions_state"),
        table_name="market_data_window_versions",
    )
    op.drop_index(
        op.f("ix_market_data_window_versions_source"),
        table_name="market_data_window_versions",
    )
    op.drop_index(
        op.f("ix_market_data_window_versions_payload_checksum"),
        table_name="market_data_window_versions",
    )
    op.drop_index(
        op.f("ix_market_data_window_versions_event_id"),
        table_name="market_data_window_versions",
    )
    op.drop_index(
        op.f("ix_market_data_window_versions_created_at"),
        table_name="market_data_window_versions",
    )
    op.drop_table("market_data_window_versions")

    op.drop_index(
        "ux_market_data_outbox_event_topic_version",
        table_name="market_data_outbox",
    )
    op.drop_index(
        "ix_market_data_outbox_status_available_at",
        table_name="market_data_outbox",
    )
    op.drop_index(
        op.f("ix_market_data_outbox_status"),
        table_name="market_data_outbox",
    )
    op.drop_index(
        op.f("ix_market_data_outbox_event_id"),
        table_name="market_data_outbox",
    )
    op.drop_index(
        op.f("ix_market_data_outbox_created_at"),
        table_name="market_data_outbox",
    )
    op.drop_index(
        op.f("ix_market_data_outbox_available_at"),
        table_name="market_data_outbox",
    )
    op.drop_table("market_data_outbox")

    op.drop_index(
        op.f("ix_market_data_event_inbox_payload_checksum"),
        table_name="market_data_event_inbox",
    )
    op.drop_index(
        "ix_market_data_event_inbox_last_seen_at",
        table_name="market_data_event_inbox",
    )
    op.drop_index(
        op.f("ix_market_data_event_inbox_first_seen_at"),
        table_name="market_data_event_inbox",
    )
    op.drop_table("market_data_event_inbox")

    op.drop_index(
        "ix_market_data_events_window_event_time",
        table_name="market_data_events",
    )
    op.drop_index(
        op.f("ix_market_data_events_window_id"),
        table_name="market_data_events",
    )
    op.drop_index(
        "ix_market_data_events_stream_event_time",
        table_name="market_data_events",
    )
    op.drop_index(
        op.f("ix_market_data_events_source"),
        table_name="market_data_events",
    )
    op.drop_index(
        op.f("ix_market_data_events_raw_observation_id"),
        table_name="market_data_events",
    )
    op.drop_index(
        op.f("ix_market_data_events_persisted_at"),
        table_name="market_data_events",
    )
    op.drop_index(
        op.f("ix_market_data_events_payload_checksum"),
        table_name="market_data_events",
    )
    op.drop_index(
        op.f("ix_market_data_events_event_time"),
        table_name="market_data_events",
    )
    op.drop_table("market_data_events")

    op.drop_index(
        "ix_market_data_raw_observations_window_end",
        table_name="market_data_raw_observations",
    )
    op.drop_index(
        "ix_market_data_raw_observations_stream_observed_at",
        table_name="market_data_raw_observations",
    )
    op.drop_index(
        op.f("ix_market_data_raw_observations_source"),
        table_name="market_data_raw_observations",
    )
    op.drop_index(
        op.f("ix_market_data_raw_observations_payload_checksum"),
        table_name="market_data_raw_observations",
    )
    op.drop_index(
        op.f("ix_market_data_raw_observations_observed_at"),
        table_name="market_data_raw_observations",
    )
    op.drop_index(
        op.f("ix_market_data_raw_observations_created_at"),
        table_name="market_data_raw_observations",
    )
    op.drop_table("market_data_raw_observations")
