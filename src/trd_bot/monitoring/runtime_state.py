from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from trd_bot.monitoring.models import normalize_timestamp

MONITORING_RUNTIME_STATE_KEY = "architecture-monitoring"


class MonitoringRuntimeState(BaseModel):
    """Persisted state for the successful architecture-monitoring cycle."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    last_checked_at: datetime | None = None

    @field_validator("last_checked_at")
    @classmethod
    def last_checked_at_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        return normalize_timestamp(value)


class MonitoringRuntimeStateRepository(Protocol):
    """Persistence contract for the singleton monitoring runtime state."""

    def get(self) -> MonitoringRuntimeState: ...

    def mark_checked(
        self,
        *,
        checked_at: datetime,
    ) -> MonitoringRuntimeState: ...


class InMemoryMonitoringRuntimeStateRepository:
    """In-memory runtime state used by isolated tests."""

    def __init__(self) -> None:
        self._state = MonitoringRuntimeState()

    def get(self) -> MonitoringRuntimeState:
        return self._state

    def mark_checked(
        self,
        *,
        checked_at: datetime,
    ) -> MonitoringRuntimeState:
        normalized_time = normalize_timestamp(checked_at)

        if (
            self._state.last_checked_at is not None
            and normalized_time < self._state.last_checked_at
        ):
            return self._state

        self._state = MonitoringRuntimeState(
            last_checked_at=normalized_time,
        )
        return self._state
