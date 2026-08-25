from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
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
