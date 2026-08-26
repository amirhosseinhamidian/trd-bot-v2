from collections.abc import Callable
from time import perf_counter

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from trd_bot.monitoring.observations import MonitoringObservationRecorder

MonotonicClock = Callable[[], float]


class ApiMetricsMiddleware:
    """Record aggregate latency and server-error observations for HTTP requests."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        recorder: MonitoringObservationRecorder,
        clock: MonotonicClock = perf_counter,
    ) -> None:
        self._app = app
        self._recorder = recorder
        self._clock = clock

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        started_at = self._clock()
        status_code = 500

        async def send_with_status(message: Message) -> None:
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = int(message["status"])

            await send(message)

        try:
            await self._app(scope, receive, send_with_status)
        finally:
            duration_seconds = max(0.0, self._clock() - started_at)
            self._recorder.record_api_request(
                duration_seconds=duration_seconds,
                status_code=status_code,
            )
