from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyArchitectureRecommendationRepository,
    SqlAlchemySystemMetricRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.monitoring import (
    ArchitectureCandidate,
    ArchitectureEvidence,
    ArchitectureRecommendation,
    InMemoryArchitectureRecommendationRepository,
    InMemorySystemMetricRepository,
    MetricSampleQuery,
    RecommendationQuery,
    RecommendationSeverity,
    RecommendationStatus,
    SystemMetricName,
    SystemMetricSample,
    SystemMetricSource,
    SystemMetricUnit,
    build_architecture_recommendation_id,
    build_metric_sample_id,
)

START_TIME = datetime(
    2026,
    8,
    24,
    10,
    tzinfo=UTC,
)


def create_metric_sample(
    *,
    recorded_at: datetime,
    value: str,
) -> SystemMetricSample:
    sample_id = build_metric_sample_id(
        metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
        source=SystemMetricSource.API,
        recorded_at=recorded_at,
        window_seconds=300,
    )

    return SystemMetricSample(
        sample_id=sample_id,
        metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
        source=SystemMetricSource.API,
        unit=SystemMetricUnit.SECONDS,
        value=Decimal(value),
        recorded_at=recorded_at,
        window_seconds=300,
        observed_count=100,
        labels={
            "route": "/api/v1/research/overview",
        },
    )


def create_recommendation(
    *,
    first_detected_at: datetime,
    last_detected_at: datetime,
    severity: RecommendationSeverity,
) -> ArchitectureRecommendation:
    recommendation_id = build_architecture_recommendation_id(
        candidate=ArchitectureCandidate.REDIS,
        first_detected_at=first_detected_at,
    )

    return ArchitectureRecommendation(
        recommendation_id=recommendation_id,
        candidate=ArchitectureCandidate.REDIS,
        severity=severity,
        status=RecommendationStatus.ACTIVE,
        title="Review repeated API reads",
        summary=("Repeated API read latency remained above its configured threshold."),
        first_detected_at=first_detected_at,
        last_detected_at=last_detected_at,
        evidence=(
            ArchitectureEvidence(
                metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
                observed_value=Decimal("0.75"),
                threshold_value=Decimal("0.50"),
                comparison=("greater_than_or_equal"),
                consecutive_windows=3,
            ),
        ),
    )


def test_in_memory_metric_repository_filters_and_orders() -> None:
    repository = InMemorySystemMetricRepository()

    earlier = create_metric_sample(
        recorded_at=START_TIME,
        value="0.40",
    )

    later = create_metric_sample(
        recorded_at=(START_TIME + timedelta(minutes=5)),
        value="0.70",
    )

    repository.save(earlier)
    repository.save(later)

    page = repository.search_page(
        query=MetricSampleQuery(
            source=SystemMetricSource.API,
        ),
        limit=10,
        offset=0,
    )

    assert page == (later, earlier)
    assert repository.count_matching(MetricSampleQuery()) == 2

    assert repository.latest(metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95)) == later


def test_metric_repository_rejects_invalid_pagination() -> None:
    repository = InMemorySystemMetricRepository()

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        repository.search_page(
            query=MetricSampleQuery(),
            limit=0,
            offset=0,
        )

    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        repository.search_page(
            query=MetricSampleQuery(),
            limit=10,
            offset=-1,
        )


def test_in_memory_recommendation_repository_upserts() -> None:
    repository = InMemoryArchitectureRecommendationRepository()

    first = create_recommendation(
        first_detected_at=START_TIME,
        last_detected_at=START_TIME,
        severity=RecommendationSeverity.WARNING,
    )

    updated = create_recommendation(
        first_detected_at=START_TIME,
        last_detected_at=(START_TIME + timedelta(minutes=15)),
        severity=RecommendationSeverity.CRITICAL,
    )

    repository.upsert(first)
    repository.upsert(updated)

    assert repository.get(first.recommendation_id) == updated

    assert (
        repository.count_matching(
            RecommendationQuery(
                status=RecommendationStatus.ACTIVE,
            )
        )
        == 1
    )


def test_sqlalchemy_metric_repository_persists_samples() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    sample = create_metric_sample(
        recorded_at=START_TIME,
        value="0.45",
    )

    try:
        with factory() as session:
            repository = SqlAlchemySystemMetricRepository(session)

            assert repository.save(sample) == sample
            assert repository.save(sample) == sample

            stored = repository.get(sample.sample_id)

            assert stored == sample

            assert (
                repository.latest(
                    metric_name=sample.metric_name,
                    source=sample.source,
                )
                == sample
            )
    finally:
        engine.dispose()


def test_sqlalchemy_recommendation_repository_upserts() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    first = create_recommendation(
        first_detected_at=START_TIME,
        last_detected_at=START_TIME,
        severity=RecommendationSeverity.WARNING,
    )

    updated = create_recommendation(
        first_detected_at=START_TIME,
        last_detected_at=(START_TIME + timedelta(minutes=15)),
        severity=RecommendationSeverity.CRITICAL,
    )

    try:
        with factory() as session:
            repository = SqlAlchemyArchitectureRecommendationRepository(session)

            repository.upsert(first)
            repository.upsert(updated)

            assert repository.get(first.recommendation_id) == updated

            results = repository.search_page(
                query=RecommendationQuery(
                    severity=(RecommendationSeverity.CRITICAL),
                ),
                limit=10,
                offset=0,
            )

            assert results == (updated,)
    finally:
        engine.dispose()
