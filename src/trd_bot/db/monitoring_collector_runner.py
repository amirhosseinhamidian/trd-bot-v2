from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db.monitoring_repositories import (
    SqlAlchemyArchitectureRecommendationRepository,
    SqlAlchemySystemMetricRepository,
)
from trd_bot.db.monitoring_runtime_state_repository import (
    SqlAlchemyMonitoringRuntimeStateRepository,
)
from trd_bot.monitoring.checkpoints import ArchitectureCheckpointPolicy
from trd_bot.monitoring.collector import (
    AggregatedMetricObservation,
    MonitoringCollectionResult,
    MonitoringCollector,
)

ObservationProvider = Callable[[], Sequence[AggregatedMetricObservation]]
CollectorClock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class SqlAlchemyMonitoringCollectorRunner:
    """Run one collector cycle against SQLAlchemy-backed repositories."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        observation_provider: ObservationProvider,
        policies: Sequence[ArchitectureCheckpointPolicy] | None = None,
        window_seconds: int = 300,
        clock: CollectorClock = utc_now,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self._session_factory = session_factory
        self._observation_provider = observation_provider
        self._policies = tuple(policies) if policies is not None else None
        self._window_seconds = window_seconds
        self._clock = clock

    def run_once(self) -> MonitoringCollectionResult:
        """Collect current observations in a fresh database session."""

        observations = tuple(self._observation_provider())
        checked_at = self._clock()

        with self._session_factory() as session:
            collector = MonitoringCollector(
                metric_repository=SqlAlchemySystemMetricRepository(session),
                recommendation_repository=(SqlAlchemyArchitectureRecommendationRepository(session)),
                policies=self._policies,
            )

            result = collector.collect(
                observations=observations,
                checked_at=checked_at,
                window_seconds=self._window_seconds,
            )

            SqlAlchemyMonitoringRuntimeStateRepository(session).mark_checked(
                checked_at=result.checked_at,
            )

            return result
