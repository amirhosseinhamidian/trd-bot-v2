import math
from decimal import Decimal
from threading import Lock

from trd_bot.monitoring.collector import AggregatedMetricObservation
from trd_bot.monitoring.models import SystemMetricName, SystemMetricSource


def percentile_95(values: tuple[Decimal, ...]) -> Decimal:
    """Return the nearest-rank 95th percentile for a non-empty sample."""

    if not values:
        raise ValueError("percentile values cannot be empty")

    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


class MonitoringObservationRecorder:
    """Collect process-local observations and drain aggregate metric windows."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._api_durations: list[Decimal] = []
        self._api_request_count = 0
        self._api_error_count = 0
        self._database_durations: list[Decimal] = []

    def record_api_request(
        self,
        *,
        duration_seconds: float,
        status_code: int,
    ) -> None:
        """Record one completed HTTP request without retaining request data."""

        duration = self._validate_duration(duration_seconds)

        if status_code < 100 or status_code > 599:
            raise ValueError("status_code must be between 100 and 599")

        with self._lock:
            self._api_durations.append(duration)
            self._api_request_count += 1

            if status_code >= 500:
                self._api_error_count += 1

    def record_database_query(self, *, duration_seconds: float) -> None:
        """Record one database query duration."""

        duration = self._validate_duration(duration_seconds)

        with self._lock:
            self._database_durations.append(duration)

    def drain(self) -> tuple[AggregatedMetricObservation, ...]:
        """Atomically return the current aggregate window and clear it."""

        with self._lock:
            api_durations = tuple(self._api_durations)
            api_request_count = self._api_request_count
            api_error_count = self._api_error_count
            database_durations = tuple(self._database_durations)

            self._api_durations.clear()
            self._api_request_count = 0
            self._api_error_count = 0
            self._database_durations.clear()

        observations: list[AggregatedMetricObservation] = []

        if api_request_count > 0:
            observations.extend(
                (
                    AggregatedMetricObservation(
                        metric_name=SystemMetricName.API_REQUEST_LATENCY_P95,
                        source=SystemMetricSource.API,
                        value=percentile_95(api_durations),
                        observed_count=api_request_count,
                        labels={"aggregation": "p95"},
                    ),
                    AggregatedMetricObservation(
                        metric_name=SystemMetricName.API_ERROR_RATE,
                        source=SystemMetricSource.API,
                        value=Decimal(api_error_count) / Decimal(api_request_count),
                        observed_count=api_request_count,
                        labels={"aggregation": "rate"},
                    ),
                )
            )

        if database_durations:
            observations.append(
                AggregatedMetricObservation(
                    metric_name=SystemMetricName.DATABASE_QUERY_LATENCY_P95,
                    source=SystemMetricSource.DATABASE,
                    value=percentile_95(database_durations),
                    observed_count=len(database_durations),
                    labels={"aggregation": "p95"},
                )
            )

        return tuple(observations)

    @staticmethod
    def _validate_duration(duration_seconds: float) -> Decimal:
        if not math.isfinite(duration_seconds) or duration_seconds < 0:
            raise ValueError("duration_seconds must be a finite non-negative value")

        return Decimal(str(duration_seconds))
