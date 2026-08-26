import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from trd_bot.core.config import Settings
from trd_bot.db.monitoring_collector_runner import SqlAlchemyMonitoringCollectorRunner
from trd_bot.db.monitoring_instrumentation import SqlAlchemyQueryTimingInstrumentation
from trd_bot.db.session import get_database_engine, get_session_factory
from trd_bot.monitoring import MonitoringObservationRecorder, PeriodicMonitoringCollector

LOGGER = logging.getLogger(__name__)


class QueryInstrumentation(Protocol):
    """Lifecycle contract for database query instrumentation."""

    def install(self) -> None: ...

    def uninstall(self) -> None: ...


class PeriodicCollector(Protocol):
    """Lifecycle contract for one stoppable periodic collector."""

    async def run(self, stop_event: asyncio.Event) -> None: ...


class MonitoringRuntimeProtocol(Protocol):
    """Startup and shutdown contract used by the FastAPI lifespan."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class MonitoringRuntime:
    """Own instrumentation and the periodic collector task for one process."""

    def __init__(
        self,
        *,
        instrumentation: QueryInstrumentation,
        periodic_collector: PeriodicCollector,
    ) -> None:
        self._instrumentation = instrumentation
        self._periodic_collector = periodic_collector
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Install instrumentation and start one collector task."""

        if self._task is not None:
            return

        self._instrumentation.install()
        self._task = asyncio.create_task(
            self._periodic_collector.run(self._stop_event),
            name="monitoring-collector",
        )

    async def stop(self) -> None:
        """Stop the collector and always remove query instrumentation."""

        if self._task is None:
            return

        self._stop_event.set()

        try:
            await self._task
        finally:
            self._instrumentation.uninstall()
            self._task = None


def create_monitoring_runtime(
    settings: Settings,
    recorder: MonitoringObservationRecorder,
) -> MonitoringRuntime:
    """Build the production monitoring runtime from process-wide dependencies."""

    instrumentation = SqlAlchemyQueryTimingInstrumentation(
        engine=get_database_engine(),
        recorder=recorder,
    )
    collector_runner = SqlAlchemyMonitoringCollectorRunner(
        session_factory=get_session_factory(),
        observation_provider=recorder.drain,
        window_seconds=settings.monitoring_collector_window_seconds,
    )

    def run_once_safely() -> None:
        try:
            collector_runner.run_once()
        except Exception:
            LOGGER.exception("monitoring collector cycle failed")

    return MonitoringRuntime(
        instrumentation=instrumentation,
        periodic_collector=PeriodicMonitoringCollector(
            run_once=run_once_safely,
            interval_seconds=settings.monitoring_collector_interval_seconds,
        ),
    )


RuntimeFactory = Callable[
    [Settings, MonitoringObservationRecorder],
    MonitoringRuntimeProtocol,
]
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def build_monitoring_lifespan(
    *,
    settings: Settings,
    recorder: MonitoringObservationRecorder,
    runtime_factory: RuntimeFactory = create_monitoring_runtime,
) -> Lifespan:
    """Build an optional monitoring lifespan controlled by application settings."""

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        runtime: MonitoringRuntimeProtocol | None = None

        if settings.monitoring_collector_enabled:
            runtime = runtime_factory(settings, recorder)
            await runtime.start()

        try:
            yield
        finally:
            if runtime is not None:
                await runtime.stop()

    return lifespan
