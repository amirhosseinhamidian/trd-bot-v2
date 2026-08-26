from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_architecture_recommendation_repository,
    get_monitoring_runtime_state_repository,
    get_system_metric_repository,
)
from trd_bot.main import app
from trd_bot.monitoring import (
    METRIC_UNITS,
    ArchitectureCandidate,
    ArchitectureEvidence,
    ArchitectureRecommendation,
    InMemoryArchitectureRecommendationRepository,
    InMemoryMonitoringRuntimeStateRepository,
    InMemorySystemMetricRepository,
    RecommendationSeverity,
    RecommendationStatus,
    SystemMetricName,
    SystemMetricSample,
    SystemMetricSource,
    build_architecture_recommendation_id,
    build_metric_sample_id,
)

client = TestClient(app)

START_TIME = datetime(
    2026,
    8,
    24,
    10,
    tzinfo=UTC,
)


@pytest.fixture
def repositories() -> Iterator[
    tuple[
        InMemorySystemMetricRepository,
        InMemoryArchitectureRecommendationRepository,
    ]
]:
    metric_repository = InMemorySystemMetricRepository()

    recommendation_repository = InMemoryArchitectureRecommendationRepository()
    runtime_state_repository = InMemoryMonitoringRuntimeStateRepository()

    def override_metrics() -> InMemorySystemMetricRepository:
        return metric_repository

    def override_recommendations() -> InMemoryArchitectureRecommendationRepository:
        return recommendation_repository

    app.dependency_overrides[get_system_metric_repository] = override_metrics

    app.dependency_overrides[get_architecture_recommendation_repository] = override_recommendations

    app.dependency_overrides[get_monitoring_runtime_state_repository] = lambda: (
        runtime_state_repository
    )

    try:
        yield (
            metric_repository,
            recommendation_repository,
        )
    finally:
        app.dependency_overrides.pop(
            get_system_metric_repository,
            None,
        )

        app.dependency_overrides.pop(
            get_architecture_recommendation_repository,
            None,
        )

        app.dependency_overrides.pop(
            get_monitoring_runtime_state_repository,
            None,
        )


def create_metric(
    *,
    metric_name: SystemMetricName,
    source: SystemMetricSource,
    value: str,
    recorded_at: datetime,
) -> SystemMetricSample:
    sample_id = build_metric_sample_id(
        metric_name=metric_name,
        source=source,
        recorded_at=recorded_at,
        window_seconds=300,
    )

    return SystemMetricSample(
        sample_id=sample_id,
        metric_name=metric_name,
        source=source,
        unit=METRIC_UNITS[metric_name],
        value=Decimal(value),
        recorded_at=recorded_at,
        window_seconds=300,
        observed_count=100,
        labels={
            "synthetic": "true",
        },
    )


def create_critical_recommendation() -> ArchitectureRecommendation:
    recommendation_id = build_architecture_recommendation_id(
        candidate=(ArchitectureCandidate.CLICKHOUSE),
        first_detected_at=START_TIME,
    )

    return ArchitectureRecommendation(
        recommendation_id=recommendation_id,
        candidate=ArchitectureCandidate.CLICKHOUSE,
        severity=RecommendationSeverity.CRITICAL,
        status=RecommendationStatus.ACTIVE,
        title="[DEMO] Review analytical storage",
        summary=("Synthetic analytical workload exceeded its configured thresholds."),
        first_detected_at=START_TIME,
        last_detected_at=START_TIME,
        evidence=(
            ArchitectureEvidence(
                metric_name=(SystemMetricName.ANALYTICAL_QUERY_LATENCY_P95),
                observed_value=Decimal("12"),
                threshold_value=Decimal("10"),
                comparison=("greater_than_or_equal"),
                consecutive_windows=3,
            ),
        ),
    )


def test_api_lists_filtered_metric_samples(
    repositories: tuple[
        InMemorySystemMetricRepository,
        InMemoryArchitectureRecommendationRepository,
    ],
) -> None:
    metrics, _ = repositories

    earlier = create_metric(
        metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
        source=SystemMetricSource.API,
        value="0.40",
        recorded_at=START_TIME,
    )

    later = create_metric(
        metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
        source=SystemMetricSource.API,
        value="0.70",
        recorded_at=(START_TIME + timedelta(minutes=5)),
    )

    metrics.save(earlier)
    metrics.save(later)

    response = client.get(
        "/api/v1/monitoring/metrics",
        params={
            "metric_name": ("api_request_latency_p95"),
            "limit": 1,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert data["count"] == 1
    assert data["has_next"] is True
    assert data["items"][0]["sample_id"] == (later.sample_id)


def test_api_returns_latest_metric(
    repositories: tuple[
        InMemorySystemMetricRepository,
        InMemoryArchitectureRecommendationRepository,
    ],
) -> None:
    metrics, _ = repositories

    sample = create_metric(
        metric_name=(SystemMetricName.DATABASE_QUERY_LATENCY_P95),
        source=SystemMetricSource.DATABASE,
        value="0.45",
        recorded_at=START_TIME,
    )

    metrics.save(sample)

    response = client.get(
        "/api/v1/monitoring/metrics/latest",
        params={
            "metric_name": ("database_query_latency_p95"),
            "source": "database",
        },
    )

    assert response.status_code == 200
    assert response.json()["sample_id"] == (sample.sample_id)


def test_api_returns_404_for_missing_latest_metric(
    repositories: tuple[
        InMemorySystemMetricRepository,
        InMemoryArchitectureRecommendationRepository,
    ],
) -> None:
    response = client.get(
        "/api/v1/monitoring/metrics/latest",
        params={
            "metric_name": "api_error_rate",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == ("metric sample not found")


def test_api_lists_active_recommendations(
    repositories: tuple[
        InMemorySystemMetricRepository,
        InMemoryArchitectureRecommendationRepository,
    ],
) -> None:
    _, recommendations = repositories

    recommendation = create_critical_recommendation()

    recommendations.upsert(recommendation)

    response = client.get(
        "/api/v1/monitoring/recommendations",
        params={
            "status": "active",
            "severity": "critical",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["recommendation_id"] == recommendation.recommendation_id


def test_api_builds_critical_monitoring_summary(
    repositories: tuple[
        InMemorySystemMetricRepository,
        InMemoryArchitectureRecommendationRepository,
    ],
) -> None:
    metrics, recommendations = repositories

    sample = create_metric(
        metric_name=(SystemMetricName.ANALYTICAL_QUERY_LATENCY_P95),
        source=SystemMetricSource.DATABASE,
        value="12",
        recorded_at=START_TIME,
    )

    metrics.save(sample)

    recommendations.upsert(create_critical_recommendation())

    response = client.get("/api/v1/monitoring/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["overall_status"] == "critical"
    assert data["metric_sample_count"] == 1
    assert data["active_recommendation_count"] == 1
    assert data["warning_count"] == 0
    assert data["critical_count"] == 1
    assert len(data["latest_metrics"]) == 1
    assert data["interpretation"] == "capacity_planning_only"


def test_api_acknowledges_active_recommendation(
    repositories: tuple[
        InMemorySystemMetricRepository,
        InMemoryArchitectureRecommendationRepository,
    ],
) -> None:
    _, recommendations = repositories

    recommendation = create_critical_recommendation()
    recommendations.upsert(recommendation)

    url = f"/api/v1/monitoring/recommendations/{recommendation.recommendation_id}/acknowledge"

    first_response = client.post(url)

    assert first_response.status_code == 200

    first_payload = first_response.json()

    assert first_payload["status"] == "active"
    assert first_payload["acknowledged_at"] is not None
    assert first_payload["resolved_at"] is None

    second_response = client.post(url)

    assert second_response.status_code == 200
    assert second_response.json()["acknowledged_at"] == first_payload["acknowledged_at"]


def test_api_resolves_recommendation_idempotently(
    repositories: tuple[
        InMemorySystemMetricRepository,
        InMemoryArchitectureRecommendationRepository,
    ],
) -> None:
    _, recommendations = repositories

    recommendation = create_critical_recommendation()
    recommendations.upsert(recommendation)

    url = f"/api/v1/monitoring/recommendations/{recommendation.recommendation_id}/resolve"

    first_response = client.post(url)

    assert first_response.status_code == 200

    first_payload = first_response.json()

    assert first_payload["status"] == "resolved"
    assert first_payload["resolved_at"] is not None

    second_response = client.post(url)

    assert second_response.status_code == 200
    assert second_response.json()["resolved_at"] == first_payload["resolved_at"]


def test_api_returns_404_for_unknown_recommendation_action() -> None:
    response = client.post(
        "/api/v1/monitoring/recommendations/recommendation-0000000000000000/acknowledge"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == ("architecture recommendation not found")
