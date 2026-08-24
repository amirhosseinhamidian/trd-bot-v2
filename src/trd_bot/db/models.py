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
