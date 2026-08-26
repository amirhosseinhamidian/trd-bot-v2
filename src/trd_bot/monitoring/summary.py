from datetime import UTC, datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
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
        generated_at: datetime | None = None,
    ) -> MonitoringSummary:
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

        if critical_count > 0:
            overall_status = MonitoringOverallStatus.CRITICAL
        elif warning_count > 0:
            overall_status = MonitoringOverallStatus.WARNING
        else:
            overall_status = MonitoringOverallStatus.HEALTHY

        state = runtime_state.get() if runtime_state is not None else None

        return MonitoringSummary(
            generated_at=(generated_at or datetime.now(UTC)),
            last_checked_at=(state.last_checked_at if state is not None else None),
            overall_status=overall_status,
            metric_sample_count=(metrics.count_matching(MetricSampleQuery())),
            latest_metrics=latest_metrics,
            active_recommendation_count=(active_count),
            warning_count=warning_count,
            critical_count=critical_count,
            active_recommendations=(active_recommendations),
        )
