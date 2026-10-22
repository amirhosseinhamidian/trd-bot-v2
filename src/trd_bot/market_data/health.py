from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.jobs import BackgroundJobStatus
from trd_bot.market_data.connections import (
    MarketDataConnectionHealth,
    MarketDataConnectionState,
)
from trd_bot.market_data.events import MarketDataEventReason
from trd_bot.market_data.polling import (
    MarketDataPollRunStatus,
    MarketDataWatchlistState,
)
from trd_bot.market_data.replay import MarketDataRevisionKind


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-data monitoring timestamps must include timezone information")
    return value.astimezone(UTC)


class MarketDataFreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    NO_DATA = "no_data"


class MarketDataStreamHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    PAUSED = "paused"
    NO_DATA = "no_data"


class MarketDataMonitoringOverallStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    NO_DATA = "no_data"


class MarketDataProviderRouteHealth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ordinal: int = Field(ge=1, le=2)
    provider_id: str = Field(min_length=1, max_length=50)
    connection_id: str = Field(min_length=1, max_length=100)
    connection_state: MarketDataConnectionState | None = None
    health_status: MarketDataConnectionHealth | None = None
    last_tested_at: datetime | None = None
    last_error_code: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("last_tested_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)


class MarketDataStreamHealth(BaseModel):
    """Read-only operational projection for one watchlist stream."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    watchlist_id: str = Field(pattern=r"^market-watch-[a-f0-9]{16}$")
    pair: TradingPair
    timeframe: Timeframe
    watchlist_state: MarketDataWatchlistState
    health_status: MarketDataStreamHealthStatus
    freshness_status: MarketDataFreshnessStatus
    provider_routes: tuple[MarketDataProviderRouteHealth, ...] = Field(min_length=2, max_length=2)
    selected_provider_id: str | None = Field(default=None, min_length=1, max_length=50)
    latest_poll_status: MarketDataPollRunStatus | None = None
    latest_poll_completed_at: datetime | None = None
    latest_poll_error_code: str | None = Field(default=None, min_length=1, max_length=100)
    latest_finalized_window_end: datetime | None = None
    latest_watermark_time: datetime | None = None
    data_age_seconds: int | None = Field(default=None, ge=0)
    lag_seconds: int | None = Field(default=None, ge=0)
    freshness_target_seconds: int = Field(ge=1)
    poll_overdue_seconds: int = Field(ge=0)
    finalization_backlog_count: int = Field(ge=0)

    @field_validator(
        "latest_poll_completed_at",
        "latest_finalized_window_end",
        "latest_watermark_time",
    )
    @classmethod
    def normalize_optional_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_freshness(self) -> Self:
        has_data = self.latest_finalized_window_end is not None
        if has_data != (self.data_age_seconds is not None):
            raise ValueError("market-data age must match finalized-window availability")
        if has_data != (self.lag_seconds is not None):
            raise ValueError("market-data lag must match finalized-window availability")
        if has_data == (self.freshness_status is MarketDataFreshnessStatus.NO_DATA):
            raise ValueError("market-data freshness state is inconsistent")
        if self.watchlist_state is MarketDataWatchlistState.PAUSED:
            if self.health_status is not MarketDataStreamHealthStatus.PAUSED:
                raise ValueError("paused watchlist requires paused health")
        elif self.health_status is MarketDataStreamHealthStatus.PAUSED:
            raise ValueError("active watchlist cannot report paused health")
        return self


class MarketDataReplayHealth(BaseModel):
    """Sanitized replay lifecycle without payload or worker identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    replay_id: str = Field(pattern=r"^market-replay-[a-f0-9]{16}$")
    decision_id: str = Field(pattern=r"^market-decision-[a-f0-9]{16}$")
    window_id: str = Field(pattern=r"^market-window-[a-f0-9]{16}$")
    reason: MarketDataEventReason
    requested_by: str = Field(min_length=1, max_length=100)
    requested_at: datetime
    job_id: str = Field(pattern=r"^job-[a-f0-9]{20}$")
    job_status: BackgroundJobStatus
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    revision_id: str | None = Field(
        default=None,
        pattern=r"^market-revision-[a-f0-9]{16}$",
    )
    revision_kind: MarketDataRevisionKind | None = None
    revised_version: int | None = Field(default=None, ge=1)
    completed_at: datetime | None = None

    @field_validator("requested_at", "completed_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_revision(self) -> Self:
        has_revision = self.revision_id is not None
        if has_revision != (self.revision_kind is not None):
            raise ValueError("replay revision kind is inconsistent")
        if has_revision != (self.revised_version is not None):
            raise ValueError("replay revised version is inconsistent")
        if has_revision != (self.completed_at is not None):
            raise ValueError("replay completion time is inconsistent")
        return self


class MarketDataBacklogSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    poll_jobs: int = Field(ge=0)
    replay_jobs: int = Field(ge=0)
    overdue_watchlists: int = Field(ge=0)
    finalization_windows: int = Field(ge=0)
    unrequested_revisions: int = Field(ge=0)
    pending_replays: int = Field(ge=0)
    failed_replays: int = Field(ge=0)
    completed_revisions: int = Field(ge=0)


class MarketDataMonitoringSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-monitoring-v1"] = "market-data-monitoring-v1"
    generated_at: datetime
    overall_status: MarketDataMonitoringOverallStatus
    stream_count: int = Field(ge=0)
    healthy_count: int = Field(ge=0)
    degraded_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    no_data_count: int = Field(ge=0)
    paused_count: int = Field(ge=0)
    backlog: MarketDataBacklogSummary
    streams: tuple[MarketDataStreamHealth, ...]
    recent_replays: tuple[MarketDataReplayHealth, ...]

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.stream_count != len(self.streams):
            raise ValueError("market-data stream count is inconsistent")
        if self.healthy_count != sum(
            item.health_status is MarketDataStreamHealthStatus.HEALTHY for item in self.streams
        ):
            raise ValueError("market-data healthy count is inconsistent")
        if self.degraded_count != sum(
            item.health_status is MarketDataStreamHealthStatus.DEGRADED for item in self.streams
        ):
            raise ValueError("market-data degraded count is inconsistent")
        if self.stale_count != sum(
            item.freshness_status is MarketDataFreshnessStatus.STALE for item in self.streams
        ):
            raise ValueError("market-data stale count is inconsistent")
        if self.no_data_count != sum(
            item.freshness_status is MarketDataFreshnessStatus.NO_DATA for item in self.streams
        ):
            raise ValueError("market-data no-data count is inconsistent")
        if self.paused_count != sum(
            item.health_status is MarketDataStreamHealthStatus.PAUSED for item in self.streams
        ):
            raise ValueError("market-data paused count is inconsistent")
        return self


class MarketDataMonitoringReader(Protocol):
    def read(self, *, generated_at: datetime | None = None) -> MarketDataMonitoringSummary: ...
