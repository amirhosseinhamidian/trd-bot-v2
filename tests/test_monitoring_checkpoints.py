from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trd_bot.monitoring import (
    METRIC_UNITS,
    ArchitectureCandidate,
    ArchitectureCheckpointEvaluator,
    ArchitectureCheckpointPolicy,
    CheckpointOutcome,
    InMemoryArchitectureRecommendationRepository,
    InMemorySystemMetricRepository,
    RecommendationStatus,
    SystemMetricName,
    SystemMetricSample,
    SystemMetricSource,
    build_metric_sample_id,
    default_checkpoint_policies,
)

START_TIME = datetime(
    2026,
    8,
    24,
    10,
    tzinfo=UTC,
)


def get_policy(
    candidate: ArchitectureCandidate,
) -> ArchitectureCheckpointPolicy:
    return next(policy for policy in default_checkpoint_policies() if policy.candidate is candidate)


def save_sample(
    repository: InMemorySystemMetricRepository,
    *,
    metric_name: SystemMetricName,
    source: SystemMetricSource,
    value: str,
    recorded_at: datetime,
) -> None:
    sample_id = build_metric_sample_id(
        metric_name=metric_name,
        source=source,
        recorded_at=recorded_at,
        window_seconds=300,
    )

    repository.save(
        SystemMetricSample(
            sample_id=sample_id,
            metric_name=metric_name,
            source=source,
            unit=METRIC_UNITS[metric_name],
            value=Decimal(value),
            recorded_at=recorded_at,
            window_seconds=300,
            observed_count=100,
        )
    )


def save_redis_windows(
    repository: InMemorySystemMetricRepository,
    *,
    latency: str,
    repeated_reads: str,
    start_time: datetime = START_TIME,
) -> None:
    for index in range(3):
        recorded_at = start_time + timedelta(minutes=index * 5)

        save_sample(
            repository,
            metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
            source=SystemMetricSource.API,
            value=latency,
            recorded_at=recorded_at,
        )

        save_sample(
            repository,
            metric_name=(SystemMetricName.API_REPEATED_READ_RATIO),
            source=SystemMetricSource.API,
            value=repeated_reads,
            recorded_at=recorded_at,
        )


def test_checkpoint_requires_all_metrics() -> None:
    metrics = InMemorySystemMetricRepository()
    recommendations = InMemoryArchitectureRecommendationRepository()

    for index in range(3):
        save_sample(
            metrics,
            metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
            source=SystemMetricSource.API,
            value="0.8",
            recorded_at=(START_TIME + timedelta(minutes=index * 5)),
        )

    result = ArchitectureCheckpointEvaluator(
        metric_repository=metrics,
        recommendation_repository=recommendations,
    ).evaluate(
        policy=get_policy(ArchitectureCandidate.REDIS),
        evaluated_at=(START_TIME + timedelta(minutes=15)),
    )

    assert result.outcome is CheckpointOutcome.INSUFFICIENT_DATA
    assert result.recommendation is None


def test_checkpoint_ignores_transient_spike() -> None:
    metrics = InMemorySystemMetricRepository()
    recommendations = InMemoryArchitectureRecommendationRepository()

    save_redis_windows(
        metrics,
        latency="0.20",
        repeated_reads="0.20",
    )

    save_sample(
        metrics,
        metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
        source=SystemMetricSource.API,
        value="2.0",
        recorded_at=(START_TIME + timedelta(minutes=15)),
    )

    result = ArchitectureCheckpointEvaluator(
        metric_repository=metrics,
        recommendation_repository=recommendations,
    ).evaluate(
        policy=get_policy(ArchitectureCandidate.REDIS),
        evaluated_at=(START_TIME + timedelta(minutes=20)),
    )

    assert result.outcome is CheckpointOutcome.HEALTHY
    assert result.recommendation is None


def test_checkpoint_creates_warning_after_sustained_values() -> None:
    metrics = InMemorySystemMetricRepository()
    recommendations = InMemoryArchitectureRecommendationRepository()

    save_redis_windows(
        metrics,
        latency="0.75",
        repeated_reads="0.70",
    )

    result = ArchitectureCheckpointEvaluator(
        metric_repository=metrics,
        recommendation_repository=recommendations,
    ).evaluate(
        policy=get_policy(ArchitectureCandidate.REDIS),
        evaluated_at=(START_TIME + timedelta(minutes=15)),
    )

    assert result.outcome is CheckpointOutcome.WARNING
    assert result.recommendation is not None
    assert result.recommendation.status is (RecommendationStatus.ACTIVE)
    assert len(result.evidence) == 2


def test_checkpoint_creates_critical_recommendation() -> None:
    metrics = InMemorySystemMetricRepository()
    recommendations = InMemoryArchitectureRecommendationRepository()

    save_redis_windows(
        metrics,
        latency="2.0",
        repeated_reads="0.90",
    )

    result = ArchitectureCheckpointEvaluator(
        metric_repository=metrics,
        recommendation_repository=recommendations,
    ).evaluate(
        policy=get_policy(ArchitectureCandidate.REDIS),
        evaluated_at=(START_TIME + timedelta(minutes=15)),
    )

    assert result.outcome is CheckpointOutcome.CRITICAL
    assert result.recommendation is not None


def test_checkpoint_resolves_recovered_recommendation() -> None:
    metrics = InMemorySystemMetricRepository()
    recommendations = InMemoryArchitectureRecommendationRepository()

    evaluator = ArchitectureCheckpointEvaluator(
        metric_repository=metrics,
        recommendation_repository=recommendations,
    )

    policy = get_policy(ArchitectureCandidate.REDIS)

    save_redis_windows(
        metrics,
        latency="0.75",
        repeated_reads="0.70",
    )

    warning_result = evaluator.evaluate(
        policy=policy,
        evaluated_at=(START_TIME + timedelta(minutes=15)),
    )

    assert warning_result.recommendation is not None

    recovery_start = START_TIME + timedelta(minutes=20)

    save_redis_windows(
        metrics,
        latency="0.20",
        repeated_reads="0.20",
        start_time=recovery_start,
    )

    recovered_result = evaluator.evaluate(
        policy=policy,
        evaluated_at=(recovery_start + timedelta(minutes=15)),
    )

    assert recovered_result.outcome is (CheckpointOutcome.HEALTHY)
    assert recovered_result.recommendation is not None
    assert recovered_result.recommendation.status is (RecommendationStatus.RESOLVED)
