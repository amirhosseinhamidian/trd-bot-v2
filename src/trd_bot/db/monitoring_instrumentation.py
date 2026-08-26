from collections.abc import Callable
from time import perf_counter
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.engine import Connection, ExceptionContext

from trd_bot.monitoring.observations import MonitoringObservationRecorder

MonotonicClock = Callable[[], float]
QUERY_START_STACK_KEY = "trd_bot_monitoring_query_start_times"


class SqlAlchemyQueryTimingInstrumentation:
    """Record SQLAlchemy query durations without retaining SQL or parameters."""

    def __init__(
        self,
        *,
        engine: Engine,
        recorder: MonitoringObservationRecorder,
        clock: MonotonicClock = perf_counter,
    ) -> None:
        self._engine = engine
        self._recorder = recorder
        self._clock = clock
        self._installed = False

    def install(self) -> None:
        """Install query listeners once for the configured engine."""

        if self._installed:
            return

        event.listen(
            self._engine,
            "before_cursor_execute",
            self._before_cursor_execute,
        )
        event.listen(
            self._engine,
            "after_cursor_execute",
            self._after_cursor_execute,
        )
        event.listen(
            self._engine,
            "handle_error",
            self._handle_error,
        )
        self._installed = True

    def uninstall(self) -> None:
        """Remove installed listeners without failing on repeated calls."""

        if not self._installed:
            return

        event.remove(
            self._engine,
            "before_cursor_execute",
            self._before_cursor_execute,
        )
        event.remove(
            self._engine,
            "after_cursor_execute",
            self._after_cursor_execute,
        )
        event.remove(
            self._engine,
            "handle_error",
            self._handle_error,
        )
        self._installed = False

    def _before_cursor_execute(
        self,
        connection: Connection,
        _cursor: Any,
        _statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        stack = connection.info.setdefault(QUERY_START_STACK_KEY, [])
        stack.append(self._clock())

    def _after_cursor_execute(
        self,
        connection: Connection,
        _cursor: Any,
        _statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        self._record_elapsed(connection)

    def _handle_error(self, exception_context: ExceptionContext) -> None:
        self._record_elapsed(exception_context.connection)

    def _record_elapsed(self, connection: Connection | None) -> None:
        if connection is None:
            return

        stack = connection.info.get(QUERY_START_STACK_KEY)

        if not isinstance(stack, list) or not stack:
            return

        started_at = float(stack.pop())

        if not stack:
            connection.info.pop(QUERY_START_STACK_KEY, None)

        self._recorder.record_database_query(duration_seconds=max(0.0, self._clock() - started_at))
