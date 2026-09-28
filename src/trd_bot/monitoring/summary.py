from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from trd_bot.jobs import (
    BackgroundJob,
    BackgroundJobKind,
    BackgroundJobRepository,
    BackgroundJobStatus,
)
from trd_bot.market_data import (
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionRepository,
    MarketDataConnectionState,
)
from trd_bot.market_data.import_history import (
    MarketDataImportRepository,
    MarketDataImportStatus,
)
from trd_bot.monitoring.models import (
    ArchitectureRecommendation,
    RecommendationSeverity,
    RecommendationStatus,
    SystemMetricName,
    SystemMetricSample,
    normalize_timestamp,
)
from trd_bot.monitoring.repositories import (
    ArchitectureRecommendationRepository,
    MetricSampleQuery,
    RecommendationQuery,
    SystemMetricRepository,
)
from trd_bot.monitoring.runtime_state import MonitoringRuntimeStateRepository


class MonitoringOverallStatus(StrEnum):
    """Dashboard-level capacity status."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class OperationalFailureReason(BaseModel):
    """A safe aggregated error code from recent persisted work."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    error_code: str = Field(min_length=1, max_length=100)
    count: int = Field(ge=1)


class OperationalJobSummary(BaseModel):
    """Recent job state without payload, worker identity, or error text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    kind: BackgroundJobKind
    status: BackgroundJobStatus
    progress_percent: int = Field(ge=0, le=100)
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    run_after: datetime
    lease_expires_at: datetime | None
    cancel_requested: bool
    result_reference: str | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_job(cls, job: BackgroundJob) -> "OperationalJobSummary":
        return cls.model_validate(
            job.model_dump(
                exclude={
                    "payload_version",
                    "payload",
                    "idempotency_key",
                    "lease_owner",
                    "error_message",
                }
            )
        )


class ConnectionHealthSummary(BaseModel):
    """Current health state of configured read-only providers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_count: int = Field(ge=0)
    enabled_count: int = Field(ge=0)
    healthy_count: int = Field(ge=0)
    unhealthy_count: int = Field(ge=0)
    untested_count: int = Field(ge=0)
    latest_tested_at: datetime | None = None
    latest_error_at: datetime | None = None
    latest_error_code: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("latest_tested_at", "latest_error_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)


class ImportOperationsSummary(BaseModel):
    """Bounded recent import reliability evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_size: int = Field(ge=0, le=100)
    succeeded_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    failure_rate: Decimal | None = Field(default=None, ge=0, le=1)
    latest_success_at: datetime | None = None
    latest_failure_at: datetime | None = None
    latest_failure_code: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("latest_success_at", "latest_failure_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)


class JobQueueSummary(BaseModel):
    """Durable queue depth, recovery signals, and recent outcomes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_count: int = Field(ge=0)
    queued_count: int = Field(ge=0)
    running_count: int = Field(ge=0)
    stuck_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    cancelled_count: int = Field(ge=0)
    recent_terminal_sample_size: int = Field(ge=0, le=100)
    average_duration_seconds: Decimal | None = Field(default=None, ge=0)
    latest_success_at: datetime | None = None
    latest_failure_at: datetime | None = None
    failure_reasons: tuple[OperationalFailureReason, ...] = ()
    recent_jobs: tuple[OperationalJobSummary, ...] = ()

    @field_validator("latest_success_at", "latest_failure_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)


class OperationalMonitoringSummary(BaseModel):
    """Read-only operational evidence derived from persisted state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary_version: Literal["operational-monitoring-v1"] = "operational-monitoring-v1"
    generated_at: datetime
    connections: ConnectionHealthSummary
    imports: ImportOperationsSummary
    jobs: JobQueueSummary

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)


class MonitoringSummary(BaseModel):
    """Dashboard-ready monitoring overview."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    generated_at: datetime
    last_checked_at: datetime | None = None
    overall_status: MonitoringOverallStatus

    metric_sample_count: int = Field(ge=0)

    latest_metrics: tuple[
        SystemMetricSample,
        ...,
    ]

    active_recommendation_count: int = Field(ge=0)

    warning_count: int = Field(ge=0)
    critical_count: int = Field(ge=0)

    active_recommendations: tuple[
        ArchitectureRecommendation,
        ...,
    ]

    operations: OperationalMonitoringSummary | None = None

    interpretation: str = "capacity_planning_only"

    @field_validator(
        "generated_at",
        "last_checked_at",
    )
    @classmethod
    def generated_at_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        return normalize_timestamp(value)


class MonitoringSummaryBuilder:
    """Build a monitoring summary from repositories."""

    def build(
        self,
        *,
        metrics: SystemMetricRepository,
        recommendations: (ArchitectureRecommendationRepository),
        runtime_state: MonitoringRuntimeStateRepository | None = None,
        jobs: BackgroundJobRepository | None = None,
        connections: MarketDataConnectionRepository | None = None,
        imports: MarketDataImportRepository | None = None,
        generated_at: datetime | None = None,
    ) -> MonitoringSummary:
        summary_generated_at = generated_at or datetime.now(UTC)
        active_query = RecommendationQuery(
            status=RecommendationStatus.ACTIVE,
        )

        active_count = recommendations.count_matching(active_query)

        active_recommendations = recommendations.search_page(
            query=active_query,
            limit=max(
                1,
                min(active_count, 100),
            ),
            offset=0,
        )

        latest_metrics = tuple(
            sample
            for metric_name in SystemMetricName
            if (sample := metrics.latest(metric_name=metric_name)) is not None
        )

        warning_count = sum(
            recommendation.severity is RecommendationSeverity.WARNING
            for recommendation in active_recommendations
        )

        critical_count = sum(
            recommendation.severity is RecommendationSeverity.CRITICAL
            for recommendation in active_recommendations
        )

        operations = (
            self._build_operations(
                jobs=jobs,
                connections=connections,
                imports=imports,
                generated_at=summary_generated_at,
            )
            if jobs is not None and connections is not None and imports is not None
            else None
        )

        if critical_count > 0 or (operations is not None and operations.jobs.stuck_count > 0):
            overall_status = MonitoringOverallStatus.CRITICAL
        elif warning_count > 0 or (
            operations is not None
            and (
                operations.connections.unhealthy_count > 0
                or operations.jobs.failed_count > 0
                or operations.imports.failed_count > 0
            )
        ):
            overall_status = MonitoringOverallStatus.WARNING
        else:
            overall_status = MonitoringOverallStatus.HEALTHY

        state = runtime_state.get() if runtime_state is not None else None

        return MonitoringSummary(
            generated_at=summary_generated_at,
            last_checked_at=(state.last_checked_at if state is not None else None),
            overall_status=overall_status,
            metric_sample_count=(metrics.count_matching(MetricSampleQuery())),
            latest_metrics=latest_metrics,
            active_recommendation_count=(active_count),
            warning_count=warning_count,
            critical_count=critical_count,
            active_recommendations=(active_recommendations),
            operations=operations,
        )

    @staticmethod
    def _build_operations(
        *,
        jobs: BackgroundJobRepository,
        connections: MarketDataConnectionRepository,
        imports: MarketDataImportRepository,
        generated_at: datetime,
    ) -> OperationalMonitoringSummary:
        connection_items = MonitoringSummaryBuilder._all_connections(connections)
        tested = tuple(item for item in connection_items if item.last_tested_at is not None)
        unhealthy = tuple(
            item for item in tested if item.health_status is MarketDataConnectionHealth.UNHEALTHY
        )
        latest_tested = max(
            tested, key=lambda item: item.last_tested_at or item.created_at, default=None
        )
        latest_error = max(
            unhealthy,
            key=lambda item: item.last_tested_at or item.created_at,
            default=None,
        )

        recent_imports = imports.list_page(limit=100, offset=0)
        succeeded_imports = tuple(
            item for item in recent_imports if item.status is MarketDataImportStatus.SUCCEEDED
        )
        failed_imports = tuple(
            item for item in recent_imports if item.status is MarketDataImportStatus.FAILED
        )
        latest_import_success = max(
            succeeded_imports,
            key=lambda item: item.completed_at,
            default=None,
        )
        latest_import_failure = max(
            failed_imports,
            key=lambda item: item.completed_at,
            default=None,
        )

        counts = {status: jobs.count(statuses=(status,)) for status in BackgroundJobStatus}
        running_jobs = MonitoringSummaryBuilder._all_jobs(
            jobs,
            statuses=(BackgroundJobStatus.RUNNING,),
        )
        stuck_count = sum(
            item.lease_expires_at is not None and item.lease_expires_at <= generated_at
            for item in running_jobs
        )
        terminal_statuses = (
            BackgroundJobStatus.SUCCEEDED,
            BackgroundJobStatus.FAILED,
            BackgroundJobStatus.CANCELLED,
        )
        recent_terminal = jobs.list_page(
            limit=100,
            offset=0,
            statuses=terminal_statuses,
        )
        recent_jobs = jobs.list_page(limit=10, offset=0)
        durations = tuple(
            Decimal(str((item.finished_at - item.started_at).total_seconds()))
            for item in recent_terminal
            if item.started_at is not None
            and item.finished_at is not None
            and item.finished_at >= item.started_at
        )
        failures = tuple(
            item
            for item in recent_terminal
            if item.status is BackgroundJobStatus.FAILED and item.error_code is not None
        )
        failure_counts = Counter(
            item.error_code for item in failures if item.error_code is not None
        )
        failure_reasons = tuple(
            OperationalFailureReason(error_code=code, count=count)
            for code, count in sorted(
                failure_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        )
        successful_jobs = tuple(
            item for item in recent_terminal if item.status is BackgroundJobStatus.SUCCEEDED
        )
        failed_jobs = tuple(
            item for item in recent_terminal if item.status is BackgroundJobStatus.FAILED
        )

        return OperationalMonitoringSummary(
            generated_at=generated_at,
            connections=ConnectionHealthSummary(
                total_count=len(connection_items),
                enabled_count=sum(
                    item.state is MarketDataConnectionState.ENABLED for item in connection_items
                ),
                healthy_count=sum(
                    item.health_status is MarketDataConnectionHealth.HEALTHY
                    for item in connection_items
                ),
                unhealthy_count=sum(
                    item.health_status is MarketDataConnectionHealth.UNHEALTHY
                    for item in connection_items
                ),
                untested_count=sum(
                    item.health_status is MarketDataConnectionHealth.UNTESTED
                    for item in connection_items
                ),
                latest_tested_at=(
                    latest_tested.last_tested_at if latest_tested is not None else None
                ),
                latest_error_at=(latest_error.last_tested_at if latest_error is not None else None),
                latest_error_code=(
                    latest_error.last_error_code.value
                    if latest_error is not None and latest_error.last_error_code is not None
                    else None
                ),
            ),
            imports=ImportOperationsSummary(
                sample_size=len(recent_imports),
                succeeded_count=len(succeeded_imports),
                failed_count=len(failed_imports),
                failure_rate=(
                    Decimal(len(failed_imports)) / Decimal(len(recent_imports))
                    if recent_imports
                    else None
                ),
                latest_success_at=(
                    latest_import_success.completed_at
                    if latest_import_success is not None
                    else None
                ),
                latest_failure_at=(
                    latest_import_failure.completed_at
                    if latest_import_failure is not None
                    else None
                ),
                latest_failure_code=(
                    latest_import_failure.error_code if latest_import_failure is not None else None
                ),
            ),
            jobs=JobQueueSummary(
                total_count=sum(counts.values()),
                queued_count=counts[BackgroundJobStatus.QUEUED],
                running_count=counts[BackgroundJobStatus.RUNNING],
                stuck_count=stuck_count,
                succeeded_count=counts[BackgroundJobStatus.SUCCEEDED],
                failed_count=counts[BackgroundJobStatus.FAILED],
                cancelled_count=counts[BackgroundJobStatus.CANCELLED],
                recent_terminal_sample_size=len(recent_terminal),
                average_duration_seconds=(
                    sum(durations, start=Decimal(0)) / Decimal(len(durations))
                    if durations
                    else None
                ),
                latest_success_at=MonitoringSummaryBuilder._latest_finished_at(successful_jobs),
                latest_failure_at=MonitoringSummaryBuilder._latest_finished_at(failed_jobs),
                failure_reasons=failure_reasons,
                recent_jobs=tuple(OperationalJobSummary.from_job(item) for item in recent_jobs),
            ),
        )

    @staticmethod
    def _all_connections(
        repository: MarketDataConnectionRepository,
    ) -> tuple[MarketDataConnection, ...]:
        total = repository.count()
        items: list[MarketDataConnection] = []
        for offset in range(0, total, 100):
            items.extend(repository.list_page(limit=100, offset=offset))
        return tuple(items)

    @staticmethod
    def _all_jobs(
        repository: BackgroundJobRepository,
        *,
        statuses: tuple[BackgroundJobStatus, ...],
    ) -> tuple[BackgroundJob, ...]:
        total = repository.count(statuses=statuses)
        items: list[BackgroundJob] = []
        for offset in range(0, total, 100):
            items.extend(repository.list_page(limit=100, offset=offset, statuses=statuses))
        return tuple(items)

    @staticmethod
    def _latest_finished_at(items: tuple[BackgroundJob, ...]) -> datetime | None:
        finished = tuple(item.finished_at for item in items if item.finished_at is not None)
        return max(finished, default=None)
