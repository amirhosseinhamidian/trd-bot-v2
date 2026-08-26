import asyncio

from fastapi import FastAPI

from trd_bot.api.monitoring_lifecycle import MonitoringRuntime, build_monitoring_lifespan
from trd_bot.core.config import Settings
from trd_bot.monitoring import MonitoringObservationRecorder


class FakeInstrumentation:
    def __init__(self) -> None:
        self.installed = False
        self.uninstalled = False

    def install(self) -> None:
        self.installed = True

    def uninstall(self) -> None:
        self.uninstalled = True


class FakePeriodicCollector:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.stopped = False

    async def run(self, stop_event: asyncio.Event) -> None:
        self.started.set()
        await stop_event.wait()
        self.stopped = True


class FakeRuntime:
    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0

    async def start(self) -> None:
        self.start_count += 1

    async def stop(self) -> None:
        self.stop_count += 1


def test_monitoring_runtime_installs_and_cleans_up_resources() -> None:
    async def scenario() -> tuple[FakeInstrumentation, FakePeriodicCollector]:
        instrumentation = FakeInstrumentation()
        periodic = FakePeriodicCollector()
        runtime = MonitoringRuntime(
            instrumentation=instrumentation,
            periodic_collector=periodic,
        )

        await runtime.start()
        await runtime.start()
        await periodic.started.wait()
        await runtime.stop()

        return instrumentation, periodic

    instrumentation, periodic = asyncio.run(scenario())

    assert instrumentation.installed is True
    assert instrumentation.uninstalled is True
    assert periodic.stopped is True


def test_enabled_lifespan_starts_and_stops_runtime() -> None:
    async def scenario() -> FakeRuntime:
        runtime = FakeRuntime()
        lifespan = build_monitoring_lifespan(
            settings=Settings(monitoring_collector_enabled=True),
            recorder=MonitoringObservationRecorder(),
            runtime_factory=lambda _settings, _recorder: runtime,
        )

        async with lifespan(FastAPI()):
            assert runtime.start_count == 1
            assert runtime.stop_count == 0

        return runtime

    runtime = asyncio.run(scenario())

    assert runtime.start_count == 1
    assert runtime.stop_count == 1


def test_disabled_lifespan_does_not_build_runtime() -> None:
    async def scenario() -> int:
        factory_calls = 0

        def runtime_factory(
            _settings: Settings,
            _recorder: MonitoringObservationRecorder,
        ) -> FakeRuntime:
            nonlocal factory_calls
            factory_calls += 1
            return FakeRuntime()

        lifespan = build_monitoring_lifespan(
            settings=Settings(monitoring_collector_enabled=False),
            recorder=MonitoringObservationRecorder(),
            runtime_factory=runtime_factory,
        )

        async with lifespan(FastAPI()):
            pass

        return factory_calls

    assert asyncio.run(scenario()) == 0
