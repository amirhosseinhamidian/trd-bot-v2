from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
            "(health_status = 'untested' AND last_tested_at IS NULL AND last_error IS NULL) "
            "OR (health_status = 'healthy' AND last_tested_at IS NOT NULL "
            "AND last_error IS NULL) "
            "OR (health_status = 'unhealthy' AND last_tested_at IS NOT NULL "
            "AND last_error IS NOT NULL)",
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
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


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
