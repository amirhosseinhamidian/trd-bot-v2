from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from trd_bot.monitoring.models import (
    ArchitectureCandidate,
    ArchitectureEvidence,
    ArchitectureRecommendation,
    RecommendationSeverity,
    RecommendationStatus,
    SystemMetricName,
    SystemMetricSource,
    build_architecture_recommendation_id,
    normalize_timestamp,
)
from trd_bot.monitoring.repositories import (
    ArchitectureRecommendationRepository,
    MetricSampleQuery,
    RecommendationQuery,
    SystemMetricRepository,
)


class CheckpointOutcome(StrEnum):
    """Possible outcomes of one capacity checkpoint."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    INSUFFICIENT_DATA = "insufficient_data"


class MetricThresholdRule(BaseModel):
    """Thresholds for one consecutive metric condition."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    metric_name: SystemMetricName
    source: SystemMetricSource

    warning_threshold: Decimal = Field(ge=0)
    critical_threshold: Decimal = Field(ge=0)

    minimum_consecutive_windows: int = Field(
        default=3,
        ge=1,
        le=100,
    )

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.critical_threshold < self.warning_threshold:
            raise ValueError("critical threshold cannot be lower than warning threshold")

        return self


class ArchitectureCheckpointPolicy(BaseModel):
    """Evidence requirements for one architecture candidate."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    candidate: ArchitectureCandidate

    title: str = Field(
        min_length=1,
        max_length=150,
    )

    summary: str = Field(
        min_length=1,
        max_length=500,
    )

    rules: tuple[
        MetricThresholdRule,
        ...,
    ] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_rules(self) -> Self:
        identities = [
            (
                rule.metric_name,
                rule.source,
            )
            for rule in self.rules
        ]

        if len(identities) != len(set(identities)):
            raise ValueError("checkpoint rules must be unique")

        return self


class CheckpointEvaluationResult(BaseModel):
    """Transparent result of one checkpoint evaluation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    candidate: ArchitectureCandidate
    outcome: CheckpointOutcome
    evaluated_at: datetime

    evidence: tuple[
        ArchitectureEvidence,
        ...,
    ] = ()

    recommendation: ArchitectureRecommendation | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        normalized_time = normalize_timestamp(self.evaluated_at)

        object.__setattr__(
            self,
            "evaluated_at",
            normalized_time,
        )

        if self.outcome is CheckpointOutcome.INSUFFICIENT_DATA and self.recommendation is not None:
            raise ValueError("insufficient data cannot create a recommendation")

        return self


class ArchitectureCheckpointEvaluator:
    """Evaluate sustained metrics and manage recommendations."""

    def __init__(
        self,
        *,
        metric_repository: SystemMetricRepository,
        recommendation_repository: (ArchitectureRecommendationRepository),
    ) -> None:
        self._metrics = metric_repository
        self._recommendations = recommendation_repository

    def evaluate(
        self,
        *,
        policy: ArchitectureCheckpointPolicy,
        evaluated_at: datetime,
    ) -> CheckpointEvaluationResult:
        normalized_time = normalize_timestamp(evaluated_at)

        evidence: list[ArchitectureEvidence] = []

        rule_severities: list[RecommendationSeverity] = []

        for rule in policy.rules:
            samples = self._metrics.search_page(
                query=MetricSampleQuery(
                    metric_name=rule.metric_name,
                    source=rule.source,
                ),
                limit=(rule.minimum_consecutive_windows),
                offset=0,
            )

            if len(samples) < (rule.minimum_consecutive_windows):
                return CheckpointEvaluationResult(
                    candidate=policy.candidate,
                    outcome=(CheckpointOutcome.INSUFFICIENT_DATA),
                    evaluated_at=normalized_time,
                )

            values = tuple(sample.value for sample in samples)

            if all(value >= rule.critical_threshold for value in values):
                severity = RecommendationSeverity.CRITICAL
                threshold = rule.critical_threshold

            elif all(value >= rule.warning_threshold for value in values):
                severity = RecommendationSeverity.WARNING
                threshold = rule.warning_threshold

            else:
                resolved = self._resolve_active(
                    candidate=policy.candidate,
                    evaluated_at=normalized_time,
                )

                return CheckpointEvaluationResult(
                    candidate=policy.candidate,
                    outcome=CheckpointOutcome.HEALTHY,
                    evaluated_at=normalized_time,
                    recommendation=resolved,
                )

            rule_severities.append(severity)

            evidence.append(
                ArchitectureEvidence(
                    metric_name=rule.metric_name,
                    observed_value=min(values),
                    threshold_value=threshold,
                    comparison=("greater_than_or_equal"),
                    consecutive_windows=(rule.minimum_consecutive_windows),
                )
            )

        severity = (
            RecommendationSeverity.CRITICAL
            if all(item is RecommendationSeverity.CRITICAL for item in rule_severities)
            else RecommendationSeverity.WARNING
        )

        active = self._find_active(policy.candidate)

        first_detected_at = active.first_detected_at if active is not None else normalized_time

        recommendation_id = build_architecture_recommendation_id(
            candidate=policy.candidate,
            first_detected_at=(first_detected_at),
        )

        recommendation = ArchitectureRecommendation(
            recommendation_id=(recommendation_id),
            candidate=policy.candidate,
            severity=severity,
            status=(RecommendationStatus.ACTIVE),
            title=policy.title,
            summary=policy.summary,
            first_detected_at=(first_detected_at),
            last_detected_at=(normalized_time),
            acknowledged_at=(active.acknowledged_at if active is not None else None),
            evidence=tuple(evidence),
        )

        stored = self._recommendations.upsert(recommendation)

        outcome = (
            CheckpointOutcome.CRITICAL
            if severity is RecommendationSeverity.CRITICAL
            else CheckpointOutcome.WARNING
        )

        return CheckpointEvaluationResult(
            candidate=policy.candidate,
            outcome=outcome,
            evaluated_at=normalized_time,
            evidence=tuple(evidence),
            recommendation=stored,
        )

    def _find_active(
        self,
        candidate: ArchitectureCandidate,
    ) -> ArchitectureRecommendation | None:
        recommendations = self._recommendations.search_page(
            query=RecommendationQuery(
                candidate=candidate,
                status=(RecommendationStatus.ACTIVE),
            ),
            limit=1,
            offset=0,
        )

        if not recommendations:
            return None

        return recommendations[0]

    def _resolve_active(
        self,
        *,
        candidate: ArchitectureCandidate,
        evaluated_at: datetime,
    ) -> ArchitectureRecommendation | None:
        active = self._find_active(candidate)

        if active is None:
            return None

        resolved = active.resolve(
            resolved_at=evaluated_at,
        )

        return self._recommendations.upsert(resolved)


def default_checkpoint_policies() -> tuple[
    ArchitectureCheckpointPolicy,
    ...,
]:
    """Return initial evidence-based capacity policies."""

    return (
        ArchitectureCheckpointPolicy(
            candidate=(ArchitectureCandidate.POSTGRESQL_TUNING),
            title="Review PostgreSQL performance",
            summary=("Database query latency remained above its configured budget."),
            rules=(
                MetricThresholdRule(
                    metric_name=(SystemMetricName.DATABASE_QUERY_LATENCY_P95),
                    source=(SystemMetricSource.DATABASE),
                    warning_threshold=(Decimal("0.250")),
                    critical_threshold=(Decimal("1.000")),
                ),
            ),
        ),
        ArchitectureCheckpointPolicy(
            candidate=ArchitectureCandidate.REDIS,
            title="Review read caching",
            summary=(
                "API latency and repeated-read ratio remained above their configured budgets."
            ),
            rules=(
                MetricThresholdRule(
                    metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
                    source=SystemMetricSource.API,
                    warning_threshold=(Decimal("0.500")),
                    critical_threshold=(Decimal("1.500")),
                ),
                MetricThresholdRule(
                    metric_name=(SystemMetricName.API_REPEATED_READ_RATIO),
                    source=SystemMetricSource.API,
                    warning_threshold=(Decimal("0.600")),
                    critical_threshold=(Decimal("0.800")),
                ),
            ),
        ),
        ArchitectureCheckpointPolicy(
            candidate=(ArchitectureCandidate.TIMESCALEDB),
            title="Review time-series storage",
            summary=("Time-series query latency and candle storage share remained elevated."),
            rules=(
                MetricThresholdRule(
                    metric_name=(SystemMetricName.TIME_SERIES_QUERY_LATENCY_P95),
                    source=(SystemMetricSource.DATABASE),
                    warning_threshold=Decimal("1"),
                    critical_threshold=Decimal("3"),
                ),
                MetricThresholdRule(
                    metric_name=(SystemMetricName.CANDLE_STORAGE_SHARE),
                    source=(SystemMetricSource.DATABASE),
                    warning_threshold=(Decimal("0.60")),
                    critical_threshold=(Decimal("0.80")),
                ),
            ),
        ),
        ArchitectureCheckpointPolicy(
            candidate=(ArchitectureCandidate.CLICKHOUSE),
            title="Review analytical storage",
            summary=("Analytical query latency and database resource usage remained elevated."),
            rules=(
                MetricThresholdRule(
                    metric_name=(SystemMetricName.ANALYTICAL_QUERY_LATENCY_P95),
                    source=(SystemMetricSource.DATABASE),
                    warning_threshold=Decimal("3"),
                    critical_threshold=Decimal("10"),
                ),
                MetricThresholdRule(
                    metric_name=(SystemMetricName.ANALYTICAL_DATABASE_RESOURCE_SHARE),
                    source=(SystemMetricSource.DATABASE),
                    warning_threshold=(Decimal("0.30")),
                    critical_threshold=(Decimal("0.60")),
                ),
            ),
        ),
    )
