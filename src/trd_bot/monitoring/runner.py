import asyncio
from collections.abc import Callable

CollectorCycle = Callable[[], object]


class PeriodicMonitoringCollector:
    """Execute collector cycles at a fixed interval until signalled to stop."""

    def __init__(
        self,
        *,
        run_once: CollectorCycle,
        interval_seconds: float,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")

        self._run_once = run_once
        self._interval_seconds = interval_seconds

    async def run(self, stop_event: asyncio.Event) -> None:
        """Run immediately, then wait between cycles without blocking the event loop."""

        while not stop_event.is_set():
            await asyncio.to_thread(self._run_once)

            if stop_event.is_set():
                break

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._interval_seconds,
                )
            except TimeoutError:
                continue
