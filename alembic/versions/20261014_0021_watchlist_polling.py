"""Add durable watchlist polling schedules and evidence.

Revision ID: 20261014_0021
Revises: 20261014_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0021"
down_revision: str | None = "20261014_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_watchlist",
        sa.Column("watchlist_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("polling_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("lookback_candles", sa.Integer(), nullable=False),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_enqueued_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_job_id", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(last_enqueued_for IS NULL AND last_job_id IS NULL) OR "
            "(last_enqueued_for IS NOT NULL AND last_job_id IS NOT NULL)",
            name=op.f("ck_market_data_watchlist_enqueue_reference_consistent"),
        ),
        sa.CheckConstraint(
            "lookback_candles >= 1 AND lookback_candles <= 20",
            name=op.f("ck_market_data_watchlist_lookback_candles_bounded"),
        ),
        sa.CheckConstraint(
            "next_poll_at >= created_at",
            name=op.f("ck_market_data_watchlist_next_poll_after_created"),
        ),
        sa.CheckConstraint(
            "polling_interval_seconds >= 1",
            name=op.f("ck_market_data_watchlist_polling_interval_positive"),
        ),
        sa.CheckConstraint(
            "state IN ('active', 'paused')",
            name=op.f("ck_market_data_watchlist_state_supported"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name=op.f("ck_market_data_watchlist_updated_after_created"),
        ),
        sa.PrimaryKeyConstraint(
            "watchlist_id",
            name=op.f("pk_market_data_watchlist"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_watchlist_created_at"),
        "market_data_watchlist",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_market_data_watchlist_last_job_id"),
        "market_data_watchlist",
        ["last_job_id"],
    )
    op.create_index(
        op.f("ix_market_data_watchlist_next_poll_at"),
        "market_data_watchlist",
        ["next_poll_at"],
    )
    op.create_index(
        op.f("ix_market_data_watchlist_state"),
        "market_data_watchlist",
        ["state"],
    )
    op.create_index(
        "ix_market_data_watchlist_state_next_poll_at",
        "market_data_watchlist",
        ["state", "next_poll_at"],
    )
    op.create_index(
        "ux_market_data_watchlist_stream",
        "market_data_watchlist",
        ["base_asset", "quote_asset", "market_type", "timeframe"],
        unique=True,
    )

    op.create_table(
        "market_data_provider_budgets",
        sa.Column("provider_id", sa.String(length=50), nullable=False),
        sa.Column("tokens", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("refilled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tokens >= 0",
            name=op.f("ck_market_data_provider_budgets_tokens_nonnegative"),
        ),
        sa.CheckConstraint(
            "updated_at >= refilled_at",
            name=op.f("ck_market_data_provider_budgets_updated_after_refill"),
        ),
        sa.PrimaryKeyConstraint(
            "provider_id",
            name=op.f("pk_market_data_provider_budgets"),
        ),
    )

    op.create_table(
        "market_data_poll_runs",
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=False),
        sa.Column("job_attempt", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.String(length=100), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("selected_connection_id", sa.String(length=100), nullable=True),
        sa.Column("selected_provider_id", sa.String(length=50), nullable=True),
        sa.Column("received_candles", sa.Integer(), nullable=False),
        sa.Column("accepted_events", sa.Integer(), nullable=False),
        sa.Column("duplicate_events", sa.Integer(), nullable=False),
        sa.Column("revision_required_events", sa.Integer(), nullable=False),
        sa.Column("watermark_before_id", sa.String(length=100), nullable=True),
        sa.Column("watermark_after_id", sa.String(length=100), nullable=True),
        sa.Column("failure_retryable", sa.Boolean(), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempt_count >= 1 AND attempt_count <= 2",
            name=op.f("ck_market_data_poll_runs_attempt_count_bounded"),
        ),
        sa.CheckConstraint(
            "completed_at >= started_at",
            name=op.f("ck_market_data_poll_runs_completion_after_start"),
        ),
        sa.CheckConstraint(
            "received_candles >= 0 AND accepted_events >= 0 "
            "AND duplicate_events >= 0 AND revision_required_events >= 0",
            name=op.f("ck_market_data_poll_runs_counts_nonnegative"),
        ),
        sa.CheckConstraint(
            "job_attempt >= 1 AND job_attempt <= 10",
            name=op.f("ck_market_data_poll_runs_job_attempt_bounded"),
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND selected_connection_id IS NOT NULL "
            "AND selected_provider_id IS NOT NULL AND received_candles >= 1 "
            "AND failure_retryable = false "
            "AND failure_code IS NULL AND failure_message IS NULL) OR "
            "(status = 'no_data' AND selected_connection_id IS NULL "
            "AND selected_provider_id IS NULL AND received_candles = 0 "
            "AND failure_retryable = false "
            "AND failure_code IS NULL AND failure_message IS NULL) OR "
            "(status = 'failed' AND selected_connection_id IS NULL "
            "AND selected_provider_id IS NULL AND received_candles = 0 "
            "AND failure_code IS NOT NULL AND failure_message IS NOT NULL)",
            name=op.f("ck_market_data_poll_runs_outcome_consistent"),
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'no_data', 'failed')",
            name=op.f("ck_market_data_poll_runs_status_supported"),
        ),
        sa.PrimaryKeyConstraint(
            "run_id",
            name=op.f("pk_market_data_poll_runs"),
        ),
    )
    op.create_index(
        op.f("ix_market_data_poll_runs_completed_at"),
        "market_data_poll_runs",
        ["completed_at"],
    )
    op.create_index(
        op.f("ix_market_data_poll_runs_job_id"),
        "market_data_poll_runs",
        ["job_id"],
    )
    op.create_index(
        op.f("ix_market_data_poll_runs_scheduled_for"),
        "market_data_poll_runs",
        ["scheduled_for"],
    )
    op.create_index(
        op.f("ix_market_data_poll_runs_status"),
        "market_data_poll_runs",
        ["status"],
    )
    op.create_index(
        op.f("ix_market_data_poll_runs_watchlist_id"),
        "market_data_poll_runs",
        ["watchlist_id"],
    )
    op.create_index(
        "ix_market_data_poll_runs_status_completed_at",
        "market_data_poll_runs",
        ["status", "completed_at"],
    )
    op.create_index(
        "ix_market_data_poll_runs_watchlist_scheduled_for",
        "market_data_poll_runs",
        ["watchlist_id", "scheduled_for"],
    )
    op.create_index(
        "ux_market_data_poll_runs_job_attempt",
        "market_data_poll_runs",
        ["job_id", "job_attempt"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_market_data_poll_runs_job_attempt",
        table_name="market_data_poll_runs",
    )
    op.drop_index(
        "ix_market_data_poll_runs_watchlist_scheduled_for",
        table_name="market_data_poll_runs",
    )
    op.drop_index(
        "ix_market_data_poll_runs_status_completed_at",
        table_name="market_data_poll_runs",
    )
    op.drop_index(
        op.f("ix_market_data_poll_runs_watchlist_id"),
        table_name="market_data_poll_runs",
    )
    op.drop_index(
        op.f("ix_market_data_poll_runs_status"),
        table_name="market_data_poll_runs",
    )
    op.drop_index(
        op.f("ix_market_data_poll_runs_scheduled_for"),
        table_name="market_data_poll_runs",
    )
    op.drop_index(
        op.f("ix_market_data_poll_runs_job_id"),
        table_name="market_data_poll_runs",
    )
    op.drop_index(
        op.f("ix_market_data_poll_runs_completed_at"),
        table_name="market_data_poll_runs",
    )
    op.drop_table("market_data_poll_runs")

    op.drop_table("market_data_provider_budgets")

    op.drop_index(
        "ux_market_data_watchlist_stream",
        table_name="market_data_watchlist",
    )
    op.drop_index(
        "ix_market_data_watchlist_state_next_poll_at",
        table_name="market_data_watchlist",
    )
    op.drop_index(
        op.f("ix_market_data_watchlist_state"),
        table_name="market_data_watchlist",
    )
    op.drop_index(
        op.f("ix_market_data_watchlist_next_poll_at"),
        table_name="market_data_watchlist",
    )
    op.drop_index(
        op.f("ix_market_data_watchlist_last_job_id"),
        table_name="market_data_watchlist",
    )
    op.drop_index(
        op.f("ix_market_data_watchlist_created_at"),
        table_name="market_data_watchlist",
    )
    op.drop_table("market_data_watchlist")
