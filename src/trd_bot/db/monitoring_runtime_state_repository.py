from datetime import UTC, datetime

from sqlalchemy.orm import Session

from trd_bot.db.models import MonitoringRuntimeStateRow
from trd_bot.monitoring.models import normalize_timestamp
from trd_bot.monitoring.runtime_state import (
    MONITORING_RUNTIME_STATE_KEY,
    MonitoringRuntimeState,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


class SqlAlchemyMonitoringRuntimeStateRepository:
    """Persist the last successful monitoring collector cycle."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> MonitoringRuntimeState:
        row = self._session.get(
            MonitoringRuntimeStateRow,
            MONITORING_RUNTIME_STATE_KEY,
        )

        if row is None:
            return MonitoringRuntimeState()

        return MonitoringRuntimeState(
            last_checked_at=(
                _as_utc(row.last_checked_at) if row.last_checked_at is not None else None
            ),
        )

    def mark_checked(
        self,
        *,
        checked_at: datetime,
    ) -> MonitoringRuntimeState:
        normalized_time = normalize_timestamp(checked_at)
        row = self._session.get(
            MonitoringRuntimeStateRow,
            MONITORING_RUNTIME_STATE_KEY,
        )

        if row is None:
            row = MonitoringRuntimeStateRow(
                state_key=MONITORING_RUNTIME_STATE_KEY,
                last_checked_at=normalized_time,
            )
            self._session.add(row)
        elif row.last_checked_at is not None and _as_utc(row.last_checked_at) > normalized_time:
            return self.get()
        else:
            row.last_checked_at = normalized_time

        self._session.commit()

        return MonitoringRuntimeState(
            last_checked_at=normalized_time,
        )
