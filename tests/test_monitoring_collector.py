from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from trd_bot.monitoring import (
    AggregatedMetricObservation,
    ArchitectureCandidate,
    ArchitectureCheckpointPolicy,
    CheckpointOutcome,
    InMemoryArchitectureRecommendationRepository,
    InMemorySystemMetricRepository,
    MetricSampleQuery,
    MetricThresholdRule,
    MonitoringCollector,
    RecommendationQuery,
    SystemMetricName,
    SystemMetricSource,
)

START_TIME = datetime(2026, 8, 26, 10, tzinfo=UTC)


def create_collector() -> tuple[
    MonitoringCollector,
    InMemorySystemMetricRepository,
    InMemoryArchitectureRecommendationRepository,
]:
    metrics = InMemorySystemMetricRepository()
    recommendations = InMemoryArchitectureRecommendationRepository()
    policy = ArchitectureCheckpointPolicy(
        candidate=ArchitectureCandidate.POSTGRESQL_TUNING,
        title="Review API error capacity",
        summary="The API error rate remained above the configured threshold.",
        rules=(
            MetricThresholdRule(
                metric_name=SystemMetricName.API_ERROR_RATE,
                source=SystemMetricSource.API,
                warning_threshold=Decimal("0.05"),
                critical_threshold=Decimal("0.10"),
                minimum_consecutive_windows=3,
            ),
        ),
    )

    return (
        MonitoringCollector(
            metric_repository=metrics,
            recommendation_repository=recommendations,
            policies=(policy,),
        ),
        metrics,
        recommendations,
    )


def observation(value: str = "0.06") -> AggregatedMetricObservation:
    return AggregatedMetricObservation(
        metric_name=SystemMetricName.API_ERROR_RATE,
        source=SystemMetricSource.API,
        value=Decimal(value),
        observed_count=100,
        labels={"environment": "test"},
    )


def test_collector_persists_samples_and_evaluates_sustained_windows() -> None:
    collector, metrics, recommendations = create_collector()

    results = tuple(
        collector.collect(
            observations=(observation(),),
            checked_at=START_TIME + timedelta(minutes=index * 5),
        )
        for index in range(3)
    )

    assert [result.checkpoints[0].outcome for result in results] == [
        CheckpointOutcome.INSUFFICIENT_DATA,
        CheckpointOutcome.INSUFFICIENT_DATA,
        CheckpointOutcome.WARNING,
    ]
    assert metrics.count_matching(MetricSampleQuery()) == 3
    assert results[-1].checkpoints[0].recommendation is not None
    assert recommendations.count_matching(RecommendationQuery()) == 1


def test_collector_is_idempotent_for_the_same_window() -> None:
    collector, metrics, _ = create_collector()

    first = collector.collect(
        observations=(observation(),),
        checked_at=START_TIME,
    )
    second = collector.collect(
        observations=(observation(),),
        checked_at=START_TIME,
    )

    assert first.samples == second.samples
    assert metrics.count_matching(MetricSampleQuery()) == 1


def test_collector_normalizes_the_last_check_time_to_utc() -> None:
    collector, _, _ = create_collector()
    local_time = START_TIME.astimezone(timezone(timedelta(hours=3, minutes=30)))

    result = collector.collect(
        observations=(observation(),),
        checked_at=local_time,
    )

    assert result.checked_at == START_TIME
    assert result.checked_at.tzinfo is UTC


def test_collector_rejects_duplicate_metric_sources() -> None:
    collector, _, _ = create_collector()

    with pytest.raises(ValueError, match="unique by metric name and source"):
        collector.collect(
            observations=(observation(), observation("0.07")),
            checked_at=START_TIME,
        )


def test_collector_rejects_invalid_window_size() -> None:
    collector, _, _ = create_collector()

    with pytest.raises(ValueError, match="greater than zero"):
        collector.collect(
            observations=(observation(),),
            checked_at=START_TIME,
            window_seconds=0,
        )
