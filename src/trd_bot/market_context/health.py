from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import TradingPair
from trd_bot.jobs import BackgroundJobStatus
from trd_bot.market_context.contracts import MarketContextAssessmentStatus


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-context monitoring timestamps must include timezone information")
    return value.astimezone(UTC)


class MarketContextFreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    NO_DATA = "no_data"


class MarketContextStreamHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    NO_DATA = "no_data"


class MarketContextMonitoringOverallStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    NO_DATA = "no_data"


class MarketContextHealthIssueCode(StrEnum):
    ASSESSMENT_EXPIRED = "assessment_expired"
    ASSESSMENT_MISSING = "assessment_missing"
    BOUNDARY_LAGGING = "boundary_lagging"
    EVALUATION_FAILED = "evaluation_failed"
    EVALUATION_PENDING = "evaluation_pending"
    EVALUATION_RETRYING = "evaluation_retrying"
    ASSESSMENT_NOT_READY = "assessment_not_ready"


class MarketContextStreamHealth(BaseModel):
    """Sanitized operational state for one source and trading pair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    health_status: MarketContextStreamHealthStatus
    freshness_status: MarketContextFreshnessStatus
    issue_codes: tuple[MarketContextHealthIssueCode, ...] = ()
    expected_as_of: datetime

    latest_assessment_id: str | None = Field(
        default=None,
        pattern=r"^market-regime-[a-f0-9]{16}$",
    )
    latest_assessment_status: MarketContextAssessmentStatus | None = None
    latest_assessment_as_of: datetime | None = None
    assessed_at: datetime | None = None
    expires_at: datetime | None = None
    assessment_age_seconds: int | None = Field(default=None, ge=0)
    boundary_lag_seconds: int | None = Field(default=None, ge=0)
    feature_set_version: str | None = Field(default=None, min_length=1, max_length=100)
    algorithm_version: str | None = Field(default=None, min_length=1, max_length=100)

    latest_job_id: str | None = Field(default=None, pattern=r"^job-[a-f0-9]{20}$")
    latest_job_status: BackgroundJobStatus | None = None
    latest_job_as_of: datetime | None = None
    latest_job_updated_at: datetime | None = None
    latest_job_progress_percent: int | None = Field(default=None, ge=0, le=100)
    latest_job_attempt_count: int | None = Field(default=None, ge=0)
    latest_job_max_attempts: int | None = Field(default=None, ge=1)
    latest_job_error_code: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("market-context monitoring source cannot be empty")
        return normalized

    @field_validator("issue_codes")
    @classmethod
    def validate_issue_codes(
        cls,
        value: tuple[MarketContextHealthIssueCode, ...],
    ) -> tuple[MarketContextHealthIssueCode, ...]:
        if value != tuple(sorted(value, key=lambda item: item.value)):
            raise ValueError("market-context issue codes must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("market-context issue codes must be unique")
        return value

    @field_validator(
        "expected_as_of",
        "latest_assessment_as_of",
        "assessed_at",
        "expires_at",
        "latest_job_as_of",
        "latest_job_updated_at",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_projection(self) -> Self:
        assessment_fields = (
            self.latest_assessment_status,
            self.latest_assessment_as_of,
            self.assessed_at,
            self.expires_at,
            self.assessment_age_seconds,
            self.boundary_lag_seconds,
            self.feature_set_version,
            self.algorithm_version,
        )
        if self.latest_assessment_id is None:
            if any(item is not None for item in assessment_fields):
                raise ValueError("market-context assessment projection is incomplete")
            if self.freshness_status is not MarketContextFreshnessStatus.NO_DATA:
                raise ValueError("missing market-context assessment must report no data")
        elif any(item is None for item in assessment_fields):
            raise ValueError("market-context assessment projection is incomplete")
        elif self.freshness_status is MarketContextFreshnessStatus.NO_DATA:
            raise ValueError("persisted market-context assessment cannot report no data")

        job_fields = (
            self.latest_job_status,
            self.latest_job_as_of,
            self.latest_job_updated_at,
            self.latest_job_progress_percent,
            self.latest_job_attempt_count,
            self.latest_job_max_attempts,
        )
        if self.latest_job_id is None:
            if (
                any(item is not None for item in job_fields)
                or self.latest_job_error_code is not None
            ):
                raise ValueError("market-context job projection is incomplete")
        elif any(item is None for item in job_fields):
            raise ValueError("market-context job projection is incomplete")
        return self


class MarketContextBacklogSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    queued_jobs: int = Field(ge=0)
    running_jobs: int = Field(ge=0)
    retrying_jobs: int = Field(ge=0)
    failed_streams: int = Field(ge=0)
    expired_assessments: int = Field(ge=0)
    lagging_streams: int = Field(ge=0)
    missing_assessments: int = Field(ge=0)


class MarketContextMonitoringSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-monitoring-v1"] = "market-context-monitoring-v1"
    generated_at: datetime
    overall_status: MarketContextMonitoringOverallStatus
    stream_count: int = Field(ge=0)
    healthy_count: int = Field(ge=0)
    degraded_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    no_data_count: int = Field(ge=0)
    backlog: MarketContextBacklogSummary
    streams: tuple[MarketContextStreamHealth, ...]

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.stream_count != len(self.streams):
            raise ValueError("market-context stream count is inconsistent")
        if self.healthy_count != sum(
            item.health_status is MarketContextStreamHealthStatus.HEALTHY for item in self.streams
        ):
            raise ValueError("market-context healthy count is inconsistent")
        if self.degraded_count != sum(
            item.health_status is MarketContextStreamHealthStatus.DEGRADED for item in self.streams
        ):
            raise ValueError("market-context degraded count is inconsistent")
        if self.stale_count != sum(
            item.freshness_status is MarketContextFreshnessStatus.STALE for item in self.streams
        ):
            raise ValueError("market-context stale count is inconsistent")
        if self.no_data_count != sum(
            item.freshness_status is MarketContextFreshnessStatus.NO_DATA for item in self.streams
        ):
            raise ValueError("market-context no-data count is inconsistent")
        return self


class MarketContextMonitoringReader(Protocol):
    def read(self, *, generated_at: datetime | None = None) -> MarketContextMonitoringSummary: ...
