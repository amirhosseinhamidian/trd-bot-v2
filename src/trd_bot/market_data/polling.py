import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("polling timestamps must include timezone information")
    return value.astimezone(UTC)


def _stable_id(prefix: str, value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:16]}"


class MarketDataWatchlistState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class MarketDataWatchlistRoute(BaseModel):
    """One explicit provider connection in fallback order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connection_id: str = Field(min_length=1, max_length=100)
    provider_id: str = Field(min_length=1, max_length=50)


class MarketDataWatchlistEntry(BaseModel):
    """Durable polling schedule for one normalized Crypto Spot stream."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-watchlist-v1"] = "market-data-watchlist-v1"
    watchlist_id: str = Field(pattern=r"^market-watch-[a-f0-9]{16}$")
    pair: TradingPair
    timeframe: Timeframe
    routes: tuple[MarketDataWatchlistRoute, MarketDataWatchlistRoute]
    policy_version: Literal["market-data-service-level-policy-v1"] = (
        "market-data-service-level-policy-v1"
    )
    polling_interval_seconds: int = Field(ge=1)
    lookback_candles: int = Field(default=3, ge=1, le=20)
    state: MarketDataWatchlistState = MarketDataWatchlistState.ACTIVE
    next_poll_at: datetime
    last_enqueued_for: datetime | None = None
    last_job_id: str | None = Field(default=None, pattern=r"^job-[a-f0-9]{20}$")
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "next_poll_at",
        "last_enqueued_for",
        "created_at",
        "updated_at",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        provider_order = tuple(route.provider_id for route in self.routes)
        if provider_order != ("kraken-public", "binance-public"):
            raise ValueError("watchlist provider order must be Kraken then Binance")
        if len({route.connection_id for route in self.routes}) != len(self.routes):
            raise ValueError("watchlist routes must use distinct connections")
        if self.updated_at < self.created_at or self.next_poll_at < self.created_at:
            raise ValueError("watchlist lifecycle timestamps are inconsistent")
        if (self.last_enqueued_for is None) != (self.last_job_id is None):
            raise ValueError("watchlist enqueue time and job reference must be stored together")
        if self.last_enqueued_for is not None and self.last_enqueued_for < self.created_at:
            raise ValueError("watchlist enqueue time cannot precede creation")
        if self.watchlist_id != self.build_watchlist_id(
            pair=self.pair,
            timeframe=self.timeframe,
        ):
            raise ValueError("watchlist ID is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        pair: TradingPair,
        timeframe: Timeframe,
        routes: tuple[MarketDataWatchlistRoute, MarketDataWatchlistRoute],
        polling_interval_seconds: int,
        lookback_candles: int,
        now: datetime,
    ) -> Self:
        normalized = _normalize_timestamp(now)
        return cls(
            watchlist_id=cls.build_watchlist_id(pair=pair, timeframe=timeframe),
            pair=pair,
            timeframe=timeframe,
            routes=routes,
            polling_interval_seconds=polling_interval_seconds,
            lookback_candles=lookback_candles,
            next_poll_at=normalized,
            created_at=normalized,
            updated_at=normalized,
        )

    @staticmethod
    def build_watchlist_id(*, pair: TradingPair, timeframe: Timeframe) -> str:
        return _stable_id(
            "market-watch",
            {
                "pair": pair.model_dump(mode="json"),
                "timeframe": timeframe.value,
            },
        )

    def mark_enqueued(
        self,
        *,
        job_id: str,
        enqueued_at: datetime,
    ) -> Self:
        normalized = _normalize_timestamp(enqueued_at)
        scheduled_for = self.next_poll_at
        next_poll_at = scheduled_for
        interval = timedelta(seconds=self.polling_interval_seconds)
        while next_poll_at <= normalized:
            next_poll_at += interval
        return type(self).model_validate(
            self.model_copy(
                update={
                    "next_poll_at": next_poll_at,
                    "last_enqueued_for": scheduled_for,
                    "last_job_id": job_id,
                    "updated_at": normalized,
                }
            ).model_dump()
        )


class MarketDataPollJobPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-poll-job-v1"] = "market-data-poll-job-v1"
    watchlist_id: str = Field(pattern=r"^market-watch-[a-f0-9]{16}$")
    scheduled_for: datetime

    @field_validator("scheduled_for")
    @classmethod
    def normalize_scheduled_for(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)


class MarketDataPollAttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    NO_DATA = "no_data"
    CONNECTION_UNAVAILABLE = "connection_unavailable"
    PROVIDER_FAILED = "provider_failed"
    QUALITY_REJECTED = "quality_rejected"
    RATE_LIMITED_LOCALLY = "rate_limited_locally"
    INGESTION_FAILED = "ingestion_failed"
    FINALIZATION_FAILED = "finalization_failed"


class MarketDataPollAttempt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ordinal: int = Field(ge=1, le=2)
    connection_id: str = Field(min_length=1, max_length=100)
    provider_id: str = Field(min_length=1, max_length=50)
    outcome: MarketDataPollAttemptOutcome
    received_candles: int = Field(ge=0)
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    started_at: datetime
    completed_at: datetime

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("poll attempt completion cannot precede start")
        successful = self.outcome is MarketDataPollAttemptOutcome.SUCCEEDED
        no_data = self.outcome is MarketDataPollAttemptOutcome.NO_DATA
        if successful and (self.received_candles < 1 or self.error_code is not None):
            raise ValueError("successful poll attempt requires candles and no error")
        if no_data and (self.received_candles != 0 or self.error_code is not None):
            raise ValueError("no-data poll attempt cannot contain candles or an error")
        if not successful and not no_data and self.error_code is None:
            raise ValueError("failed poll attempt requires an error code")
        return self


class MarketDataPollRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    NO_DATA = "no_data"
    FAILED = "failed"


class MarketDataPollRun(BaseModel):
    """Sanitized durable evidence for one background-job polling attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-poll-run-v1"] = "market-data-poll-run-v1"
    run_id: str = Field(pattern=r"^market-poll-run-[a-f0-9]{16}$")
    job_id: str = Field(pattern=r"^job-[a-f0-9]{20}$")
    job_attempt: int = Field(ge=1, le=10)
    watchlist_id: str = Field(pattern=r"^market-watch-[a-f0-9]{16}$")
    scheduled_for: datetime
    status: MarketDataPollRunStatus
    attempts: tuple[MarketDataPollAttempt, ...] = Field(min_length=1, max_length=2)
    selected_connection_id: str | None = Field(default=None, min_length=1, max_length=100)
    selected_provider_id: str | None = Field(default=None, min_length=1, max_length=50)
    received_candles: int = Field(ge=0)
    accepted_events: int = Field(ge=0)
    duplicate_events: int = Field(ge=0)
    revision_required_events: int = Field(ge=0)
    watermark_before_id: str | None = Field(
        default=None,
        pattern=r"^market-watermark-[a-f0-9]{16}$",
    )
    watermark_after_id: str | None = Field(
        default=None,
        pattern=r"^market-watermark-[a-f0-9]{16}$",
    )
    failure_retryable: bool = False
    failure_code: str | None = Field(default=None, min_length=1, max_length=100)
    failure_message: str | None = Field(default=None, min_length=1, max_length=500)
    started_at: datetime
    completed_at: datetime

    @field_validator("scheduled_for", "started_at", "completed_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_run(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("poll run completion cannot precede start")
        if tuple(attempt.ordinal for attempt in self.attempts) != tuple(
            range(1, len(self.attempts) + 1)
        ):
            raise ValueError("poll attempts must preserve provider order")

        decision_total = (
            self.accepted_events + self.duplicate_events + self.revision_required_events
        )
        if self.status is MarketDataPollRunStatus.SUCCEEDED:
            if (
                self.selected_connection_id is None
                or self.selected_provider_id is None
                or self.received_candles < 1
                or decision_total != self.received_candles
                or self.watermark_before_id is None
                or self.watermark_after_id is None
                or self.failure_retryable
                or self.failure_code is not None
                or self.failure_message is not None
            ):
                raise ValueError("successful poll run outcome is inconsistent")
        elif self.status is MarketDataPollRunStatus.NO_DATA:
            if (
                self.selected_connection_id is not None
                or self.selected_provider_id is not None
                or self.received_candles != 0
                or decision_total != 0
                or self.watermark_before_id is not None
                or self.watermark_after_id is not None
                or self.failure_retryable
                or self.failure_code is not None
                or self.failure_message is not None
            ):
                raise ValueError("no-data poll run outcome is inconsistent")
        elif (
            self.selected_connection_id is not None
            or self.selected_provider_id is not None
            or self.received_candles != 0
            or decision_total != 0
            or self.watermark_before_id is not None
            or self.watermark_after_id is not None
            or self.failure_code is None
            or self.failure_message is None
        ):
            raise ValueError("failed poll run outcome is inconsistent")
        return self

    @staticmethod
    def build_run_id(*, job_id: str, job_attempt: int) -> str:
        return _stable_id(
            "market-poll-run",
            {"job_id": job_id, "job_attempt": job_attempt},
        )


class MarketDataPollingError(RuntimeError):
    """Base error for one durable polling job."""


class MarketDataPollingFailedError(MarketDataPollingError):
    """Every explicit provider route failed for the polling attempt."""

    def __init__(
        self,
        *,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> None:
        self.error_code = error_code
        self.error_message = error_message
        self.retryable = retryable
        super().__init__(error_message)
