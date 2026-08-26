from decimal import Decimal

import pytest

from trd_bot.monitoring import (
    MonitoringObservationRecorder,
    SystemMetricName,
    percentile_95,
)


def observation_values(recorder: MonitoringObservationRecorder) -> dict[SystemMetricName, Decimal]:
    return {observation.metric_name: observation.value for observation in recorder.drain()}


def test_recorder_aggregates_api_latency_and_error_rate() -> None:
    recorder = MonitoringObservationRecorder()

    for index in range(1, 11):
        recorder.record_api_request(
            duration_seconds=index / 10,
            status_code=500 if index in {3, 8} else 200,
        )

    values = observation_values(recorder)

    assert values[SystemMetricName.API_REQUEST_LATENCY_P95] == Decimal("1.0")
    assert values[SystemMetricName.API_ERROR_RATE] == Decimal("0.2")
    assert recorder.drain() == ()


def test_recorder_aggregates_database_query_latency() -> None:
    recorder = MonitoringObservationRecorder()

    recorder.record_database_query(duration_seconds=0.02)
    recorder.record_database_query(duration_seconds=0.08)
    recorder.record_database_query(duration_seconds=0.04)

    observations = recorder.drain()

    assert len(observations) == 1
    assert observations[0].metric_name is SystemMetricName.DATABASE_QUERY_LATENCY_P95
    assert observations[0].value == Decimal("0.08")
    assert observations[0].observed_count == 3


def test_percentile_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        percentile_95(())


@pytest.mark.parametrize("duration", [-0.1, float("inf"), float("nan")])
def test_recorder_rejects_invalid_durations(duration: float) -> None:
    recorder = MonitoringObservationRecorder()

    with pytest.raises(ValueError, match="finite non-negative"):
        recorder.record_database_query(duration_seconds=duration)


def test_recorder_rejects_invalid_status_code() -> None:
    recorder = MonitoringObservationRecorder()

    with pytest.raises(ValueError, match="between 100 and 599"):
        recorder.record_api_request(duration_seconds=0.1, status_code=700)
