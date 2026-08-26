from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.monitoring import (
    ArchitectureCandidate,
    ArchitectureEvidence,
    ArchitectureRecommendation,
    RecommendationSeverity,
    RecommendationStatus,
    SystemMetricName,
    SystemMetricSample,
    SystemMetricSource,
    SystemMetricUnit,
    build_architecture_recommendation_id,
    build_metric_sample_id,
)

RECORDED_AT = datetime(
    2026,
    8,
    24,
    10,
    tzinfo=UTC,
)


def create_latency_sample() -> SystemMetricSample:
    sample_id = build_metric_sample_id(
        metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
        source=SystemMetricSource.API,
        recorded_at=RECORDED_AT,
        window_seconds=300,
    )

    return SystemMetricSample(
        sample_id=sample_id,
        metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
        source=SystemMetricSource.API,
        unit=SystemMetricUnit.SECONDS,
        value=Decimal("0.450"),
        recorded_at=RECORDED_AT,
        window_seconds=300,
        observed_count=150,
        labels={
            "route": "/api/v1/research/overview",
        },
    )


def test_metric_sample_has_deterministic_identity() -> None:
    first = create_latency_sample()
    second = create_latency_sample()

    assert first.sample_id == second.sample_id
    assert first.recorded_at == RECORDED_AT


def test_metric_sample_rejects_wrong_unit() -> None:
    sample = create_latency_sample()
    payload = sample.model_dump()

    payload["unit"] = SystemMetricUnit.FRACTION

    with pytest.raises(
        ValidationError,
        match="metric unit does not match",
    ):
        SystemMetricSample.model_validate(payload)


def test_fraction_metric_rejects_value_above_one() -> None:
    sample_id = build_metric_sample_id(
        metric_name=SystemMetricName.API_ERROR_RATE,
        source=SystemMetricSource.API,
        recorded_at=RECORDED_AT,
        window_seconds=300,
    )

    with pytest.raises(
        ValidationError,
        match="cannot exceed one",
    ):
        SystemMetricSample(
            sample_id=sample_id,
            metric_name=SystemMetricName.API_ERROR_RATE,
            source=SystemMetricSource.API,
            unit=SystemMetricUnit.FRACTION,
            value=Decimal("1.01"),
            recorded_at=RECORDED_AT,
            window_seconds=300,
            observed_count=100,
        )


def test_metric_sample_rejects_mismatched_id() -> None:
    sample = create_latency_sample()

    with pytest.raises(
        ValidationError,
        match="ID does not match",
    ):
        SystemMetricSample(
            **{
                **sample.model_dump(),
                "sample_id": ("metric-sample-0000000000000000"),
            }
        )


def test_architecture_recommendation_is_validated() -> None:
    recommendation_id = build_architecture_recommendation_id(
        candidate=ArchitectureCandidate.REDIS,
        first_detected_at=RECORDED_AT,
    )

    recommendation = ArchitectureRecommendation(
        recommendation_id=recommendation_id,
        candidate=ArchitectureCandidate.REDIS,
        severity=RecommendationSeverity.WARNING,
        title="Review repeated API reads",
        summary=("Repeated read latency remained above the configured warning threshold."),
        first_detected_at=RECORDED_AT,
        last_detected_at=(RECORDED_AT + timedelta(minutes=15)),
        evidence=(
            ArchitectureEvidence(
                metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
                observed_value=Decimal("0.750"),
                threshold_value=Decimal("0.500"),
                comparison="greater_than_or_equal",
                consecutive_windows=3,
            ),
        ),
    )

    assert recommendation.interpretation == "capacity_planning_only"


def test_recommendation_acknowledge_and_resolve_are_idempotent() -> None:
    recommendation_id = build_architecture_recommendation_id(
        candidate=ArchitectureCandidate.REDIS,
        first_detected_at=RECORDED_AT,
    )

    recommendation = ArchitectureRecommendation(
        recommendation_id=recommendation_id,
        candidate=ArchitectureCandidate.REDIS,
        severity=RecommendationSeverity.WARNING,
        title="Review repeated API reads",
        summary=("Repeated read latency remained above the configured warning threshold."),
        first_detected_at=RECORDED_AT,
        last_detected_at=(RECORDED_AT + timedelta(minutes=15)),
        evidence=(
            ArchitectureEvidence(
                metric_name=SystemMetricName.API_REQUEST_LATENCY_P95,
                observed_value=Decimal("0.750"),
                threshold_value=Decimal("0.500"),
                comparison="greater_than_or_equal",
                consecutive_windows=3,
            ),
        ),
    )

    acknowledged_at = RECORDED_AT + timedelta(minutes=20)
    acknowledged = recommendation.acknowledge(
        acknowledged_at=acknowledged_at,
    )

    assert acknowledged.status is RecommendationStatus.ACTIVE
    assert acknowledged.acknowledged_at == acknowledged_at
    assert (
        acknowledged.acknowledge(
            acknowledged_at=(acknowledged_at + timedelta(minutes=1)),
        )
        == acknowledged
    )

    resolved_at = RECORDED_AT + timedelta(minutes=25)
    resolved = acknowledged.resolve(
        resolved_at=resolved_at,
    )

    assert resolved.status is RecommendationStatus.RESOLVED
    assert resolved.acknowledged_at == acknowledged_at
    assert resolved.resolved_at == resolved_at
    assert (
        resolved.resolve(
            resolved_at=(resolved_at + timedelta(minutes=1)),
        )
        == resolved
    )


def test_recommendation_rejects_reversed_times() -> None:
    recommendation_id = build_architecture_recommendation_id(
        candidate=(ArchitectureCandidate.TIMESCALEDB),
        first_detected_at=RECORDED_AT,
    )

    with pytest.raises(
        ValidationError,
        match="cannot precede",
    ):
        ArchitectureRecommendation(
            recommendation_id=recommendation_id,
            candidate=(ArchitectureCandidate.TIMESCALEDB),
            severity=(RecommendationSeverity.WARNING),
            title="Review time-series storage",
            summary=("Time-series queries exceeded their latency budget."),
            first_detected_at=RECORDED_AT,
            last_detected_at=(RECORDED_AT - timedelta(minutes=5)),
            evidence=(
                ArchitectureEvidence(
                    metric_name=(SystemMetricName.DATABASE_QUERY_LATENCY_P95),
                    observed_value=Decimal("1.2"),
                    threshold_value=Decimal("1"),
                    comparison=("greater_than_or_equal"),
                    consecutive_windows=3,
                ),
            ),
        )
