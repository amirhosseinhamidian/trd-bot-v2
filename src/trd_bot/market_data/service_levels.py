from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe


class CapacityEvidenceScope(StrEnum):
    """Independent evidence areas required before freezing capacity."""

    PROVIDER = "provider"
    EVENT_PROCESSING = "event_processing"
    DATABASE = "database"
    BACKGROUND_JOBS = "background_jobs"
    STORAGE = "storage"


class CapacityEvidenceMethod(StrEnum):
    """How a capacity observation was obtained."""

    LIVE_PROBE = "live_probe"
    SYNTHETIC_BENCHMARK = "synthetic_benchmark"
    PRODUCTION_TELEMETRY = "production_telemetry"
    UNAVAILABLE = "unavailable"


class TimeframeServiceLevel(BaseModel):
    """Freshness and event-time budgets for one candle timeframe."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timeframe: Timeframe
    polling_interval_seconds: int = Field(ge=1)
    allowed_lateness_seconds: int = Field(ge=0)
    maximum_future_clock_skew_seconds: int = Field(ge=0)
    provisional_freshness_p95_seconds: int = Field(ge=1)
    finalized_freshness_p95_seconds: int = Field(ge=1)
    minimum_eligible_window_success_fraction: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_service_level(self) -> Self:
        timeframe_seconds = int(self.timeframe.duration.total_seconds())
        if self.polling_interval_seconds >= timeframe_seconds:
            raise ValueError("polling interval must be shorter than its candle timeframe")
        if self.provisional_freshness_p95_seconds < self.polling_interval_seconds:
            raise ValueError("provisional freshness cannot be tighter than polling cadence")
        minimum_finalization = (
            self.polling_interval_seconds + self.allowed_lateness_seconds
        )
        if self.finalized_freshness_p95_seconds < minimum_finalization:
            raise ValueError("finalized freshness must include polling and lateness budgets")
        return self


class ProviderRequestBudget(BaseModel):
    """Application-owned request cap; never a claim about provider guarantees."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(min_length=1, max_length=50)
    sustained_requests_per_minute: int = Field(ge=1)
    burst_requests: int = Field(ge=1)
    maximum_concurrent_requests: int = Field(ge=1)
    request_timeout_seconds: int = Field(ge=1, le=30)
    maximum_attempts: int = Field(ge=1, le=3)
    maximum_retry_after_seconds: int = Field(ge=0, le=30)
    http_latency_p95_seconds: Decimal = Field(gt=0)
    maximum_failure_fraction: Decimal = Field(ge=0, le=1)
    minimum_probe_samples: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_request_budget(self) -> Self:
        if self.burst_requests > self.sustained_requests_per_minute:
            raise ValueError("provider burst cannot exceed the sustained minute budget")
        if self.maximum_concurrent_requests > self.burst_requests:
            raise ValueError("provider concurrency cannot exceed the burst budget")
        return self


class MarketDataRetentionPolicy(BaseModel):
    """Deletion eligibility for v0.3 market-data records."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_observation_days: int = Field(ge=1)
    normalized_event_days: int = Field(ge=1)
    inbox_deduplication_days: int = Field(ge=1)
    delivered_outbox_days: int = Field(ge=1)
    failed_outbox_days: int = Field(ge=1)
    provisional_window_days_after_finalization: int = Field(ge=1)
    finalized_window_days: int | None = Field(default=None, ge=1)
    revision_evidence_days: int = Field(ge=1)
    benchmark_evidence_days: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_retention_order(self) -> Self:
        if self.normalized_event_days < self.raw_observation_days:
            raise ValueError("normalized events cannot expire before raw observations")
        if self.inbox_deduplication_days < self.normalized_event_days:
            raise ValueError("inbox deduplication must outlive normalized events")
        if self.failed_outbox_days < self.delivered_outbox_days:
            raise ValueError("failed outbox evidence must outlive delivered messages")
        if self.revision_evidence_days < self.inbox_deduplication_days:
            raise ValueError("revision evidence must outlive the deduplication horizon")
        return self


class MarketDataCapacityBudget(BaseModel):
    """Initial operating targets evaluated against reference evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_processing_latency_p95_milliseconds: Decimal = Field(gt=0)
    event_processing_throughput_per_second: Decimal = Field(gt=0)
    database_query_latency_p95_milliseconds: Decimal = Field(gt=0)
    database_pool_utilization_p95_fraction: Decimal = Field(gt=0, le=1)
    job_queue_wait_p95_seconds: Decimal = Field(gt=0)
    job_runtime_p95_seconds: dict[str, Decimal] = Field(min_length=1)
    queue_depth_warning: int = Field(ge=1)
    queue_depth_overload: int = Field(ge=1)
    worker_concurrency: int = Field(ge=1)
    maximum_storage_growth_bytes_per_30_days: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_capacity_budget(self) -> Self:
        if any(not kind.strip() for kind in self.job_runtime_p95_seconds):
            raise ValueError("job runtime budget kind cannot be empty")
        if any(runtime <= 0 for runtime in self.job_runtime_p95_seconds.values()):
            raise ValueError("job runtime budgets must be positive")
        if self.queue_depth_overload <= self.queue_depth_warning:
            raise ValueError("queue overload threshold must exceed the warning threshold")
        return self


class CapacityEvidence(BaseModel):
    """Sanitized measurements for one independent benchmark scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: CapacityEvidenceScope
    method: CapacityEvidenceMethod
    complete: bool
    observed_count: int = Field(ge=0)
    metrics: dict[str, Decimal] = Field(default_factory=dict)
    evidence_reference: str | None = Field(default=None, min_length=1, max_length=200)
    limitation: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.method is CapacityEvidenceMethod.UNAVAILABLE:
            if (
                self.complete
                or self.observed_count != 0
                or self.metrics
                or self.limitation is None
            ):
                raise ValueError("unavailable evidence requires only a limitation")
        elif self.observed_count < 1 or not self.metrics:
            raise ValueError("measured evidence requires observations and metrics")
        elif not self.complete and self.limitation is None:
            raise ValueError("incomplete measured evidence requires a limitation")
        if any(value < 0 for value in self.metrics.values()):
            raise ValueError("capacity evidence metrics cannot be negative")
        return self


class CapacityBenchmarkReport(BaseModel):
    """Machine-readable evidence gate for the P0-04 capacity freeze."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-capacity-benchmark-v1"] = (
        "market-data-capacity-benchmark-v1"
    )
    environment_label: str = Field(min_length=1, max_length=64)
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    generated_at: datetime
    python_version: str = Field(min_length=1, max_length=50)
    platform: str = Field(min_length=1, max_length=200)
    evidence: tuple[CapacityEvidence, ...] = Field(min_length=1)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("benchmark timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_scope_uniqueness(self) -> Self:
        scopes = [item.scope for item in self.evidence]
        if len(scopes) != len(set(scopes)):
            raise ValueError("capacity report cannot contain duplicate evidence scopes")
        return self

    @property
    def missing_scopes(self) -> tuple[CapacityEvidenceScope, ...]:
        measured = {
            item.scope
            for item in self.evidence
            if item.method is not CapacityEvidenceMethod.UNAVAILABLE and item.complete
        }
        return tuple(scope for scope in CapacityEvidenceScope if scope not in measured)

    @property
    def ready_to_freeze(self) -> bool:
        return not self.missing_scopes


class MarketDataServiceLevelPolicy(BaseModel):
    """Versioned P0-04 policy independent of runtime configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-service-level-policy-v1"] = (
        "market-data-service-level-policy-v1"
    )
    timeframes: tuple[TimeframeServiceLevel, ...] = Field(min_length=1)
    providers: tuple[ProviderRequestBudget, ...] = Field(min_length=1)
    retention: MarketDataRetentionPolicy
    capacity: MarketDataCapacityBudget

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        timeframes = [item.timeframe for item in self.timeframes]
        if len(timeframes) != len(set(timeframes)):
            raise ValueError("service-level policy cannot repeat timeframes")
        provider_ids = [item.provider_id for item in self.providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("service-level policy cannot repeat providers")
        return self

    def for_timeframe(self, timeframe: Timeframe) -> TimeframeServiceLevel:
        try:
            return next(item for item in self.timeframes if item.timeframe is timeframe)
        except StopIteration as exc:
            raise ValueError(f"timeframe has no service-level policy: {timeframe.value}") from exc

    def for_provider(self, provider_id: str) -> ProviderRequestBudget:
        normalized = provider_id.strip()
        try:
            return next(item for item in self.providers if item.provider_id == normalized)
        except StopIteration as exc:
            raise ValueError(f"provider has no request budget: {normalized}") from exc


def default_market_data_service_level_policy() -> MarketDataServiceLevelPolicy:
    """Return the conservative single-user v0.3 operating policy."""

    timeframe_values = (
        (Timeframe.MINUTES_15, 60, 180, 120, 300),
        (Timeframe.HOUR_1, 120, 300, 300, 600),
        (Timeframe.HOURS_4, 300, 900, 600, 1_800),
        (Timeframe.DAY_1, 600, 1_800, 1_200, 3_600),
    )
    timeframes = tuple(
        TimeframeServiceLevel(
            timeframe=timeframe,
            polling_interval_seconds=polling,
            allowed_lateness_seconds=lateness,
            maximum_future_clock_skew_seconds=30,
            provisional_freshness_p95_seconds=provisional,
            finalized_freshness_p95_seconds=finalized,
            minimum_eligible_window_success_fraction=Decimal("0.99"),
        )
        for timeframe, polling, lateness, provisional, finalized in timeframe_values
    )

    providers = tuple(
        ProviderRequestBudget(
            provider_id=provider_id,
            sustained_requests_per_minute=10,
            burst_requests=3,
            maximum_concurrent_requests=2,
            request_timeout_seconds=10,
            maximum_attempts=3,
            maximum_retry_after_seconds=30,
            http_latency_p95_seconds=Decimal("3"),
            maximum_failure_fraction=Decimal("0.01"),
            minimum_probe_samples=30,
        )
        for provider_id in (
            "binance-public",
            "kraken-public",
            "nobitex-public",
        )
    )

    return MarketDataServiceLevelPolicy(
        timeframes=timeframes,
        providers=providers,
        retention=MarketDataRetentionPolicy(
            raw_observation_days=30,
            normalized_event_days=90,
            inbox_deduplication_days=180,
            delivered_outbox_days=7,
            failed_outbox_days=30,
            provisional_window_days_after_finalization=30,
            finalized_window_days=None,
            revision_evidence_days=365,
            benchmark_evidence_days=365,
        ),
        capacity=MarketDataCapacityBudget(
            event_processing_latency_p95_milliseconds=Decimal("10"),
            event_processing_throughput_per_second=Decimal("1000"),
            database_query_latency_p95_milliseconds=Decimal("250"),
            database_pool_utilization_p95_fraction=Decimal("0.80"),
            job_queue_wait_p95_seconds=Decimal("10"),
            job_runtime_p95_seconds={
                "dataset_file_import": Decimal("120"),
                "experiment_execution": Decimal("60"),
                "market_data_import": Decimal("120"),
                "optimization_execution": Decimal("600"),
                "walk_forward_execution": Decimal("300"),
            },
            queue_depth_warning=25,
            queue_depth_overload=100,
            worker_concurrency=1,
            maximum_storage_growth_bytes_per_30_days=5 * 1024 * 1024 * 1024,
        ),
    )
