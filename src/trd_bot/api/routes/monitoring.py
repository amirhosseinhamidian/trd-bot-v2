from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import Field

from trd_bot.api.dependencies import (
    get_architecture_recommendation_repository,
    get_monitoring_runtime_state_repository,
    get_system_metric_repository,
)
from trd_bot.api.pagination import (
    Page,
    PaginationParams,
    build_page,
)
from trd_bot.monitoring import (
    ArchitectureRecommendation,
    ArchitectureRecommendationRepository,
    MetricSampleQuery,
    MonitoringRuntimeStateRepository,
    MonitoringSummary,
    MonitoringSummaryBuilder,
    RecommendationQuery,
    SystemMetricName,
    SystemMetricRepository,
    SystemMetricSample,
    SystemMetricSource,
)

router = APIRouter(
    prefix="/monitoring",
    tags=["Monitoring"],
)

MetricRepositoryDependency = Annotated[
    SystemMetricRepository,
    Depends(get_system_metric_repository),
]

RecommendationRepositoryDependency = Annotated[
    ArchitectureRecommendationRepository,
    Depends(get_architecture_recommendation_repository),
]

RuntimeStateRepositoryDependency = Annotated[
    MonitoringRuntimeStateRepository,
    Depends(get_monitoring_runtime_state_repository),
]


class MetricCatalogParams(MetricSampleQuery):
    """Metric filters with pagination."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )

    def catalog_query(
        self,
    ) -> MetricSampleQuery:
        return MetricSampleQuery.model_validate(
            self.model_dump(
                exclude={
                    "limit",
                    "offset",
                }
            )
        )


class RecommendationCatalogParams(RecommendationQuery):
    """Recommendation filters with pagination."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )

    def catalog_query(
        self,
    ) -> RecommendationQuery:
        return RecommendationQuery.model_validate(
            self.model_dump(
                exclude={
                    "limit",
                    "offset",
                }
            )
        )


class LatestMetricParams(MetricSampleQuery):
    """Required identity for a latest metric query."""

    metric_name: SystemMetricName
    source: SystemMetricSource | None = None


MetricCatalogParamsQuery = Annotated[
    MetricCatalogParams,
    Query(),
]

RecommendationCatalogParamsQuery = Annotated[
    RecommendationCatalogParams,
    Query(),
]

LatestMetricParamsQuery = Annotated[
    LatestMetricParams,
    Query(),
]


@router.get(
    "/metrics",
    response_model=Page[SystemMetricSample],
)
def list_metric_samples(
    repository: MetricRepositoryDependency,
    params: MetricCatalogParamsQuery,
) -> Page[SystemMetricSample]:
    """List filtered aggregated metric snapshots."""

    query = params.catalog_query()

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )

    items = repository.search_page(
        query=query,
        limit=params.limit,
        offset=params.offset,
    )

    return build_page(
        items,
        total=repository.count_matching(query),
        pagination=pagination,
    )


@router.get(
    "/metrics/latest",
    response_model=SystemMetricSample,
)
def get_latest_metric_sample(
    repository: MetricRepositoryDependency,
    params: LatestMetricParamsQuery,
) -> SystemMetricSample:
    """Return the latest matching metric snapshot."""

    sample = repository.latest(
        metric_name=params.metric_name,
        source=params.source,
    )

    if sample is None:
        raise HTTPException(
            status_code=404,
            detail="metric sample not found",
        )

    return sample


@router.get(
    "/recommendations",
    response_model=(Page[ArchitectureRecommendation]),
)
def list_architecture_recommendations(
    repository: (RecommendationRepositoryDependency),
    params: RecommendationCatalogParamsQuery,
) -> Page[ArchitectureRecommendation]:
    """List evidence-backed capacity recommendations."""

    query = params.catalog_query()

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )

    items = repository.search_page(
        query=query,
        limit=params.limit,
        offset=params.offset,
    )

    return build_page(
        items,
        total=repository.count_matching(query),
        pagination=pagination,
    )


@router.post(
    "/recommendations/{recommendation_id}/acknowledge",
    response_model=ArchitectureRecommendation,
)
def acknowledge_architecture_recommendation(
    recommendation_id: str,
    repository: RecommendationRepositoryDependency,
) -> ArchitectureRecommendation:
    """Mark one active recommendation as acknowledged."""

    recommendation = repository.get(recommendation_id)

    if recommendation is None:
        raise HTTPException(
            status_code=404,
            detail="architecture recommendation not found",
        )

    try:
        updated = recommendation.acknowledge(
            acknowledged_at=datetime.now(UTC),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    return repository.upsert(updated)


@router.post(
    "/recommendations/{recommendation_id}/resolve",
    response_model=ArchitectureRecommendation,
)
def resolve_architecture_recommendation(
    recommendation_id: str,
    repository: RecommendationRepositoryDependency,
) -> ArchitectureRecommendation:
    """Resolve one active architecture recommendation."""

    recommendation = repository.get(recommendation_id)

    if recommendation is None:
        raise HTTPException(
            status_code=404,
            detail="architecture recommendation not found",
        )

    try:
        updated = recommendation.resolve(
            resolved_at=datetime.now(UTC),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    return repository.upsert(updated)


@router.get(
    "/summary",
    response_model=MonitoringSummary,
)
def get_monitoring_summary(
    metrics: MetricRepositoryDependency,
    recommendations: (RecommendationRepositoryDependency),
    runtime_state: RuntimeStateRepositoryDependency,
) -> MonitoringSummary:
    """Return a dashboard-ready capacity summary."""

    return MonitoringSummaryBuilder().build(
        metrics=metrics,
        recommendations=recommendations,
        runtime_state=runtime_state,
    )
