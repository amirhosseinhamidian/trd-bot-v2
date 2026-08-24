from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from trd_bot.monitoring.models import (
    ArchitectureCandidate,
    ArchitectureRecommendation,
    RecommendationSeverity,
    RecommendationStatus,
    SystemMetricName,
    SystemMetricSample,
    SystemMetricSource,
    normalize_timestamp,
)


class MonitoringSortDirection(StrEnum):
    """Supported ordering directions for monitoring catalogs."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class MetricSampleQuery(BaseModel):
    """Filters and ordering for aggregated metric samples."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    metric_name: SystemMetricName | None = None
    source: SystemMetricSource | None = None

    recorded_at_from: datetime | None = None
    recorded_at_to: datetime | None = None

    sort_direction: MonitoringSortDirection = MonitoringSortDirection.DESCENDING

    @field_validator(
        "recorded_at_from",
        "recorded_at_to",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if (
            self.recorded_at_from is not None
            and self.recorded_at_to is not None
            and self.recorded_at_to < self.recorded_at_from
        ):
            raise ValueError("recorded_at_to must be on or after recorded_at_from")

        return self


class RecommendationQuery(BaseModel):
    """Filters and ordering for architecture recommendations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    candidate: ArchitectureCandidate | None = None
    severity: RecommendationSeverity | None = None
    status: RecommendationStatus | None = None

    detected_at_from: datetime | None = None
    detected_at_to: datetime | None = None

    sort_direction: MonitoringSortDirection = MonitoringSortDirection.DESCENDING

    @field_validator(
        "detected_at_from",
        "detected_at_to",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if (
            self.detected_at_from is not None
            and self.detected_at_to is not None
            and self.detected_at_to < self.detected_at_from
        ):
            raise ValueError("detected_at_to must be on or after detected_at_from")

        return self


def validate_monitoring_pagination(
    *,
    limit: int,
    offset: int,
) -> None:
    """Validate repository pagination values."""

    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    if offset < 0:
        raise ValueError("offset cannot be negative")


class SystemMetricRepository(Protocol):
    """Persistence contract for aggregated metric samples."""

    def save(
        self,
        sample: SystemMetricSample,
    ) -> SystemMetricSample: ...

    def get(
        self,
        sample_id: str,
    ) -> SystemMetricSample | None: ...

    def latest(
        self,
        *,
        metric_name: SystemMetricName,
        source: SystemMetricSource | None = None,
    ) -> SystemMetricSample | None: ...

    def count_matching(
        self,
        query: MetricSampleQuery,
    ) -> int: ...

    def search_page(
        self,
        *,
        query: MetricSampleQuery,
        limit: int,
        offset: int,
    ) -> tuple[SystemMetricSample, ...]: ...


class ArchitectureRecommendationRepository(Protocol):
    """Persistence contract for architecture recommendations."""

    def upsert(
        self,
        recommendation: ArchitectureRecommendation,
    ) -> ArchitectureRecommendation: ...

    def get(
        self,
        recommendation_id: str,
    ) -> ArchitectureRecommendation | None: ...

    def count_matching(
        self,
        query: RecommendationQuery,
    ) -> int: ...

    def search_page(
        self,
        *,
        query: RecommendationQuery,
        limit: int,
        offset: int,
    ) -> tuple[ArchitectureRecommendation, ...]: ...


class InMemorySystemMetricRepository:
    """Store metric samples in memory for isolated tests."""

    def __init__(self) -> None:
        self._samples: dict[
            str,
            SystemMetricSample,
        ] = {}

    def save(
        self,
        sample: SystemMetricSample,
    ) -> SystemMetricSample:
        existing = self._samples.get(sample.sample_id)

        if existing is not None:
            if existing != sample:
                raise ValueError("metric sample ID already exists with different content")

            return existing

        self._samples[sample.sample_id] = sample

        return sample

    def get(
        self,
        sample_id: str,
    ) -> SystemMetricSample | None:
        return self._samples.get(sample_id)

    def latest(
        self,
        *,
        metric_name: SystemMetricName,
        source: SystemMetricSource | None = None,
    ) -> SystemMetricSample | None:
        candidates = [
            sample
            for sample in self._samples.values()
            if sample.metric_name is metric_name and (source is None or sample.source is source)
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda sample: (
                sample.recorded_at,
                sample.sample_id,
            ),
        )

    def count_matching(
        self,
        query: MetricSampleQuery,
    ) -> int:
        return len(self._filter(query))

    def search_page(
        self,
        *,
        query: MetricSampleQuery,
        limit: int,
        offset: int,
    ) -> tuple[SystemMetricSample, ...]:
        validate_monitoring_pagination(
            limit=limit,
            offset=offset,
        )

        reverse = query.sort_direction is MonitoringSortDirection.DESCENDING

        samples = sorted(
            self._filter(query),
            key=lambda sample: (
                sample.recorded_at,
                sample.sample_id,
            ),
            reverse=reverse,
        )

        return tuple(samples[offset : offset + limit])

    def _filter(
        self,
        query: MetricSampleQuery,
    ) -> tuple[SystemMetricSample, ...]:
        return tuple(
            sample
            for sample in self._samples.values()
            if (query.metric_name is None or sample.metric_name is query.metric_name)
            and (query.source is None or sample.source is query.source)
            and (query.recorded_at_from is None or sample.recorded_at >= query.recorded_at_from)
            and (query.recorded_at_to is None or sample.recorded_at <= query.recorded_at_to)
        )


class InMemoryArchitectureRecommendationRepository:
    """Store architecture recommendations in memory."""

    def __init__(self) -> None:
        self._recommendations: dict[
            str,
            ArchitectureRecommendation,
        ] = {}

    def upsert(
        self,
        recommendation: ArchitectureRecommendation,
    ) -> ArchitectureRecommendation:
        existing = self._recommendations.get(recommendation.recommendation_id)

        if existing is not None:
            if existing.candidate is not recommendation.candidate:
                raise ValueError("recommendation ID belongs to another candidate")

            if existing.first_detected_at != recommendation.first_detected_at:
                raise ValueError("recommendation first detection cannot be changed")

        self._recommendations[recommendation.recommendation_id] = recommendation

        return recommendation

    def get(
        self,
        recommendation_id: str,
    ) -> ArchitectureRecommendation | None:
        return self._recommendations.get(recommendation_id)

    def count_matching(
        self,
        query: RecommendationQuery,
    ) -> int:
        return len(self._filter(query))

    def search_page(
        self,
        *,
        query: RecommendationQuery,
        limit: int,
        offset: int,
    ) -> tuple[ArchitectureRecommendation, ...]:
        validate_monitoring_pagination(
            limit=limit,
            offset=offset,
        )

        reverse = query.sort_direction is MonitoringSortDirection.DESCENDING

        recommendations = sorted(
            self._filter(query),
            key=lambda recommendation: (
                recommendation.last_detected_at,
                recommendation.recommendation_id,
            ),
            reverse=reverse,
        )

        return tuple(recommendations[offset : offset + limit])

    def _filter(
        self,
        query: RecommendationQuery,
    ) -> tuple[
        ArchitectureRecommendation,
        ...,
    ]:
        return tuple(
            recommendation
            for recommendation in self._recommendations.values()
            if (query.candidate is None or recommendation.candidate is query.candidate)
            and (query.severity is None or recommendation.severity is query.severity)
            and (query.status is None or recommendation.status is query.status)
            and (
                query.detected_at_from is None
                or recommendation.last_detected_at >= query.detected_at_from
            )
            and (
                query.detected_at_to is None
                or recommendation.last_detected_at <= query.detected_at_to
            )
        )
