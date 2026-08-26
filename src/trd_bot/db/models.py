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
