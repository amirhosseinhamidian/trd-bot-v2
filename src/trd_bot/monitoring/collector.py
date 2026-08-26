from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trd_bot.monitoring.checkpoints import (
    ArchitectureCheckpointEvaluator,
    ArchitectureCheckpointPolicy,
    CheckpointEvaluationResult,
    default_checkpoint_policies,
)
from trd_bot.monitoring.models import (
    METRIC_UNITS,
    SystemMetricName,
    SystemMetricSample,
    SystemMetricSource,
    build_metric_sample_id,
    normalize_timestamp,
)
from trd_bot.monitoring.repositories import (
    ArchitectureRecommendationRepository,
    SystemMetricRepository,
)


class AggregatedMetricObservation(BaseModel):
    """A pre-aggregated metric value ready for one collector window."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    metric_name: SystemMetricName
    source: SystemMetricSource
    value: Decimal = Field(ge=0)
    observed_count: int = Field(ge=1)
    labels: dict[str, str] = Field(default_factory=dict)


class MonitoringCollectionResult(BaseModel):
    """Immutable report produced by one collector cycle."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    checked_at: datetime
    window_seconds: int = Field(ge=1)
    samples: tuple[SystemMetricSample, ...]
    checkpoints: tuple[CheckpointEvaluationResult, ...]

    @field_validator("checked_at")
    @classmethod
    def checked_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)


class MonitoringCollector:
    """Persist metric windows and evaluate architecture checkpoints."""

    def __init__(
        self,
        *,
        metric_repository: SystemMetricRepository,
        recommendation_repository: ArchitectureRecommendationRepository,
        policies: Sequence[ArchitectureCheckpointPolicy] | None = None,
    ) -> None:
        self._metrics = metric_repository
        self._recommendations = recommendation_repository
        self._policies = tuple(policies) if policies is not None else default_checkpoint_policies()

    def collect(
        self,
        *,
        observations: Sequence[AggregatedMetricObservation],
        checked_at: datetime,
        window_seconds: int = 300,
    ) -> MonitoringCollectionResult:
        normalized_time = normalize_timestamp(checked_at)

        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self._validate_unique_observations(observations)

        samples = tuple(
            self._metrics.save(
                SystemMetricSample(
                    sample_id=build_metric_sample_id(
                        metric_name=observation.metric_name,
                        source=observation.source,
                        recorded_at=normalized_time,
                        window_seconds=window_seconds,
                    ),
                    metric_name=observation.metric_name,
                    source=observation.source,
                    unit=METRIC_UNITS[observation.metric_name],
                    value=observation.value,
                    recorded_at=normalized_time,
                    window_seconds=window_seconds,
                    observed_count=observation.observed_count,
                    labels=dict(observation.labels),
                )
            )
            for observation in observations
        )

        evaluator = ArchitectureCheckpointEvaluator(
            metric_repository=self._metrics,
            recommendation_repository=self._recommendations,
        )

        checkpoints = tuple(
            evaluator.evaluate(
                policy=policy,
                evaluated_at=normalized_time,
            )
            for policy in self._policies
        )

        return MonitoringCollectionResult(
            checked_at=normalized_time,
            window_seconds=window_seconds,
            samples=samples,
            checkpoints=checkpoints,
        )

    @staticmethod
    def _validate_unique_observations(
        observations: Sequence[AggregatedMetricObservation],
    ) -> None:
        identities = [
            (
                observation.metric_name,
                observation.source,
            )
            for observation in observations
        ]

        if len(identities) != len(set(identities)):
            raise ValueError("collector observations must be unique by metric name and source")
