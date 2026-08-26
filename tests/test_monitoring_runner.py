import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.db.base import DatabaseBase
from trd_bot.db.monitoring_collector_runner import SqlAlchemyMonitoringCollectorRunner
from trd_bot.db.monitoring_repositories import SqlAlchemySystemMetricRepository
from trd_bot.db.session import create_database_engine, create_session_factory
from trd_bot.monitoring import (
    AggregatedMetricObservation,
    MetricSampleQuery,
    PeriodicMonitoringCollector,
    SystemMetricName,
    SystemMetricSource,
)

CHECKED_AT = datetime(2026, 8, 26, 14, tzinfo=UTC)


def database_observation() -> AggregatedMetricObservation:
    return AggregatedMetricObservation(
        metric_name=SystemMetricName.DATABASE_QUERY_LATENCY_P95,
        source=SystemMetricSource.DATABASE,
        value=Decimal("0.12"),
        observed_count=40,
        labels={"database": "test"},
    )


def test_sqlalchemy_runner_persists_one_idempotent_window() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    runner = SqlAlchemyMonitoringCollectorRunner(
        session_factory=factory,
        observation_provider=lambda: (database_observation(),),
        policies=(),
        clock=lambda: CHECKED_AT,
    )

    try:
        first = runner.run_once()
        second = runner.run_once()

        assert first.samples == second.samples
        assert first.checked_at == CHECKED_AT

        with factory() as session:
            repository = SqlAlchemySystemMetricRepository(session)
            assert repository.count_matching(MetricSampleQuery()) == 1
    finally:
        engine.dispose()


def test_periodic_collector_runs_immediately_and_stops_on_signal() -> None:
    async def scenario() -> int:
        stop_event = asyncio.Event()
        calls = 0

        def run_once() -> None:
            nonlocal calls
            calls += 1
            stop_event.set()

        periodic = PeriodicMonitoringCollector(
            run_once=run_once,
            interval_seconds=60,
        )

        await periodic.run(stop_event)
        return calls

    assert asyncio.run(scenario()) == 1


def test_periodic_collector_does_not_run_after_preemptive_stop() -> None:
    async def scenario() -> int:
        stop_event = asyncio.Event()
        stop_event.set()
        calls = 0

        def run_once() -> None:
            nonlocal calls
            calls += 1

        periodic = PeriodicMonitoringCollector(
            run_once=run_once,
            interval_seconds=60,
        )

        await periodic.run(stop_event)
        return calls

    assert asyncio.run(scenario()) == 0


def test_runner_rejects_invalid_intervals() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    factory = create_session_factory(engine)

    try:
        with pytest.raises(ValueError, match="window_seconds"):
            SqlAlchemyMonitoringCollectorRunner(
                session_factory=factory,
                observation_provider=lambda: (),
                policies=(),
                window_seconds=0,
            )

        with pytest.raises(ValueError, match="interval_seconds"):
            PeriodicMonitoringCollector(
                run_once=lambda: None,
                interval_seconds=0,
            )
    finally:
        engine.dispose()
