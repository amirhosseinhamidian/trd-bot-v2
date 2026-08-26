from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from trd_bot.db.monitoring_instrumentation import SqlAlchemyQueryTimingInstrumentation
from trd_bot.db.session import create_database_engine
from trd_bot.monitoring import MonitoringObservationRecorder, SystemMetricName


class SequenceClock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def test_query_instrumentation_records_success_and_failure_durations() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    recorder = MonitoringObservationRecorder()
    instrumentation = SqlAlchemyQueryTimingInstrumentation(
        engine=engine,
        recorder=recorder,
        clock=SequenceClock(10.0, 10.25, 20.0, 20.5),
    )

    instrumentation.install()
    instrumentation.install()

    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1

            with pytest.raises(DBAPIError):
                connection.execute(text("SELECT * FROM missing_monitoring_table"))

        observations = recorder.drain()

        assert len(observations) == 1
        assert observations[0].metric_name is SystemMetricName.DATABASE_QUERY_LATENCY_P95
        assert observations[0].value == Decimal("0.5")
        assert observations[0].observed_count == 2
    finally:
        instrumentation.uninstall()
        instrumentation.uninstall()
        engine.dispose()


def test_uninstall_stops_query_recording() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    recorder = MonitoringObservationRecorder()
    instrumentation = SqlAlchemyQueryTimingInstrumentation(
        engine=engine,
        recorder=recorder,
    )

    instrumentation.install()
    instrumentation.uninstall()

    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1

        assert recorder.drain() == ()
    finally:
        engine.dispose()
