from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from trd_bot.api.monitoring_middleware import ApiMetricsMiddleware
from trd_bot.monitoring import MonitoringObservationRecorder, SystemMetricName


class SequenceClock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def test_api_middleware_records_latency_and_status() -> None:
    recorder = MonitoringObservationRecorder()
    application = FastAPI()
    application.add_middleware(
        ApiMetricsMiddleware,
        recorder=recorder,
        clock=SequenceClock(10.0, 10.25),
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    response = TestClient(application).get("/health")
    observations = {item.metric_name: item for item in recorder.drain()}

    assert response.status_code == 200
    assert observations[SystemMetricName.API_REQUEST_LATENCY_P95].value == Decimal("0.25")
    assert observations[SystemMetricName.API_ERROR_RATE].value == Decimal("0")


def test_api_middleware_records_unhandled_errors() -> None:
    recorder = MonitoringObservationRecorder()
    application = FastAPI()
    application.add_middleware(
        ApiMetricsMiddleware,
        recorder=recorder,
        clock=SequenceClock(20.0, 20.1),
    )

    @application.get("/failure")
    def failure() -> None:
        raise RuntimeError("test failure")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/failure")

    observations = {item.metric_name: item for item in recorder.drain()}

    assert response.status_code == 500
    assert observations[SystemMetricName.API_ERROR_RATE].value == Decimal("1")
