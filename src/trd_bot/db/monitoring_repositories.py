from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from trd_bot.db.models import (
    ArchitectureRecommendationRow,
    SystemMetricSampleRow,
)
from trd_bot.monitoring.models import (
    ArchitectureRecommendation,
    SystemMetricName,
    SystemMetricSample,
    SystemMetricSource,
    SystemMetricUnit,
)
from trd_bot.monitoring.repositories import (
    MetricSampleQuery,
    MonitoringSortDirection,
    RecommendationQuery,
    validate_monitoring_pagination,
)


def as_utc(value: datetime) -> datetime:
    """Normalize timestamps returned by supported SQL dialects."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


class SqlAlchemySystemMetricRepository:
    """Persist immutable metric snapshots with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        sample: SystemMetricSample,
    ) -> SystemMetricSample:
        existing = self.get(sample.sample_id)

        if existing is not None:
            if existing != sample:
                raise ValueError("metric sample ID already exists with different content")

            return existing

        self._session.add(
            SystemMetricSampleRow(
                sample_id=sample.sample_id,
                recorded_at=sample.recorded_at,
                metric_name=sample.metric_name.value,
                source=sample.source.value,
                unit=sample.unit.value,
                value=sample.value,
                window_seconds=sample.window_seconds,
                observed_count=sample.observed_count,
                labels_json=dict(sample.labels),
            )
        )

        try:
            self._session.commit()
            return sample
        except IntegrityError as error:
            self._session.rollback()

            concurrent = self.get(sample.sample_id)

            if concurrent == sample:
                return sample

            raise ValueError("metric sample ID already exists with different content") from error

    def get(
        self,
        sample_id: str,
    ) -> SystemMetricSample | None:
        row = self._session.get(
            SystemMetricSampleRow,
            sample_id,
        )

        if row is None:
            return None

        return self._to_model(row)

    def latest(
        self,
        *,
        metric_name: SystemMetricName,
        source: SystemMetricSource | None = None,
    ) -> SystemMetricSample | None:
        conditions: list[ColumnElement[bool]] = [
            SystemMetricSampleRow.metric_name == metric_name.value
        ]

        if source is not None:
            conditions.append(SystemMetricSampleRow.source == source.value)

        row = self._session.scalar(
            select(SystemMetricSampleRow)
            .where(*conditions)
            .order_by(
                SystemMetricSampleRow.recorded_at.desc(),
                SystemMetricSampleRow.sample_id.desc(),
            )
            .limit(1)
        )

        if row is None:
            return None

        return self._to_model(row)

    def count_matching(
        self,
        query: MetricSampleQuery,
    ) -> int:
        value = self._session.scalar(
            select(func.count()).select_from(SystemMetricSampleRow).where(*self._conditions(query))
        )

        return int(value or 0)

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

        if query.sort_direction is MonitoringSortDirection.DESCENDING:
            ordering = (
                SystemMetricSampleRow.recorded_at.desc(),
                SystemMetricSampleRow.sample_id.desc(),
            )
        else:
            ordering = (
                SystemMetricSampleRow.recorded_at.asc(),
                SystemMetricSampleRow.sample_id.asc(),
            )

        rows = self._session.scalars(
            select(SystemMetricSampleRow)
            .where(*self._conditions(query))
            .order_by(*ordering)
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(self._to_model(row) for row in rows)

    @staticmethod
    def _conditions(
        query: MetricSampleQuery,
    ) -> tuple[ColumnElement[bool], ...]:
        conditions: list[ColumnElement[bool]] = []

        if query.metric_name is not None:
            conditions.append(SystemMetricSampleRow.metric_name == query.metric_name.value)

        if query.source is not None:
            conditions.append(SystemMetricSampleRow.source == query.source.value)

        if query.recorded_at_from is not None:
            conditions.append(SystemMetricSampleRow.recorded_at >= query.recorded_at_from)

        if query.recorded_at_to is not None:
            conditions.append(SystemMetricSampleRow.recorded_at <= query.recorded_at_to)

        return tuple(conditions)

    @staticmethod
    def _to_model(
        row: SystemMetricSampleRow,
    ) -> SystemMetricSample:
        return SystemMetricSample(
            sample_id=row.sample_id,
            metric_name=SystemMetricName(row.metric_name),
            source=SystemMetricSource(row.source),
            unit=SystemMetricUnit(row.unit),
            value=row.value,
            recorded_at=as_utc(row.recorded_at),
            window_seconds=row.window_seconds,
            observed_count=row.observed_count,
            labels=dict(row.labels_json),
        )


class SqlAlchemyArchitectureRecommendationRepository:
    """Persist mutable architecture recommendation lifecycle."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        recommendation: ArchitectureRecommendation,
    ) -> ArchitectureRecommendation:
        row = self._session.get(
            ArchitectureRecommendationRow,
            recommendation.recommendation_id,
        )

        if row is None:
            self._session.add(
                ArchitectureRecommendationRow(
                    recommendation_id=(recommendation.recommendation_id),
                    candidate=(recommendation.candidate.value),
                    severity=(recommendation.severity.value),
                    status=recommendation.status.value,
                    first_detected_at=(recommendation.first_detected_at),
                    last_detected_at=(recommendation.last_detected_at),
                    payload_json=(recommendation.model_dump_json()),
                )
            )

            try:
                self._session.commit()
                return recommendation
            except IntegrityError as error:
                self._session.rollback()

                concurrent = self.get(recommendation.recommendation_id)

                if concurrent == recommendation:
                    return recommendation

                raise ValueError(
                    "recommendation ID already exists with incompatible content"
                ) from error

        existing = ArchitectureRecommendation.model_validate_json(row.payload_json)

        if existing.candidate is not recommendation.candidate:
            raise ValueError("recommendation ID belongs to another candidate")

        if existing.first_detected_at != recommendation.first_detected_at:
            raise ValueError("recommendation first detection cannot be changed")

        row.severity = recommendation.severity.value
        row.status = recommendation.status.value
        row.last_detected_at = recommendation.last_detected_at
        row.payload_json = recommendation.model_dump_json()

        self._session.commit()

        return recommendation

    def get(
        self,
        recommendation_id: str,
    ) -> ArchitectureRecommendation | None:
        row = self._session.get(
            ArchitectureRecommendationRow,
            recommendation_id,
        )

        if row is None:
            return None

        return ArchitectureRecommendation.model_validate_json(row.payload_json)

    def count_matching(
        self,
        query: RecommendationQuery,
    ) -> int:
        value = self._session.scalar(
            select(func.count())
            .select_from(ArchitectureRecommendationRow)
            .where(*self._conditions(query))
        )

        return int(value or 0)

    def search_page(
        self,
        *,
        query: RecommendationQuery,
        limit: int,
        offset: int,
    ) -> tuple[
        ArchitectureRecommendation,
        ...,
    ]:
        validate_monitoring_pagination(
            limit=limit,
            offset=offset,
        )

        if query.sort_direction is MonitoringSortDirection.DESCENDING:
            ordering = (
                ArchitectureRecommendationRow.last_detected_at.desc(),
                ArchitectureRecommendationRow.recommendation_id.desc(),
            )
        else:
            ordering = (
                ArchitectureRecommendationRow.last_detected_at.asc(),
                ArchitectureRecommendationRow.recommendation_id.asc(),
            )

        rows = self._session.scalars(
            select(ArchitectureRecommendationRow)
            .where(*self._conditions(query))
            .order_by(*ordering)
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(
            ArchitectureRecommendation.model_validate_json(row.payload_json) for row in rows
        )

    @staticmethod
    def _conditions(
        query: RecommendationQuery,
    ) -> tuple[ColumnElement[bool], ...]:
        conditions: list[ColumnElement[bool]] = []

        if query.candidate is not None:
            conditions.append(ArchitectureRecommendationRow.candidate == query.candidate.value)

        if query.severity is not None:
            conditions.append(ArchitectureRecommendationRow.severity == query.severity.value)

        if query.status is not None:
            conditions.append(ArchitectureRecommendationRow.status == query.status.value)

        if query.detected_at_from is not None:
            conditions.append(
                ArchitectureRecommendationRow.last_detected_at >= query.detected_at_from
            )

        if query.detected_at_to is not None:
            conditions.append(
                ArchitectureRecommendationRow.last_detected_at <= query.detected_at_to
            )

        return tuple(conditions)
