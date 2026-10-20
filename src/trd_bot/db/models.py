from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from trd_bot.db.base import DatabaseBase


class MarketDataConnectionRow(DatabaseBase):
    """Persistent configuration and health state for one read-only data connector."""

    __tablename__ = "market_data_connections"

    __table_args__ = (
        CheckConstraint(
            "state IN ('disabled', 'enabled')",
            name="state_supported",
        ),
        CheckConstraint(
            "health_status IN ('untested', 'healthy', 'unhealthy')",
            name="health_status_supported",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="updated_after_created",
        ),
        CheckConstraint(
            "last_tested_at IS NULL OR "
            "(last_tested_at >= created_at AND last_tested_at <= updated_at)",
            name="last_tested_in_lifecycle",
        ),
        CheckConstraint(
            "(health_status = 'untested' AND last_tested_at IS NULL "
            "AND last_error_code IS NULL AND last_error IS NULL) "
            "OR (health_status = 'healthy' AND last_tested_at IS NOT NULL "
            "AND last_error_code IS NULL AND last_error IS NULL) "
            "OR (health_status = 'unhealthy' AND last_tested_at IS NOT NULL "
            "AND last_error_code IS NOT NULL AND last_error IS NOT NULL)",
            name="health_details_consistent",
        ),
        CheckConstraint(
            "state = 'disabled' OR health_status = 'healthy'",
            name="enabled_requires_healthy",
        ),
        Index(
            "ix_market_data_connections_provider_state",
            "provider_id",
            "state",
        ),
        Index(
            "ix_market_data_connections_health_updated_at",
            "health_status",
            "updated_at",
        ),
    )

    connection_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(100), index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(20), index=True)
    health_status: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketDataWatchlistRow(DatabaseBase):
    """Durable polling schedule for one normalized market-data stream."""

    __tablename__ = "market_data_watchlist"

    __table_args__ = (
        CheckConstraint("state IN ('active', 'paused')", name="state_supported"),
        CheckConstraint("polling_interval_seconds >= 1", name="polling_interval_positive"),
        CheckConstraint(
            "lookback_candles >= 1 AND lookback_candles <= 20",
            name="lookback_candles_bounded",
        ),
        CheckConstraint("updated_at >= created_at", name="updated_after_created"),
        CheckConstraint("next_poll_at >= created_at", name="next_poll_after_created"),
        CheckConstraint(
            "(last_enqueued_for IS NULL AND last_job_id IS NULL) OR "
            "(last_enqueued_for IS NOT NULL AND last_job_id IS NOT NULL)",
            name="enqueue_reference_consistent",
        ),
        Index(
            "ux_market_data_watchlist_stream",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            unique=True,
        ),
        Index(
            "ix_market_data_watchlist_state_next_poll_at",
            "state",
            "next_poll_at",
        ),
    )

    watchlist_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), index=True)
    policy_version: Mapped[str] = mapped_column(String(50))
    polling_interval_seconds: Mapped[int] = mapped_column(Integer)
    lookback_candles: Mapped[int] = mapped_column(Integer)
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_enqueued_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketDataProviderBudgetRow(DatabaseBase):
    """Durable token-bucket state shared by polling workers."""

    __tablename__ = "market_data_provider_budgets"

    __table_args__ = (
        CheckConstraint("tokens >= 0", name="tokens_nonnegative"),
        CheckConstraint("updated_at >= refilled_at", name="updated_after_refill"),
    )

    provider_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tokens: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    refilled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketDataPollRunRow(DatabaseBase):
    """Sanitized terminal evidence for one polling background-job attempt."""

    __tablename__ = "market_data_poll_runs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'no_data', 'failed')",
            name="status_supported",
        ),
        CheckConstraint("job_attempt >= 1 AND job_attempt <= 10", name="job_attempt_bounded"),
        CheckConstraint("attempt_count >= 1 AND attempt_count <= 2", name="attempt_count_bounded"),
        CheckConstraint(
            "received_candles >= 0 AND accepted_events >= 0 "
            "AND duplicate_events >= 0 AND revision_required_events >= 0",
            name="counts_nonnegative",
        ),
        CheckConstraint("completed_at >= started_at", name="completion_after_start"),
        CheckConstraint(
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
            name="outcome_consistent",
        ),
        Index(
            "ux_market_data_poll_runs_job_attempt",
            "job_id",
            "job_attempt",
            unique=True,
        ),
        Index(
            "ix_market_data_poll_runs_watchlist_scheduled_for",
            "watchlist_id",
            "scheduled_for",
        ),
        Index(
            "ix_market_data_poll_runs_status_completed_at",
            "status",
            "completed_at",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    job_id: Mapped[str] = mapped_column(String(100), index=True)
    job_attempt: Mapped[int] = mapped_column(Integer)
    watchlist_id: Mapped[str] = mapped_column(String(100), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    selected_connection_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    selected_provider_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    received_candles: Mapped[int] = mapped_column(Integer)
    accepted_events: Mapped[int] = mapped_column(Integer)
    duplicate_events: Mapped[int] = mapped_column(Integer)
    revision_required_events: Mapped[int] = mapped_column(Integer)
    watermark_before_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    watermark_after_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketDataImportRow(DatabaseBase):
    """Immutable audit row for one historical market-data dataset import attempt."""

    __tablename__ = "market_data_imports"

    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="status_supported",
        ),
        CheckConstraint(
            "requested_end_time > requested_start_time",
            name="requested_range_valid",
        ),
        CheckConstraint(
            "completed_at >= created_at",
            name="completed_after_created",
        ),
        CheckConstraint(
            "candle_count >= 0",
            name="candle_count_nonnegative",
        ),
        CheckConstraint(
            "(status = 'succeeded' AND dataset_id IS NOT NULL AND candle_count > 0 "
            "AND error_code IS NULL AND error_message IS NULL) OR "
            "(status = 'failed' AND dataset_id IS NULL "
            "AND error_code IS NOT NULL AND error_message IS NOT NULL)",
            name="outcome_consistent",
        ),
        Index(
            "ix_market_data_imports_connection_created_at",
            "connection_id",
            "created_at",
        ),
        Index(
            "ix_market_data_imports_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "ux_market_data_imports_root_version",
            "root_import_id",
            "version_number",
            unique=True,
        ),
    )

    import_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("market_data_connections.connection_id"),
    )
    provider_id: Mapped[str] = mapped_column(String(100), index=True)
    dataset_name: Mapped[str] = mapped_column(String(100))
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    requested_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), index=True)
    candle_count: Mapped[int] = mapped_column(Integer)
    dataset_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("dataset_snapshots.dataset_id"),
        nullable=True,
        index=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation: Mapped[str] = mapped_column(String(20), server_default="import")
    source_dataset_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    root_import_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parent_import_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_changed: Mapped[bool | None] = mapped_column(nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)


class DatasetSnapshotRow(DatabaseBase):
    """Serialized immutable market-data snapshot metadata and payload."""

    __tablename__ = "dataset_snapshots"

    dataset_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    base_asset: Mapped[str] = mapped_column(String(30), index=True)
    quote_asset: Mapped[str] = mapped_column(String(30), index=True)
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    candle_count: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class DatasetFileStageRow(DatabaseBase):
    """Temporary bounded upload bytes consumed by a durable import job."""

    __tablename__ = "dataset_file_stages"

    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760",
            name="file_size_bounded",
        ),
        CheckConstraint(
            "length(file_checksum) = 64",
            name="checksum_length",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="expiry_after_created",
        ),
    )

    stage_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_checksum: Mapped[str] = mapped_column(String(64), index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    content_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    request_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketDataRawObservationRow(DatabaseBase):
    """Append-only provider payload captured before normalization."""

    __tablename__ = "market_data_raw_observations"

    __table_args__ = (
        CheckConstraint("window_end > window_start", name="window_range_valid"),
        CheckConstraint("length(payload_checksum) = 64", name="checksum_length"),
        Index(
            "ix_market_data_raw_observations_stream_observed_at",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            "observed_at",
        ),
        Index(
            "ix_market_data_raw_observations_window_end",
            "window_end",
        ),
    )

    observation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_checksum: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketDataEventRow(DatabaseBase):
    """Immutable normalized market-data event with raw-observation lineage."""

    __tablename__ = "market_data_events"

    __table_args__ = (
        CheckConstraint("kind = 'candle_observed'", name="kind_supported"),
        CheckConstraint("length(payload_checksum) = 64", name="checksum_length"),
        Index(
            "ix_market_data_events_stream_event_time",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            "event_time",
        ),
        Index(
            "ix_market_data_events_window_event_time",
            "window_id",
            "event_time",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    raw_observation_id: Mapped[str] = mapped_column(String(100), index=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_id: Mapped[str] = mapped_column(String(100), index=True)
    payload_version: Mapped[str] = mapped_column(String(50))
    payload_checksum: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)
    persisted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketDataEventInboxRow(DatabaseBase):
    """Mutable delivery counter and durable deduplication tombstone."""

    __tablename__ = "market_data_event_inbox"

    __table_args__ = (
        CheckConstraint("length(payload_checksum) = 64", name="checksum_length"),
        CheckConstraint("last_seen_at >= first_seen_at", name="seen_range_valid"),
        CheckConstraint("delivery_count >= 1", name="delivery_count_positive"),
        Index(
            "ix_market_data_event_inbox_last_seen_at",
            "last_seen_at",
        ),
    )

    idempotency_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    event_id: Mapped[str] = mapped_column(String(100), unique=True)
    payload_checksum: Mapped[str] = mapped_column(String(64), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivery_count: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)


class MarketDataEventDecisionRow(DatabaseBase):
    """Append-only evidence for one raw-observation ingestion decision."""

    __tablename__ = "market_data_event_decisions"

    __table_args__ = (
        CheckConstraint(
            "arrival IN ('on_time', 'late')",
            name="arrival_supported",
        ),
        CheckConstraint(
            "disposition IN ('accepted', 'duplicate', 'revision_required')",
            name="disposition_supported",
        ),
        CheckConstraint(
            "reason IN ('new_window', 'provisional_update', 'duplicate_payload', "
            "'late_arrival', 'finalized_window_conflict')",
            name="reason_supported",
        ),
        CheckConstraint(
            "existing_window_version IS NULL OR existing_window_version >= 1",
            name="existing_version_positive",
        ),
        CheckConstraint(
            "proposed_window_version IS NULL OR proposed_window_version >= 1",
            name="proposed_version_positive",
        ),
        CheckConstraint(
            "(disposition = 'duplicate' AND proposed_window_version IS NULL "
            "AND requires_replay = false) OR "
            "(disposition = 'accepted' AND proposed_window_version IS NOT NULL "
            "AND requires_replay = false) OR "
            "(disposition = 'revision_required' AND proposed_window_version IS NOT NULL "
            "AND requires_replay = true)",
            name="decision_consistent",
        ),
        Index(
            "ux_market_data_event_decisions_observation",
            "observation_id",
            unique=True,
        ),
        Index(
            "ix_market_data_event_decisions_window_decided_at",
            "window_id",
            "decided_at",
        ),
        Index(
            "ix_market_data_event_decisions_disposition_decided_at",
            "disposition",
            "decided_at",
        ),
    )

    decision_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    observation_id: Mapped[str] = mapped_column(String(100))
    event_id: Mapped[str] = mapped_column(String(100), index=True)
    watermark_id: Mapped[str] = mapped_column(String(100), index=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    window_id: Mapped[str] = mapped_column(String(100), index=True)
    arrival: Mapped[str] = mapped_column(String(20))
    disposition: Mapped[str] = mapped_column(String(30), index=True)
    reason: Mapped[str] = mapped_column(String(50), index=True)
    existing_window_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposed_window_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_replay: Mapped[bool] = mapped_column()
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class MarketDataOutboxRow(DatabaseBase):
    """Transactional handoff from accepted events to internal consumers."""

    __tablename__ = "market_data_outbox"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name="status_supported",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 20",
            name="attempt_count_range",
        ),
        CheckConstraint("available_at >= created_at", name="available_after_created"),
        CheckConstraint("updated_at >= created_at", name="updated_after_created"),
        CheckConstraint(
            "delivered_at IS NULL OR delivered_at >= created_at",
            name="delivered_after_created",
        ),
        CheckConstraint(
            "(status = 'pending' AND delivered_at IS NULL "
            "AND error_code IS NULL AND error_message IS NULL) OR "
            "(status = 'delivered' AND delivered_at IS NOT NULL "
            "AND error_code IS NULL AND error_message IS NULL) OR "
            "(status = 'failed' AND delivered_at IS NULL "
            "AND error_code IS NOT NULL AND error_message IS NOT NULL)",
            name="outcome_consistent",
        ),
        Index(
            "ux_market_data_outbox_event_topic_version",
            "event_id",
            "topic",
            "payload_version",
            unique=True,
        ),
        Index(
            "ix_market_data_outbox_status_available_at",
            "status",
            "available_at",
        ),
    )

    outbox_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("market_data_events.event_id"),
        index=True,
    )
    schema_version: Mapped[str] = mapped_column(String(50))
    topic: Mapped[str] = mapped_column(String(100))
    payload_version: Mapped[str] = mapped_column(String(50))
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketDataWindowVersionRow(DatabaseBase):
    """Append-only version of a provisional or finalized market window."""

    __tablename__ = "market_data_window_versions"

    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "state IN ('provisional', 'finalized')",
            name="state_supported",
        ),
        CheckConstraint("window_end > window_start", name="window_range_valid"),
        CheckConstraint("length(payload_checksum) = 64", name="checksum_length"),
        CheckConstraint(
            "(state = 'provisional' AND finalized_at IS NULL) OR "
            "(state = 'finalized' AND finalized_at IS NOT NULL)",
            name="finalization_consistent",
        ),
        CheckConstraint(
            "finalized_at IS NULL OR finalized_at >= created_at",
            name="finalized_after_created",
        ),
        Index(
            "ix_market_data_window_versions_stream_window_end",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            "window_end",
        ),
        Index(
            "ix_market_data_window_versions_state_window_end",
            "state",
            "window_end",
        ),
    )

    window_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    state: Mapped[str] = mapped_column(String(20), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_id: Mapped[str] = mapped_column(String(100), index=True)
    payload_checksum: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class MarketDataWindowFinalizationRow(DatabaseBase):
    """Immutable finalization and freshness evidence for one window version."""

    __tablename__ = "market_data_window_finalizations"

    __table_args__ = (
        CheckConstraint(
            "freshness_outcome IN ('within_target', 'missed_target')",
            name="freshness_outcome_supported",
        ),
        CheckConstraint(
            "finalized_version = provisional_version + 1",
            name="version_transition_valid",
        ),
        CheckConstraint(
            "watermark_time >= window_end",
            name="window_passed_watermark",
        ),
        CheckConstraint(
            "finalized_at >= window_end",
            name="finalized_after_window_end",
        ),
        CheckConstraint(
            "freshness_seconds >= 0 AND freshness_target_seconds >= 1",
            name="freshness_values_valid",
        ),
        Index(
            "ux_market_data_window_finalizations_window_version",
            "window_id",
            "finalized_version",
            unique=True,
        ),
        Index(
            "ix_market_data_window_finalizations_stream_finalized_at",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            "finalized_at",
        ),
        Index(
            "ix_market_data_window_finalizations_outcome_finalized_at",
            "freshness_outcome",
            "finalized_at",
        ),
    )

    finalization_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    window_id: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20), index=True)
    provisional_version: Mapped[int] = mapped_column(Integer)
    finalized_version: Mapped[int] = mapped_column(Integer)
    event_id: Mapped[str] = mapped_column(String(100), index=True)
    payload_checksum: Mapped[str] = mapped_column(String(64))
    watermark_id: Mapped[str] = mapped_column(String(100), index=True)
    watermark_version: Mapped[int] = mapped_column(Integer)
    policy_version: Mapped[str] = mapped_column(String(50))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    watermark_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    freshness_seconds: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    freshness_target_seconds: Mapped[int] = mapped_column(Integer)
    freshness_outcome: Mapped[str] = mapped_column(String(30), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class MarketDataReplayRequestRow(DatabaseBase):
    """Immutable authorization for one late-data or correction replay."""

    __tablename__ = "market_data_replay_requests"

    __table_args__ = (
        CheckConstraint(
            "reason IN ('late_arrival', 'finalized_window_conflict')",
            name="reason_supported",
        ),
        Index(
            "ux_market_data_replay_requests_decision",
            "decision_id",
            unique=True,
        ),
        Index(
            "ix_market_data_replay_requests_window_requested_at",
            "window_id",
            "requested_at",
        ),
    )

    replay_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    decision_id: Mapped[str] = mapped_column(String(100), index=True)
    observation_id: Mapped[str] = mapped_column(String(100), index=True)
    event_id: Mapped[str] = mapped_column(String(100), index=True)
    window_id: Mapped[str] = mapped_column(String(100), index=True)
    reason: Mapped[str] = mapped_column(String(50), index=True)
    requested_by: Mapped[str] = mapped_column(String(100))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class MarketDataWindowRevisionRow(DatabaseBase):
    """Immutable replay evidence for one corrected finalized window version."""

    __tablename__ = "market_data_window_revisions"

    __table_args__ = (
        CheckConstraint(
            "reason IN ('late_arrival', 'finalized_window_conflict')",
            name="reason_supported",
        ),
        CheckConstraint(
            "kind IN ('late_insert', 'correction')",
            name="kind_supported",
        ),
        CheckConstraint(
            "(kind = 'late_insert' AND previous_version IS NULL "
            "AND previous_event_id IS NULL AND previous_payload_checksum IS NULL "
            "AND revised_version = 1) OR "
            "(kind = 'correction' AND previous_version IS NOT NULL "
            "AND previous_event_id IS NOT NULL AND previous_payload_checksum IS NOT NULL "
            "AND revised_version = previous_version + 1)",
            name="version_transition_valid",
        ),
        Index("ux_market_data_window_revisions_replay", "replay_id", unique=True),
        Index(
            "ux_market_data_window_revisions_window_version",
            "window_id",
            "revised_version",
            unique=True,
        ),
        Index(
            "ix_market_data_window_revisions_window_applied_at",
            "window_id",
            "applied_at",
        ),
    )

    revision_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    replay_id: Mapped[str] = mapped_column(String(100), index=True)
    decision_id: Mapped[str] = mapped_column(String(100), index=True)
    observation_id: Mapped[str] = mapped_column(String(100), index=True)
    event_id: Mapped[str] = mapped_column(String(100), index=True)
    window_id: Mapped[str] = mapped_column(String(100), index=True)
    reason: Mapped[str] = mapped_column(String(50), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    previous_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_payload_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revised_version: Mapped[int] = mapped_column(Integer)
    revised_payload_checksum: Mapped[str] = mapped_column(String(64))
    watermark_id: Mapped[str] = mapped_column(String(100), index=True)
    watermark_version: Mapped[int] = mapped_column(Integer)
    watermark_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class MarketDataWatermarkRow(DatabaseBase):
    """Append-only policy-bound watermark revision for one exact stream."""

    __tablename__ = "market_data_watermarks"

    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "allowed_lateness_seconds >= 0",
            name="allowed_lateness_nonnegative",
        ),
        CheckConstraint(
            "watermark_time <= high_water_event_time",
            name="watermark_not_after_high_water",
        ),
        Index(
            "ux_market_data_watermarks_stream_version",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            "version",
            unique=True,
        ),
        Index(
            "ix_market_data_watermarks_stream_calculated_at",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
            "calculated_at",
        ),
    )

    watermark_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    policy_version: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    high_water_event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    allowed_lateness_seconds: Mapped[int] = mapped_column(Integer)
    watermark_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload_json: Mapped[str] = mapped_column(Text)


class MarketDataRetentionControlRow(DatabaseBase):
    """Singleton row used to serialize hold changes and bounded purge runs."""

    __tablename__ = "market_data_retention_control"

    __table_args__ = (
        CheckConstraint(
            "control_id = 'market-data-retention-control'",
            name="singleton_identity",
        ),
    )

    control_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketDataRetentionHoldRow(DatabaseBase):
    """Persistent legal or incident hold that blocks every purge mode."""

    __tablename__ = "market_data_retention_holds"

    __table_args__ = (
        CheckConstraint("kind IN ('legal', 'incident')", name="kind_supported"),
        CheckConstraint(
            "(released_by IS NULL AND released_at IS NULL) OR "
            "(released_by IS NOT NULL AND released_at IS NOT NULL)",
            name="release_consistent",
        ),
        CheckConstraint(
            "released_at IS NULL OR released_at >= placed_at",
            name="release_after_placement",
        ),
        Index("ix_market_data_retention_holds_active", "released_at", "placed_at"),
    )

    hold_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(20), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    placed_by: Mapped[str] = mapped_column(String(100))
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    released_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text)


class MarketDataRetentionRunRow(DatabaseBase):
    """Immutable sanitized audit evidence for one dry-run or purge batch."""

    __tablename__ = "market_data_retention_runs"

    __table_args__ = (
        CheckConstraint("mode IN ('dry_run', 'execute')", name="mode_supported"),
        CheckConstraint(
            "outcome IN ('completed', 'blocked', 'failed')",
            name="outcome_supported",
        ),
        CheckConstraint("batch_limit >= 1 AND batch_limit <= 500", name="batch_limit_bounded"),
        CheckConstraint("selected_count >= 0", name="selected_count_nonnegative"),
        CheckConstraint("deleted_count >= 0", name="deleted_count_nonnegative"),
        CheckConstraint("completed_at >= requested_at", name="completion_after_request"),
        Index(
            "ix_market_data_retention_runs_outcome_completed_at",
            "outcome",
            "completed_at",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    policy_version: Mapped[str] = mapped_column(String(50))
    mode: Mapped[str] = mapped_column(String(20), index=True)
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    requested_by: Mapped[str] = mapped_column(String(100))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    batch_limit: Mapped[int] = mapped_column(Integer)
    selected_count: Mapped[int] = mapped_column(Integer)
    deleted_count: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)


class MarketContextInputManifestRow(DatabaseBase):
    """Immutable multi-timeframe input selected at one event-time boundary."""

    __tablename__ = "market_context_input_manifests"

    __table_args__ = (
        CheckConstraint("length(input_checksum) = 64", name="checksum_length"),
        CheckConstraint("window_count >= 3", name="window_count_minimum"),
        CheckConstraint("created_at >= as_of", name="created_after_as_of"),
        Index(
            "ix_market_context_input_manifests_stream_as_of",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "as_of",
        ),
    )

    manifest_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    policy_version: Mapped[str] = mapped_column(String(50), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    window_count: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketContextInputWindowRow(DatabaseBase):
    """Queryable finalized-window lineage for one immutable input manifest."""

    __tablename__ = "market_context_input_windows"

    __table_args__ = (
        ForeignKeyConstraint(
            ["window_id", "window_version"],
            ["market_data_window_versions.window_id", "market_data_window_versions.version"],
        ),
        CheckConstraint("ordinal >= 1", name="ordinal_positive"),
        CheckConstraint("window_version >= 2", name="window_version_finalized"),
        CheckConstraint("window_end > window_start", name="window_range_valid"),
        CheckConstraint("length(reference_checksum) = 64", name="checksum_length"),
        UniqueConstraint(
            "manifest_id",
            "window_id",
            "window_version",
            name="uq_market_context_input_windows_window_version",
        ),
        Index(
            "ix_market_context_input_windows_manifest_timeframe_ordinal",
            "manifest_id",
            "timeframe",
            "ordinal",
        ),
    )

    manifest_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("market_context_input_manifests.manifest_id", ondelete="CASCADE"),
        primary_key=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    window_id: Mapped[str] = mapped_column(String(100), index=True)
    window_version: Mapped[int] = mapped_column(Integer)
    timeframe: Mapped[str] = mapped_column(String(20), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reference_checksum: Mapped[str] = mapped_column(String(64), index=True)


class MarketContextFeatureSnapshotRow(DatabaseBase):
    """Immutable deterministic feature values for one input manifest."""

    __tablename__ = "market_context_feature_snapshots"

    __table_args__ = (
        CheckConstraint("length(input_checksum) = 64", name="input_checksum_length"),
        CheckConstraint("length(feature_set_checksum) = 64", name="feature_set_checksum_length"),
        CheckConstraint("length(snapshot_checksum) = 64", name="snapshot_checksum_length"),
        CheckConstraint("feature_count >= 1", name="feature_count_positive"),
        CheckConstraint("calculated_at >= as_of", name="calculated_after_as_of"),
        UniqueConstraint(
            "manifest_id",
            "feature_set_version",
            name="uq_market_context_feature_snapshots_manifest_feature_set",
        ),
        Index(
            "ix_market_context_feature_snapshots_stream_as_of",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "as_of",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    manifest_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("market_context_input_manifests.manifest_id"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_checksum: Mapped[str] = mapped_column(String(64))
    feature_set_version: Mapped[str] = mapped_column(String(100), index=True)
    feature_set_checksum: Mapped[str] = mapped_column(String(64))
    feature_count: Mapped[int] = mapped_column(Integer)
    snapshot_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketRegimeAssessmentRow(DatabaseBase):
    """Immutable regime result or explicit non-ready outcome."""

    __tablename__ = "market_regime_assessments"

    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'insufficient_data', 'stale')",
            name="status_supported",
        ),
        CheckConstraint(
            "trend IN ('trending_up', 'trending_down', 'ranging', 'undetermined')",
            name="trend_supported",
        ),
        CheckConstraint(
            "volatility IN ('low', 'normal', 'high', 'undetermined')",
            name="volatility_supported",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("length(input_checksum) = 64", name="input_checksum_length"),
        CheckConstraint("length(feature_set_checksum) = 64", name="feature_set_checksum_length"),
        CheckConstraint(
            "feature_snapshot_checksum IS NULL OR length(feature_snapshot_checksum) = 64",
            name="feature_snapshot_checksum_length",
        ),
        CheckConstraint("assessed_at >= as_of", name="assessed_after_as_of"),
        CheckConstraint(
            "(status = 'ready' AND trend != 'undetermined' "
            "AND volatility != 'undetermined' AND confidence > 0 "
            "AND feature_snapshot_id IS NOT NULL "
            "AND feature_snapshot_checksum IS NOT NULL AND expires_at > assessed_at) OR "
            "(status != 'ready' AND trend = 'undetermined' "
            "AND volatility = 'undetermined' AND confidence = 0 "
            "AND feature_snapshot_id IS NULL "
            "AND feature_snapshot_checksum IS NULL AND expires_at = assessed_at)",
            name="outcome_consistent",
        ),
        UniqueConstraint(
            "manifest_id",
            "feature_set_version",
            "algorithm_version",
            name="uq_market_regime_assessments_manifest_algorithm",
        ),
        Index(
            "ix_market_regime_assessments_stream_as_of",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "as_of",
        ),
        Index(
            "ix_market_regime_assessments_status_assessed_at",
            "status",
            "assessed_at",
        ),
    )

    assessment_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    manifest_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("market_context_input_manifests.manifest_id"),
        index=True,
    )
    feature_snapshot_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("market_context_feature_snapshots.snapshot_id"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_checksum: Mapped[str] = mapped_column(String(64))
    feature_set_version: Mapped[str] = mapped_column(String(100), index=True)
    feature_set_checksum: Mapped[str] = mapped_column(String(64))
    feature_snapshot_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    algorithm_version: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    trend: Mapped[str] = mapped_column(String(30))
    volatility: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    evidence_count: Mapped[int] = mapped_column(Integer)
    issue_count: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AlertRuleDefinitionRow(DatabaseBase):
    """Immutable operator-owned alert rule version."""

    __tablename__ = "alert_rule_definitions"

    __table_args__ = (
        CheckConstraint("rule_version >= 1", name="rule_version_positive"),
        CheckConstraint(
            "source_kind IN ('market_context')",
            name="source_kind_supported",
        ),
        CheckConstraint("state IN ('enabled', 'disabled')", name="state_supported"),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="severity_supported",
        ),
        CheckConstraint("length(definition_checksum) = 64", name="checksum_length"),
        UniqueConstraint(
            "rule_key",
            "rule_version",
            name="uq_alert_rule_definitions_key_version",
        ),
        Index(
            "ix_alert_rule_definitions_state_created_at",
            "state",
            "created_at",
        ),
    )

    rule_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    rule_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    rule_key: Mapped[str] = mapped_column(String(64), index=True)
    source_kind: Mapped[str] = mapped_column(String(30), index=True)
    state: Mapped[str] = mapped_column(String(20), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    definition_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AlertEvaluationRow(DatabaseBase):
    """Immutable publish-or-suppress decision for one exact rule/source pair."""

    __tablename__ = "alert_evaluations"

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_id", "rule_version"],
            ["alert_rule_definitions.rule_id", "alert_rule_definitions.rule_version"],
        ),
        CheckConstraint(
            "source_kind IN ('market_context')",
            name="source_kind_supported",
        ),
        CheckConstraint(
            "disposition IN ('published', 'suppressed')",
            name="disposition_supported",
        ),
        CheckConstraint(
            "suppression_reason_count >= 0",
            name="suppression_reason_count_nonnegative",
        ),
        CheckConstraint(
            "length(source_event_checksum) = 64",
            name="source_event_checksum_length",
        ),
        CheckConstraint(
            "length(evaluation_checksum) = 64",
            name="evaluation_checksum_length",
        ),
        CheckConstraint(
            "(disposition = 'published' AND alert_id IS NOT NULL "
            "AND suppression_reason_count = 0) OR "
            "(disposition = 'suppressed' AND alert_id IS NULL "
            "AND suppression_reason_count >= 1)",
            name="outcome_consistent",
        ),
        UniqueConstraint(
            "rule_id",
            "rule_version",
            "source_kind",
            "source_event_id",
            name="uq_alert_evaluations_rule_source",
        ),
        Index(
            "ix_alert_evaluations_disposition_evaluated_at",
            "disposition",
            "evaluated_at",
        ),
    )

    evaluation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    rule_id: Mapped[str] = mapped_column(String(100), index=True)
    rule_version: Mapped[int] = mapped_column(Integer)
    source_kind: Mapped[str] = mapped_column(String(30), index=True)
    source_reference_id: Mapped[str] = mapped_column(String(100), index=True)
    source_event_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("market_regime_assessments.assessment_id"),
        index=True,
    )
    source_event_checksum: Mapped[str] = mapped_column(String(64))
    disposition: Mapped[str] = mapped_column(String(20), index=True)
    suppression_reason_count: Mapped[int] = mapped_column(Integer)
    alert_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    evaluation_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AlertRow(DatabaseBase):
    """Immutable published in-app alert and its exact lineage."""

    __tablename__ = "alerts"

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_id", "rule_version"],
            ["alert_rule_definitions.rule_id", "alert_rule_definitions.rule_version"],
        ),
        CheckConstraint(
            "source_kind IN ('market_context')",
            name="source_kind_supported",
        ),
        CheckConstraint(
            "delivery_channel IN ('in_app')",
            name="delivery_channel_supported",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="severity_supported",
        ),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        CheckConstraint("length(draft_checksum) = 64", name="draft_checksum_length"),
        Index("ix_alerts_expires_at_created_at", "expires_at", "created_at"),
    )

    alert_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    evaluation_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("alert_evaluations.evaluation_id"),
        unique=True,
    )
    deduplication_key: Mapped[str] = mapped_column(String(100), unique=True)
    rule_id: Mapped[str] = mapped_column(String(100), index=True)
    rule_version: Mapped[int] = mapped_column(Integer)
    source_kind: Mapped[str] = mapped_column(String(30), index=True)
    source_event_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("market_regime_assessments.assessment_id"),
        index=True,
    )
    delivery_channel: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    draft_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AlertInboxStateRow(DatabaseBase):
    """Current operator-facing state for one immutable published alert."""

    __tablename__ = "alert_inbox_states"

    __table_args__ = (
        CheckConstraint(
            "(acknowledged_at IS NULL AND acknowledged_by IS NULL) OR "
            "(acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL)",
            name="acknowledgement_consistent",
        ),
        CheckConstraint(
            "(snoozed_until IS NULL AND snoozed_by IS NULL) OR "
            "(snoozed_until IS NOT NULL AND snoozed_by IS NOT NULL)",
            name="snooze_consistent",
        ),
        CheckConstraint(
            "acknowledged_at IS NULL OR snoozed_until IS NULL",
            name="acknowledged_not_snoozed",
        ),
        Index("ix_alert_inbox_states_acknowledged_at", "acknowledged_at"),
        Index("ix_alert_inbox_states_snoozed_until", "snoozed_until"),
    )

    alert_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("alerts.alert_id", ondelete="CASCADE"),
        primary_key=True,
    )
    schema_version: Mapped[str] = mapped_column(String(50))
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    snoozed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AlertActionRow(DatabaseBase):
    """Append-only audit record for one Alert Center operator action."""

    __tablename__ = "alert_actions"

    __table_args__ = (
        CheckConstraint(
            "kind IN ('acknowledged', 'snoozed')",
            name="kind_supported",
        ),
        CheckConstraint(
            "(kind = 'acknowledged' AND snoozed_until IS NULL) OR "
            "(kind = 'snoozed' AND snoozed_until IS NOT NULL "
            "AND snoozed_until > occurred_at)",
            name="payload_consistent",
        ),
        CheckConstraint("length(action_checksum) = 64", name="checksum_length"),
        Index("ix_alert_actions_alert_occurred_at", "alert_id", "occurred_at"),
    )

    action_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    alert_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("alerts.alert_id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), index=True)
    acted_by: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    action_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class AlertPublicationPolicyRow(DatabaseBase):
    """Append-only operator publication preference revision."""

    __tablename__ = "alert_publication_policies"

    __table_args__ = (
        CheckConstraint("policy_version >= 1", name="policy_version_positive"),
        CheckConstraint(
            "quiet_hours_start_minute >= 0 AND quiet_hours_start_minute <= 1439",
            name="quiet_hours_start_minute_range",
        ),
        CheckConstraint(
            "quiet_hours_end_minute >= 0 AND quiet_hours_end_minute <= 1439",
            name="quiet_hours_end_minute_range",
        ),
        CheckConstraint(
            "NOT quiet_hours_enabled OR quiet_hours_start_minute != quiet_hours_end_minute",
            name="quiet_hours_window_nonempty",
        ),
        CheckConstraint("length(policy_checksum) = 64", name="checksum_length"),
    )

    policy_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    policy_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    quiet_hours_enabled: Mapped[bool] = mapped_column(default=False)
    quiet_hours_start_minute: Mapped[int] = mapped_column(Integer)
    quiet_hours_end_minute: Mapped[int] = mapped_column(Integer)
    timezone_name: Mapped[str] = mapped_column(String(64))
    critical_bypass_quiet_hours: Mapped[bool] = mapped_column(default=True)
    updated_by: Mapped[str] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    policy_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class AlertPublicationDecisionRow(DatabaseBase):
    """Immutable publication guard decision for one alert evaluation."""

    __tablename__ = "alert_publication_decisions"

    __table_args__ = (
        CheckConstraint("policy_version >= 0", name="policy_version_nonnegative"),
        CheckConstraint("suppression_reason_count >= 0", name="reason_count_nonnegative"),
        CheckConstraint(
            "(allowed AND suppression_reason_count = 0) OR "
            "(NOT allowed AND suppression_reason_count >= 1)",
            name="outcome_consistent",
        ),
        CheckConstraint("length(policy_checksum) = 64", name="policy_checksum_length"),
        CheckConstraint("length(decision_checksum) = 64", name="decision_checksum_length"),
        Index("ix_alert_publication_decisions_allowed_evaluated_at", "allowed", "evaluated_at"),
    )

    decision_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    evaluation_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("alert_evaluations.evaluation_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    policy_id: Mapped[str] = mapped_column(String(100), index=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    policy_checksum: Mapped[str] = mapped_column(String(64))
    allowed: Mapped[bool] = mapped_column(index=True)
    suppression_reason_count: Mapped[int] = mapped_column(Integer)
    previous_alert_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("alerts.alert_id"),
        nullable=True,
    )
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    decision_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class AlertExpiryRecordRow(DatabaseBase):
    """Append-only materialization of an alert's immutable expiry boundary."""

    __tablename__ = "alert_expiry_records"

    __table_args__ = (
        CheckConstraint("recorded_at >= expired_at", name="recorded_after_expiry"),
        CheckConstraint("length(record_checksum) = 64", name="checksum_length"),
        Index("ix_alert_expiry_records_expired_recorded", "expired_at", "recorded_at"),
    )

    expiry_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    alert_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("alerts.alert_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    expired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by: Mapped[str] = mapped_column(String(100))
    record_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class AlertSimulationRow(DatabaseBase):
    """Immutable offline Paper/Shadow enrollment for a published alert."""

    __tablename__ = "alert_simulations"

    __table_args__ = (
        CheckConstraint("mode IN ('paper', 'shadow')", name="mode_supported"),
        CheckConstraint(
            "horizon_seconds >= 900 AND horizon_seconds <= 2592000",
            name="horizon_bounded",
        ),
        CheckConstraint("ends_at > started_at", name="ends_after_started"),
        CheckConstraint("offline_only", name="offline_only_required"),
        CheckConstraint(
            "NOT external_order_submission_allowed",
            name="external_order_submission_forbidden",
        ),
        CheckConstraint("length(record_checksum) = 64", name="checksum_length"),
        Index("ix_alert_simulations_alert_started_at", "alert_id", "started_at"),
        Index("ix_alert_simulations_mode_ends_at", "mode", "ends_at"),
    )

    simulation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    alert_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("alerts.alert_id", ondelete="CASCADE"),
        index=True,
    )
    alert_checksum: Mapped[str] = mapped_column(String(64))
    source_reference_id: Mapped[str] = mapped_column(String(100), index=True)
    source_reference_checksum: Mapped[str] = mapped_column(String(64))
    rule_id: Mapped[str] = mapped_column(String(100), index=True)
    rule_version: Mapped[int] = mapped_column(Integer)
    rule_definition_checksum: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20), index=True)
    expected_trend: Mapped[str] = mapped_column(String(30))
    horizon_seconds: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_by: Mapped[str] = mapped_column(String(100))
    offline_only: Mapped[bool] = mapped_column(Boolean, default=True)
    external_order_submission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    record_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class AlertOutcomeRow(DatabaseBase):
    """Append-only outcome evidence for one completed offline simulation."""

    __tablename__ = "alert_outcomes"

    __table_args__ = (
        CheckConstraint(
            "classification IN ('confirmed', 'neutral', 'false_positive')",
            name="classification_supported",
        ),
        CheckConstraint("mode IN ('paper', 'shadow')", name="mode_supported"),
        CheckConstraint("reference_price > 0", name="reference_price_positive"),
        CheckConstraint("end_price > 0", name="end_price_positive"),
        CheckConstraint("high_price > 0", name="high_price_positive"),
        CheckConstraint("low_price > 0", name="low_price_positive"),
        CheckConstraint(
            "high_price >= reference_price AND high_price >= end_price", name="high_price_valid"
        ),
        CheckConstraint(
            "low_price <= reference_price AND low_price <= end_price", name="low_price_valid"
        ),
        CheckConstraint("recorded_at >= observed_at", name="recorded_after_observation"),
        CheckConstraint(
            "false_positive = (classification = 'false_positive')",
            name="false_positive_consistent",
        ),
        CheckConstraint(
            "policy_version = 'alert-outcome-policy-v1'",
            name="policy_version_supported",
        ),
        CheckConstraint(
            "classification_threshold = 0.005",
            name="classification_threshold_supported",
        ),
        CheckConstraint("offline_only", name="offline_only_required"),
        CheckConstraint(
            "NOT external_order_submission_allowed",
            name="external_order_submission_forbidden",
        ),
        CheckConstraint("length(record_checksum) = 64", name="checksum_length"),
        Index("ix_alert_outcomes_classification_recorded", "classification", "recorded_at"),
        Index("ix_alert_outcomes_mode_recorded", "mode", "recorded_at"),
    )

    outcome_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    simulation_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("alert_simulations.simulation_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    simulation_checksum: Mapped[str] = mapped_column(String(64))
    alert_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("alerts.alert_id", ondelete="CASCADE"), index=True
    )
    alert_checksum: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20), index=True)
    expected_trend: Mapped[str] = mapped_column(String(30))
    observed_trend: Mapped[str] = mapped_column(String(30))
    reference_price: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    end_price: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    high_price: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    low_price: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    raw_return: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    directional_return: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    max_favorable_excursion: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    max_adverse_excursion: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    classification: Mapped[str] = mapped_column(String(30), index=True)
    false_positive: Mapped[bool] = mapped_column(Boolean, index=True)
    drifted: Mapped[bool] = mapped_column(Boolean, index=True)
    policy_version: Mapped[str] = mapped_column(String(50))
    policy_checksum: Mapped[str] = mapped_column(String(64))
    classification_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by: Mapped[str] = mapped_column(String(100))
    offline_only: Mapped[bool] = mapped_column(Boolean, default=True)
    external_order_submission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    record_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class DecisionPolicyDefinitionRow(DatabaseBase):
    """Immutable version of the offline decision admission policy."""

    __tablename__ = "decision_policy_definitions"

    __table_args__ = (
        CheckConstraint("policy_version >= 1", name="policy_version_positive"),
        CheckConstraint(
            "(policy_version = 1 AND supersedes_version IS NULL) OR "
            "(policy_version > 1 AND supersedes_version = policy_version - 1)",
            name="lineage_consistent",
        ),
        CheckConstraint("state IN ('enabled', 'disabled')", name="state_supported"),
        CheckConstraint(
            "allowed_mode_count >= 1 AND allowed_mode_count <= 3",
            name="allowed_mode_count_bounded",
        ),
        CheckConstraint("offline_only", name="offline_only_required"),
        CheckConstraint(
            "NOT external_order_submission_allowed",
            name="external_order_forbidden",
        ),
        CheckConstraint("length(definition_checksum) = 64", name="checksum_length"),
        UniqueConstraint(
            "policy_key",
            "policy_version",
            name="uq_decision_policy_definitions_key_version",
        ),
        Index(
            "ix_decision_policy_definitions_state_created_at",
            "state",
            "created_at",
        ),
    )

    policy_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    policy_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    policy_key: Mapped[str] = mapped_column(String(100), index=True)
    supersedes_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(20), index=True)
    allowed_mode_count: Mapped[int] = mapped_column(Integer)
    offline_only: Mapped[bool] = mapped_column(Boolean, default=True)
    external_order_submission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    definition_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DecisionEvaluationIntentRow(DatabaseBase):
    """Immutable input and lineage envelope for one offline decision evaluation."""

    __tablename__ = "decision_evaluation_intents"

    __table_args__ = (
        ForeignKeyConstraint(
            ["policy_id", "policy_version"],
            [
                "decision_policy_definitions.policy_id",
                "decision_policy_definitions.policy_version",
            ],
        ),
        CheckConstraint(
            "stage = 'strategy_evaluation'",
            name="stage_supported",
        ),
        CheckConstraint(
            "mode IN ('research', 'shadow', 'paper')",
            name="mode_supported",
        ),
        CheckConstraint("offline_only", name="offline_only_required"),
        CheckConstraint(
            "NOT external_order_submission_allowed",
            name="external_order_forbidden",
        ),
        CheckConstraint("length(dataset_reference_checksum) = 64", name="dataset_checksum_length"),
        CheckConstraint(
            "length(strategy_reference_checksum) = 64",
            name="strategy_checksum_length",
        ),
        CheckConstraint(
            "length(market_context_reference_checksum) = 64",
            name="market_context_checksum_length",
        ),
        CheckConstraint(
            "length(policy_definition_checksum) = 64",
            name="policy_checksum_length",
        ),
        CheckConstraint("length(intent_checksum) = 64", name="intent_checksum_length"),
        Index(
            "ix_decision_evaluation_intents_stream_requested_at",
            "source",
            "base_asset",
            "quote_asset",
            "market_type",
            "requested_at",
        ),
        Index(
            "ix_decision_evaluation_intents_strategy_requested_at",
            "strategy_name",
            "strategy_version",
            "requested_at",
        ),
    )

    evaluation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    stage: Mapped[str] = mapped_column(String(30))
    mode: Mapped[str] = mapped_column(String(20), index=True)
    dataset_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("dataset_snapshots.dataset_id"),
        index=True,
    )
    dataset_reference_id: Mapped[str] = mapped_column(String(100), index=True)
    dataset_reference_checksum: Mapped[str] = mapped_column(String(64))
    strategy_reference_id: Mapped[str] = mapped_column(String(100), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str] = mapped_column(String(50))
    strategy_behavior_fingerprint: Mapped[str] = mapped_column(String(71))
    strategy_reference_checksum: Mapped[str] = mapped_column(String(64))
    market_context_reference_id: Mapped[str] = mapped_column(String(100), index=True)
    market_context_assessment_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("market_regime_assessments.assessment_id"),
        index=True,
    )
    market_context_reference_checksum: Mapped[str] = mapped_column(String(64))
    policy_id: Mapped[str] = mapped_column(String(100), index=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    policy_definition_checksum: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    offline_only: Mapped[bool] = mapped_column(Boolean, default=True)
    external_order_submission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    intent_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class DecisionStageOutcomeRow(DatabaseBase):
    """Append-only semantic evidence for one decision pipeline stage."""

    __tablename__ = "decision_stage_outcomes"

    __table_args__ = (
        CheckConstraint(
            "stage IN ('strategy_evaluation', 'candidate_ranking', "
            "'risk_gate', 'portfolio_simulation')",
            name="stage_supported",
        ),
        CheckConstraint(
            "disposition IN ('accepted', 'rejected', 'deferred', 'unavailable')",
            name="disposition_supported",
        ),
        CheckConstraint("reason_code_count >= 0", name="reason_code_count_nonnegative"),
        CheckConstraint(
            "(disposition = 'accepted' AND reason_code_count = 0) OR "
            "(disposition != 'accepted' AND reason_code_count >= 1)",
            name="outcome_consistent",
        ),
        CheckConstraint("offline_only", name="offline_only_required"),
        CheckConstraint(
            "NOT external_order_submission_allowed",
            name="external_order_submission_forbidden",
        ),
        CheckConstraint("length(outcome_checksum) = 64", name="checksum_length"),
        UniqueConstraint(
            "evaluation_id",
            "stage",
            name="uq_decision_stage_outcomes_evaluation_stage",
        ),
        Index(
            "ix_decision_stage_outcomes_stage_disposition_evaluated_at",
            "stage",
            "disposition",
            "evaluated_at",
        ),
    )

    outcome_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(50))
    evaluation_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("decision_evaluation_intents.evaluation_id", ondelete="CASCADE"),
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(30), index=True)
    disposition: Mapped[str] = mapped_column(String(20), index=True)
    reason_code_count: Mapped[int] = mapped_column(Integer)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    offline_only: Mapped[bool] = mapped_column(Boolean, default=True)
    external_order_submission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class DecisionStrategyEvaluationRow(DatabaseBase):
    """Immutable context-aware strategy signals and admission evidence."""

    __tablename__ = "decision_strategy_evaluations"

    __table_args__ = (
        CheckConstraint(
            "disposition IN ('accepted', 'rejected', 'deferred', 'unavailable')",
            name="disposition_supported",
        ),
        CheckConstraint("signal_count >= 0", name="signal_count_nonnegative"),
        CheckConstraint(
            "(disposition = 'accepted' AND signal_count > 0 AND latest_signal_id IS NOT NULL) "
            "OR (disposition != 'accepted' AND signal_count = 0 "
            "AND latest_signal_id IS NULL)",
            name="signals_consistent",
        ),
        CheckConstraint("offline_only", name="offline_only_required"),
        CheckConstraint(
            "NOT external_order_submission_allowed",
            name="external_order_forbidden",
        ),
        CheckConstraint(
            "length(compatibility_policy_checksum) = 64",
            name="policy_checksum_length",
        ),
        CheckConstraint("length(record_checksum) = 64", name="record_checksum_length"),
        Index(
            "ix_decision_strategy_evaluations_disposition_evaluated_at",
            "disposition",
            "evaluated_at",
        ),
    )

    evaluation_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("decision_evaluation_intents.evaluation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    outcome_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("decision_stage_outcomes.outcome_id", ondelete="CASCADE"),
        unique=True,
    )
    schema_version: Mapped[str] = mapped_column(String(50))
    compatibility_policy_version: Mapped[str] = mapped_column(String(50))
    compatibility_policy_checksum: Mapped[str] = mapped_column(String(64), index=True)
    disposition: Mapped[str] = mapped_column(String(20), index=True)
    signal_count: Mapped[int] = mapped_column(Integer)
    latest_signal_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    offline_only: Mapped[bool] = mapped_column(Boolean, default=True)
    external_order_submission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    record_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class DecisionCandidateRankingRow(DatabaseBase):
    """Immutable candidate construction and deterministic ranking evidence."""

    __tablename__ = "decision_candidate_rankings"

    __table_args__ = (
        CheckConstraint(
            "disposition IN ('accepted', 'deferred')",
            name="disposition_supported",
        ),
        CheckConstraint("source_signal_count > 0", name="source_count_positive"),
        CheckConstraint("candidate_count >= 0", name="candidate_count_nonnegative"),
        CheckConstraint("excluded_signal_count >= 0", name="excluded_count_nonnegative"),
        CheckConstraint(
            "candidate_count + excluded_signal_count = source_signal_count",
            name="counts_consistent",
        ),
        CheckConstraint(
            "(disposition = 'accepted' AND candidate_count > 0 "
            "AND top_candidate_id IS NOT NULL) OR "
            "(disposition = 'deferred' AND candidate_count = 0 "
            "AND top_candidate_id IS NULL)",
            name="ranking_consistent",
        ),
        CheckConstraint("offline_only", name="offline_only_required"),
        CheckConstraint(
            "NOT external_order_submission_allowed",
            name="external_order_forbidden",
        ),
        CheckConstraint("length(policy_checksum) = 64", name="policy_checksum_length"),
        CheckConstraint("length(record_checksum) = 64", name="record_checksum_length"),
        Index(
            "ix_decision_candidate_rankings_disposition_ranked_at",
            "disposition",
            "ranked_at",
        ),
    )

    evaluation_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("decision_evaluation_intents.evaluation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    outcome_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("decision_stage_outcomes.outcome_id", ondelete="CASCADE"),
        unique=True,
    )
    schema_version: Mapped[str] = mapped_column(String(50))
    policy_version: Mapped[str] = mapped_column(String(50))
    policy_checksum: Mapped[str] = mapped_column(String(64), index=True)
    disposition: Mapped[str] = mapped_column(String(20), index=True)
    source_signal_count: Mapped[int] = mapped_column(Integer)
    candidate_count: Mapped[int] = mapped_column(Integer)
    excluded_signal_count: Mapped[int] = mapped_column(Integer)
    top_candidate_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    ranked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    offline_only: Mapped[bool] = mapped_column(Boolean, default=True)
    external_order_submission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    record_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class DecisionRiskGateRow(DatabaseBase):
    """Immutable risk decision and offline position-sizing evidence."""

    __tablename__ = "decision_risk_gates"

    __table_args__ = (
        CheckConstraint(
            "disposition IN ('accepted', 'rejected')",
            name="disposition_supported",
        ),
        CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="decision_supported",
        ),
        CheckConstraint(
            "(disposition = 'accepted' AND decision = 'approved' "
            "AND approved_candidate_id IS NOT NULL AND has_position_sizing) OR "
            "(disposition = 'rejected' AND decision = 'rejected' "
            "AND approved_candidate_id IS NULL AND NOT has_position_sizing)",
            name="risk_result_consistent",
        ),
        CheckConstraint("offline_only", name="offline_only_required"),
        CheckConstraint(
            "NOT external_order_submission_allowed",
            name="external_order_forbidden",
        ),
        CheckConstraint(
            "length(candidate_ranking_checksum) = 64",
            name="ranking_checksum_length",
        ),
        CheckConstraint("length(policy_checksum) = 64", name="policy_checksum_length"),
        CheckConstraint("length(assessment_checksum) = 64", name="assessment_checksum_length"),
        CheckConstraint("length(record_checksum) = 64", name="record_checksum_length"),
        Index(
            "ix_decision_risk_gates_disposition_evaluated_at",
            "disposition",
            "evaluated_at",
        ),
    )

    evaluation_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("decision_evaluation_intents.evaluation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    outcome_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("decision_stage_outcomes.outcome_id", ondelete="CASCADE"),
        unique=True,
    )
    schema_version: Mapped[str] = mapped_column(String(50))
    candidate_ranking_checksum: Mapped[str] = mapped_column(String(64), index=True)
    policy_version: Mapped[str] = mapped_column(String(50))
    policy_checksum: Mapped[str] = mapped_column(String(64), index=True)
    disposition: Mapped[str] = mapped_column(String(20), index=True)
    decision: Mapped[str] = mapped_column(String(20), index=True)
    assessment_id: Mapped[str] = mapped_column(String(100), unique=True)
    assessment_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    approved_candidate_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    has_position_sizing: Mapped[bool] = mapped_column(Boolean)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    offline_only: Mapped[bool] = mapped_column(Boolean, default=True)
    external_order_submission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    record_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class BackgroundJobRow(DatabaseBase):
    """Durable generic queue row claimed through a time-bounded worker lease."""

    __tablename__ = "background_jobs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="status_supported",
        ),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="progress_range",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts "
            "AND max_attempts > 0 AND max_attempts <= 10",
            name="attempt_range",
        ),
        CheckConstraint("updated_at >= created_at", name="updated_after_created"),
        CheckConstraint("run_after >= created_at", name="run_after_created"),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="started_after_created",
        ),
        CheckConstraint(
            "finished_at IS NULL OR (finished_at >= created_at "
            "AND (started_at IS NULL OR finished_at >= started_at))",
            name="finished_after_started",
        ),
        CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status != 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="lease_consistent",
        ),
        CheckConstraint(
            "(status IN ('succeeded', 'failed', 'cancelled') AND finished_at IS NOT NULL) "
            "OR (status IN ('queued', 'running') AND finished_at IS NULL)",
            name="finish_consistent",
        ),
        CheckConstraint(
            "status != 'succeeded' OR progress_percent = 100",
            name="success_progress_complete",
        ),
        UniqueConstraint(
            "kind",
            "idempotency_key",
            name="uq_background_jobs_kind_idempotency_key",
        ),
        Index("ix_background_jobs_claim", "status", "run_after", "created_at"),
        Index("ix_background_jobs_lease", "status", "lease_expires_at"),
    )

    job_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    progress_percent: Mapped[int] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)


class OptimizationExecutionRow(DatabaseBase):
    """Persistent lifecycle state of one historical optimization execution."""

    __tablename__ = "optimization_executions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="status_supported",
        ),
        CheckConstraint(
            "total_trials > 0",
            name="total_trials_positive",
        ),
        CheckConstraint(
            "completed_trials >= 0 AND completed_trials <= total_trials",
            name="progress_range",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="updated_after_created",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="started_after_created",
        ),
        CheckConstraint(
            "finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)",
            name="finished_after_started",
        ),
        Index(
            "ix_optimization_executions_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "ix_optimization_executions_dataset_created_at",
            "dataset_id",
            "created_at",
        ),
    )

    execution_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), index=True)
    dataset_id: Mapped[str] = mapped_column(String(100), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str] = mapped_column(String(30))
    objective: Mapped[str] = mapped_column(String(50))
    total_trials: Mapped[int] = mapped_column(Integer)
    completed_trials: Mapped[int] = mapped_column(Integer)
    best_experiment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text)


class ResearchExperimentRow(DatabaseBase):
    """Serialized result of one standard offline research experiment."""

    __tablename__ = "research_experiments"

    experiment_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dataset_id: Mapped[str] = mapped_column(String(100), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str] = mapped_column(String(30))
    horizon_candles: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)


class ExperimentExecutionRow(DatabaseBase):
    """Persistent lifecycle state of one historical experiment execution."""

    __tablename__ = "experiment_executions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="status_supported",
        ),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="progress_percent_range",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="updated_after_created",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="started_after_created",
        ),
        CheckConstraint(
            ("finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)"),
            name="finished_after_started",
        ),
        Index(
            "ix_experiment_executions_status_updated_at",
            "status",
            "updated_at",
        ),
        Index(
            "ix_experiment_executions_dataset_created_at",
            "dataset_id",
            "created_at",
        ),
    )

    execution_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        index=True,
    )

    progress_percent: Mapped[int] = mapped_column(Integer)

    dataset_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    strategy_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    strategy_version: Mapped[str] = mapped_column(String(30))

    experiment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    payload_json: Mapped[str] = mapped_column(Text)


class WalkForwardExecutionRow(DatabaseBase):
    """Persistent lifecycle state of one asynchronous walk-forward job."""

    __tablename__ = "walk_forward_executions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="status_supported",
        ),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="progress_percent_range",
        ),
        CheckConstraint(
            "total_folds > 0",
            name="total_folds_positive",
        ),
        CheckConstraint(
            "completed_folds >= 0 AND completed_folds <= total_folds",
            name="completed_folds_range",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="updated_after_created",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="started_after_created",
        ),
        CheckConstraint(
            ("finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)"),
            name="finished_after_started",
        ),
        Index(
            "ix_walk_forward_executions_status_updated_at",
            "status",
            "updated_at",
        ),
        Index(
            "ix_walk_forward_executions_dataset_created_at",
            "dataset_id",
            "created_at",
        ),
    )

    execution_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        index=True,
    )

    progress_percent: Mapped[int] = mapped_column(Integer)

    dataset_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    strategy_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    strategy_version: Mapped[str] = mapped_column(String(30))

    total_folds: Mapped[int] = mapped_column(Integer)
    completed_folds: Mapped[int] = mapped_column(Integer)

    walk_forward_run_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    payload_json: Mapped[str] = mapped_column(Text)


class WalkForwardRunRow(DatabaseBase):
    """Serialized result of one offline walk-forward research run."""

    __tablename__ = "walk_forward_runs"

    execution_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_dataset_id: Mapped[str] = mapped_column(String(100), index=True)
    plan_id: Mapped[str] = mapped_column(String(100), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str] = mapped_column(String(30))
    horizon_candles: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)


class SimulatedPortfolioRow(DatabaseBase):
    """Persistent aggregate snapshot for an offline paper or shadow portfolio."""

    __tablename__ = "simulated_portfolios"

    __table_args__ = (
        CheckConstraint(
            "mode IN ('paper', 'shadow')",
            name="mode_supported",
        ),
        CheckConstraint(
            "status IN ('active', 'completed')",
            name="status_supported",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="updated_after_created",
        ),
        CheckConstraint(
            "starting_cash > 0",
            name="starting_cash_positive",
        ),
        CheckConstraint(
            "cash >= 0",
            name="cash_non_negative",
        ),
        CheckConstraint(
            "fee_rate >= 0 AND fee_rate < 1",
            name="fee_rate_range",
        ),
        CheckConstraint(
            "fees_paid >= 0",
            name="fees_paid_non_negative",
        ),
        Index(
            "ix_simulated_portfolios_status_updated_at",
            "status",
            "updated_at",
        ),
        Index(
            "ix_simulated_portfolios_dataset_created_at",
            "dataset_id",
            "created_at",
        ),
        Index(
            "ix_simulated_portfolios_mode_status",
            "mode",
            "status",
        ),
    )

    portfolio_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    dataset_id: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    starting_cash: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    cash: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    equity: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    fees_paid: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    payload_json: Mapped[str] = mapped_column(Text)


class SimulatedPositionRow(DatabaseBase):
    """Queryable snapshot of one position in a simulated portfolio."""

    __tablename__ = "simulated_positions"

    __table_args__ = (
        CheckConstraint(
            "side IN ('long', 'short')",
            name="side_supported",
        ),
        CheckConstraint(
            "status IN ('open', 'closed')",
            name="status_supported",
        ),
        CheckConstraint(
            "quantity > 0",
            name="quantity_positive",
        ),
        CheckConstraint(
            "entry_price > 0 AND current_price > 0",
            name="prices_positive",
        ),
        CheckConstraint(
            "reserved_notional > 0",
            name="reserved_notional_positive",
        ),
        CheckConstraint(
            "entry_fee >= 0 AND exit_fee >= 0",
            name="fees_non_negative",
        ),
        CheckConstraint(
            "current_at >= opened_at",
            name="current_after_opened",
        ),
        CheckConstraint(
            "closed_at IS NULL OR closed_at > opened_at",
            name="closed_after_opened",
        ),
        CheckConstraint(
            "(status = 'open' AND exit_price IS NULL AND closed_at IS NULL) "
            "OR (status = 'closed' AND exit_price IS NOT NULL AND closed_at IS NOT NULL)",
            name="status_exit_details_consistent",
        ),
        Index(
            "ix_simulated_positions_portfolio_status",
            "portfolio_id",
            "status",
        ),
        Index(
            "ix_simulated_positions_pair_opened_at",
            "base_asset",
            "quote_asset",
            "opened_at",
        ),
    )

    position_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("simulated_portfolios.portfolio_id", ondelete="CASCADE"),
        index=True,
    )
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    side: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 10))
    entry_price: Mapped[Decimal] = mapped_column(Numeric(30, 10))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    current_price: Mapped[Decimal] = mapped_column(Numeric(30, 10))
    current_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reserved_notional: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    entry_fee: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 10), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    exit_fee: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    gross_realized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    payload_json: Mapped[str] = mapped_column(Text)


class PortfolioTimelineEventRow(DatabaseBase):
    """Persistent audit event for an offline simulated portfolio."""

    __tablename__ = "portfolio_timeline_events"

    __table_args__ = (
        CheckConstraint(
            "sequence_number > 0",
            name="sequence_number_positive",
        ),
        CheckConstraint(
            "event_type IN ('portfolio_created', 'position_opened', 'position_marked', "
            "'position_closed', 'portfolio_completed')",
            name="event_type_supported",
        ),
        UniqueConstraint(
            "portfolio_id",
            "sequence_number",
            name="portfolio_sequence_unique",
        ),
        Index(
            "ix_portfolio_timeline_events_portfolio_occurred_at",
            "portfolio_id",
            "occurred_at",
        ),
        Index(
            "ix_portfolio_timeline_events_portfolio_event_type",
            "portfolio_id",
            "event_type",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("simulated_portfolios.portfolio_id", ondelete="CASCADE"),
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    equity: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    position_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text)


class SystemMetricSampleRow(DatabaseBase):
    """Persisted aggregated system metric snapshot."""

    __tablename__ = "system_metric_samples"

    __table_args__ = (
        CheckConstraint(
            "value >= 0",
            name="value_non_negative",
        ),
        CheckConstraint(
            "window_seconds > 0",
            name="window_seconds_positive",
        ),
        CheckConstraint(
            "observed_count > 0",
            name="observed_count_positive",
        ),
        Index(
            "ix_system_metric_samples_metric_recorded_at",
            "metric_name",
            "recorded_at",
        ),
        Index(
            "ix_system_metric_samples_source_recorded_at",
            "source",
            "recorded_at",
        ),
    )

    sample_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    metric_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    unit: Mapped[str] = mapped_column(
        String(30),
    )

    value: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=30,
            scale=10,
        )
    )

    window_seconds: Mapped[int] = mapped_column(Integer)

    observed_count: Mapped[int] = mapped_column(Integer)

    labels_json: Mapped[dict[str, str]] = mapped_column(JSON)


class ArchitectureRecommendationRow(DatabaseBase):
    """Persisted evidence-backed architecture recommendation."""

    __tablename__ = "architecture_recommendations"

    __table_args__ = (
        CheckConstraint(
            ("candidate IN ('postgresql_tuning', 'redis', 'timescaledb', 'clickhouse')"),
            name="candidate_supported",
        ),
        CheckConstraint(
            ("severity IN ('info', 'warning', 'critical')"),
            name="severity_supported",
        ),
        CheckConstraint(
            ("status IN ('active', 'resolved', 'dismissed')"),
            name="status_supported",
        ),
        CheckConstraint(
            ("last_detected_at >= first_detected_at"),
            name="detection_time_order",
        ),
        Index(
            ("ix_architecture_recommendations_status_last_detected_at"),
            "status",
            "last_detected_at",
        ),
    )

    recommendation_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    candidate: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    severity: Mapped[str] = mapped_column(String(30))

    status: Mapped[str] = mapped_column(
        String(30),
        index=True,
    )

    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    payload_json: Mapped[str] = mapped_column(Text)


class MonitoringRuntimeStateRow(DatabaseBase):
    """Singleton state for the last successful monitoring collector cycle."""

    __tablename__ = "monitoring_runtime_state"

    state_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class CandidateJournalRow(DatabaseBase):
    """Queryable immutable audit record for a completed candidate lifecycle."""

    __tablename__ = "candidate_journals"

    __table_args__ = (
        CheckConstraint(
            "schema_version > 0",
            name="schema_version_positive",
        ),
        CheckConstraint(
            "recorded_at >= evaluated_at",
            name="recorded_after_evaluated",
        ),
        CheckConstraint(
            "attempted_count >= 0",
            name="attempted_count_non_negative",
        ),
        CheckConstraint(
            "status IN ('no_position', 'closed')",
            name="status_supported",
        ),
        CheckConstraint(
            "exit_reason IS NULL OR exit_reason IN "
            "('invalidation', 'target', 'trend_reversal', 'portfolio_risk', "
            "'data_unreliable', 'time_expiry', 'end_of_data')",
            name="exit_reason_supported",
        ),
        CheckConstraint(
            "(status = 'no_position' "
            "AND selected_candidate_id IS NULL "
            "AND signal_id IS NULL "
            "AND experiment_id IS NULL "
            "AND position_id IS NULL "
            "AND exit_reason IS NULL) "
            "OR "
            "(status = 'closed' "
            "AND selected_candidate_id IS NOT NULL "
            "AND signal_id IS NOT NULL "
            "AND experiment_id IS NOT NULL "
            "AND position_id IS NOT NULL "
            "AND exit_reason IS NOT NULL)",
            name="status_lineage_consistent",
        ),
        Index(
            "ix_candidate_journals_dataset_recorded_at",
            "dataset_id",
            "recorded_at",
        ),
        Index(
            "ix_candidate_journals_portfolio_recorded_at",
            "portfolio_id",
            "recorded_at",
        ),
    )

    journal_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), index=True)
    dataset_id: Mapped[str] = mapped_column(String(100), index=True)
    portfolio_id: Mapped[str] = mapped_column(String(100), index=True)
    attempted_count: Mapped[int] = mapped_column(Integer)
    selected_candidate_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    signal_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    experiment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    position_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    exit_reason: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text)


class CandidateProjectionRow(DatabaseBase):
    """Derived query model for the latest persisted candidate projection."""

    __tablename__ = "candidate_projections"

    __table_args__ = (
        CheckConstraint(
            "occurrence_count > 0",
            name="occurrence_count_positive",
        ),
        CheckConstraint(
            "latest_rank > 0",
            name="latest_rank_positive",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_supported",
        ),
        CheckConstraint(
            "signal_score >= -1 AND signal_score <= 1",
            name="signal_score_supported",
        ),
        CheckConstraint(
            "latest_ranking_score >= 0 AND latest_ranking_score <= 1",
            name="latest_ranking_score_supported",
        ),
        CheckConstraint(
            "status IN ('candidate', 'selected', 'stale', 'invalidated')",
            name="status_supported",
        ),
        CheckConstraint(
            "action IN ('long', 'short', 'neutral', 'no_trade')",
            name="action_supported",
        ),
        CheckConstraint(
            "latest_replay_status IS NULL OR "
            "latest_replay_status IN ('opened', 'risk_rejected', 'no_fill')",
            name="latest_replay_status_supported",
        ),
        CheckConstraint(
            "latest_risk_decision IS NULL OR latest_risk_decision IN ('approved', 'rejected')",
            name="latest_risk_decision_supported",
        ),
        CheckConstraint(
            "selected IN (0, 1)",
            name="selected_boolean",
        ),
        CheckConstraint(
            "exit_reason IS NULL OR exit_reason IN "
            "('invalidation', 'target', 'trend_reversal', 'portfolio_risk', "
            "'data_unreliable', 'time_expiry', 'end_of_data')",
            name="exit_reason_supported",
        ),
        CheckConstraint(
            "(selected = 1 "
            "AND latest_replay_status = 'opened' "
            "AND latest_risk_decision IS NOT NULL "
            "AND position_id IS NOT NULL "
            "AND exit_reason IS NOT NULL) "
            "OR "
            "(selected = 0 "
            "AND position_id IS NULL "
            "AND exit_reason IS NULL "
            "AND ((latest_replay_status IS NULL AND latest_risk_decision IS NULL) "
            "OR (latest_replay_status IS NOT NULL "
            "AND latest_replay_status <> 'opened' "
            "AND latest_risk_decision IS NOT NULL)))",
            name="selection_lineage_consistent",
        ),
        Index(
            "ix_candidate_projections_dataset_latest_recorded_at",
            "dataset_id",
            "latest_recorded_at",
        ),
        Index(
            "ix_candidate_projections_pair_timeframe",
            "base_asset",
            "quote_asset",
            "market_type",
            "timeframe",
        ),
        Index(
            "ix_candidate_projections_strategy_latest_recorded_at",
            "strategy_name",
            "strategy_version",
            "latest_recorded_at",
        ),
    )

    candidate_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(100), index=True)
    experiment_id: Mapped[str] = mapped_column(String(100), index=True)
    signal_id: Mapped[str] = mapped_column(String(100), index=True)

    latest_journal_id: Mapped[str] = mapped_column(String(100), index=True)
    latest_recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    status: Mapped[str] = mapped_column(String(20), index=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    base_asset: Mapped[str] = mapped_column(String(30))
    quote_asset: Mapped[str] = mapped_column(String(30))
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))

    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    signal_score: Mapped[Decimal] = mapped_column(Numeric(18, 10))

    occurrence_count: Mapped[int] = mapped_column(Integer)
    latest_rank: Mapped[int] = mapped_column(Integer)
    latest_ranking_score: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    latest_replay_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )
    latest_risk_decision: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )
    selected: Mapped[int] = mapped_column(Integer, index=True)

    position_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    exit_reason: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text)
