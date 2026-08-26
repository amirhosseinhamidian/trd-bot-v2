import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class SystemMetricName(StrEnum):
    """Stable names of aggregated system capacity metrics."""

    API_REQUEST_LATENCY_P95 = "api_request_latency_p95"
    API_ERROR_RATE = "api_error_rate"

    DATABASE_QUERY_LATENCY_P95 = "database_query_latency_p95"
    DATABASE_POOL_UTILIZATION = "database_pool_utilization"
    DATABASE_CPU_UTILIZATION = "database_cpu_utilization"
    DATABASE_DISK_UTILIZATION = "database_disk_utilization"

    JOB_QUEUE_WAIT_P95 = "job_queue_wait_p95"
    BACKTEST_FAILURE_RATE = "backtest_failure_rate"

    MARKET_DATA_LAG = "market_data_lag"
    INVALID_CANDLE_RATIO = "invalid_candle_ratio"
    CANDLE_STORAGE_SHARE = "candle_storage_share"

    API_REPEATED_READ_RATIO = "api_repeated_read_ratio"
    TIME_SERIES_QUERY_LATENCY_P95 = "time_series_query_latency_p95"
    ANALYTICAL_QUERY_LATENCY_P95 = "analytical_query_latency_p95"
    ANALYTICAL_DATABASE_RESOURCE_SHARE = "analytical_database_resource_share"


class SystemMetricUnit(StrEnum):
    """Supported units for capacity metrics."""

    SECONDS = "seconds"
    FRACTION = "fraction"
    COUNT = "count"
    BYTES = "bytes"


class SystemMetricSource(StrEnum):
    """Subsystem responsible for one metric observation."""

    API = "api"
    DATABASE = "database"
    WORKER = "worker"
    MARKET_DATA = "market_data"


METRIC_UNITS: dict[
    SystemMetricName,
    SystemMetricUnit,
] = {
    SystemMetricName.API_REQUEST_LATENCY_P95: (SystemMetricUnit.SECONDS),
    SystemMetricName.API_ERROR_RATE: (SystemMetricUnit.FRACTION),
    SystemMetricName.DATABASE_QUERY_LATENCY_P95: (SystemMetricUnit.SECONDS),
    SystemMetricName.DATABASE_POOL_UTILIZATION: (SystemMetricUnit.FRACTION),
    SystemMetricName.DATABASE_CPU_UTILIZATION: (SystemMetricUnit.FRACTION),
    SystemMetricName.DATABASE_DISK_UTILIZATION: (SystemMetricUnit.FRACTION),
    SystemMetricName.JOB_QUEUE_WAIT_P95: (SystemMetricUnit.SECONDS),
    SystemMetricName.BACKTEST_FAILURE_RATE: (SystemMetricUnit.FRACTION),
    SystemMetricName.MARKET_DATA_LAG: (SystemMetricUnit.SECONDS),
    SystemMetricName.INVALID_CANDLE_RATIO: (SystemMetricUnit.FRACTION),
    SystemMetricName.CANDLE_STORAGE_SHARE: (SystemMetricUnit.FRACTION),
    SystemMetricName.API_REPEATED_READ_RATIO: (SystemMetricUnit.FRACTION),
    SystemMetricName.TIME_SERIES_QUERY_LATENCY_P95: (SystemMetricUnit.SECONDS),
    SystemMetricName.ANALYTICAL_QUERY_LATENCY_P95: (SystemMetricUnit.SECONDS),
    SystemMetricName.ANALYTICAL_DATABASE_RESOURCE_SHARE: (SystemMetricUnit.FRACTION),
}


def normalize_timestamp(value: datetime) -> datetime:
    """Normalize a timezone-aware timestamp to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include timezone information")

    return value.astimezone(UTC)


def build_metric_sample_id(
    *,
    metric_name: SystemMetricName,
    source: SystemMetricSource,
    recorded_at: datetime,
    window_seconds: int,
) -> str:
    """Build a deterministic identifier for one metric window."""

    normalized_time = normalize_timestamp(recorded_at)

    identity = "::".join(
        [
            metric_name.value,
            source.value,
            normalized_time.isoformat(),
            str(window_seconds),
        ]
    )

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    return f"metric-sample-{digest[:16]}"


class SystemMetricSample(BaseModel):
    """One aggregated metric observation for a time window."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    sample_id: str = Field(pattern=r"^metric-sample-[a-f0-9]{16}$")

    metric_name: SystemMetricName
    source: SystemMetricSource
    unit: SystemMetricUnit

    value: Decimal = Field(ge=0)

    recorded_at: datetime

    window_seconds: int = Field(ge=1)
    observed_count: int = Field(ge=1)

    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_sample(self) -> Self:
        expected_unit = METRIC_UNITS[self.metric_name]

        if self.unit is not expected_unit:
            raise ValueError("metric unit does not match metric name")

        if self.unit is SystemMetricUnit.FRACTION and self.value > Decimal("1"):
            raise ValueError("fraction metric cannot exceed one")

        expected_id = build_metric_sample_id(
            metric_name=self.metric_name,
            source=self.source,
            recorded_at=self.recorded_at,
            window_seconds=self.window_seconds,
        )

        if self.sample_id != expected_id:
            raise ValueError("metric sample ID does not match its identity")

        return self


class ArchitectureCandidate(StrEnum):
    """Possible architecture changes suggested by capacity evidence."""

    POSTGRESQL_TUNING = "postgresql_tuning"
    REDIS = "redis"
    TIMESCALEDB = "timescaledb"
    CLICKHOUSE = "clickhouse"


class RecommendationSeverity(StrEnum):
    """Severity of one architecture recommendation."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RecommendationStatus(StrEnum):
    """Lifecycle state of one architecture recommendation."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ArchitectureEvidence(BaseModel):
    """One threshold observation supporting a recommendation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    metric_name: SystemMetricName
    observed_value: Decimal = Field(ge=0)
    threshold_value: Decimal = Field(ge=0)

    comparison: Literal[
        "greater_than_or_equal",
        "less_than_or_equal",
    ]

    consecutive_windows: int = Field(ge=1)


def build_architecture_recommendation_id(
    *,
    candidate: ArchitectureCandidate,
    first_detected_at: datetime,
) -> str:
    """Build a deterministic recommendation identifier."""

    normalized_time = normalize_timestamp(first_detected_at)

    identity = "::".join(
        [
            candidate.value,
            normalized_time.isoformat(),
        ]
    )

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    return f"recommendation-{digest[:16]}"


class ArchitectureRecommendation(BaseModel):
    """Evidence-backed capacity recommendation for the dashboard."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    recommendation_id: str = Field(pattern=r"^recommendation-[a-f0-9]{16}$")

    candidate: ArchitectureCandidate
    severity: RecommendationSeverity
    status: RecommendationStatus = RecommendationStatus.ACTIVE

    title: str = Field(
        min_length=1,
        max_length=150,
    )

    summary: str = Field(
        min_length=1,
        max_length=500,
    )

    first_detected_at: datetime
    last_detected_at: datetime

    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    evidence: tuple[
        ArchitectureEvidence,
        ...,
    ] = Field(min_length=1)

    interpretation: Literal["capacity_planning_only"] = "capacity_planning_only"

    @field_validator(
        "first_detected_at",
        "last_detected_at",
        "acknowledged_at",
        "resolved_at",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_recommendation(self) -> Self:
        if self.last_detected_at < self.first_detected_at:
            raise ValueError("last detection cannot precede first detection")

        if self.acknowledged_at is not None and self.acknowledged_at < self.first_detected_at:
            raise ValueError("acknowledgement cannot precede first detection")

        if self.resolved_at is not None and self.resolved_at < self.first_detected_at:
            raise ValueError("resolution cannot precede first detection")

        if self.resolved_at is not None and self.status is not RecommendationStatus.RESOLVED:
            raise ValueError("resolved_at requires resolved recommendation status")

        if (
            self.acknowledged_at is not None
            and self.resolved_at is not None
            and self.acknowledged_at > self.resolved_at
        ):
            raise ValueError("acknowledgement cannot follow resolution")

        expected_id = build_architecture_recommendation_id(
            candidate=self.candidate,
            first_detected_at=(self.first_detected_at),
        )

        if self.recommendation_id != expected_id:
            raise ValueError("recommendation ID does not match its identity")

        return self

    def acknowledge(
        self,
        *,
        acknowledged_at: datetime,
    ) -> Self:
        """Mark an active recommendation as seen without resolving it."""

        if self.status is not RecommendationStatus.ACTIVE:
            raise ValueError("only active recommendations can be acknowledged")

        if self.acknowledged_at is not None:
            return self

        return type(self).model_validate(
            {
                **self.model_dump(),
                "acknowledged_at": normalize_timestamp(acknowledged_at),
            }
        )

    def resolve(
        self,
        *,
        resolved_at: datetime,
    ) -> Self:
        """Resolve an active recommendation idempotently."""

        if self.status is RecommendationStatus.RESOLVED:
            return self

        if self.status is not RecommendationStatus.ACTIVE:
            raise ValueError("only active recommendations can be resolved")

        return type(self).model_validate(
            {
                **self.model_dump(),
                "status": RecommendationStatus.RESOLVED,
                "resolved_at": normalize_timestamp(resolved_at),
            }
        )
