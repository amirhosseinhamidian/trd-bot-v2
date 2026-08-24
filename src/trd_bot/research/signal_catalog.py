from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from trd_bot.strategies.signals import SignalDirection, StrategySignal


class ExperimentSignalSortDirection(StrEnum):
    """Supported ordering for stored historical signals."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class ExperimentSignalCatalogQuery(BaseModel):
    """Filters and ordering for signals derived from one stored experiment."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    direction: SignalDirection | None = None
    candle_close_time_from: datetime | None = None
    candle_close_time_to: datetime | None = None
    sort_direction: ExperimentSignalSortDirection = ExperimentSignalSortDirection.DESCENDING

    @field_validator(
        "candle_close_time_from",
        "candle_close_time_to",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("signal time filters must include timezone information")

        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if (
            self.candle_close_time_from is not None
            and self.candle_close_time_to is not None
            and self.candle_close_time_to < self.candle_close_time_from
        ):
            raise ValueError("candle_close_time_to must be on or after candle_close_time_from")

        return self


class ExperimentSignalCatalog:
    """Search immutable historical signals stored inside an experiment."""

    def count_matching(
        self,
        *,
        signals: Sequence[StrategySignal],
        query: ExperimentSignalCatalogQuery,
    ) -> int:
        return len(self._filter(signals=signals, query=query))

    def search_page(
        self,
        *,
        signals: Sequence[StrategySignal],
        query: ExperimentSignalCatalogQuery,
        limit: int,
        offset: int,
    ) -> tuple[StrategySignal, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        filtered = self._filter(
            signals=signals,
            query=query,
        )

        reverse = query.sort_direction is ExperimentSignalSortDirection.DESCENDING

        ordered = tuple(
            sorted(
                filtered,
                key=lambda signal: (
                    signal.candle_close_time,
                    signal.signal_id,
                ),
                reverse=reverse,
            )
        )

        return ordered[offset : offset + limit]

    @staticmethod
    def _filter(
        *,
        signals: Sequence[StrategySignal],
        query: ExperimentSignalCatalogQuery,
    ) -> tuple[StrategySignal, ...]:
        return tuple(
            signal
            for signal in signals
            if (query.direction is None or signal.direction is query.direction)
            and (
                query.candle_close_time_from is None
                or signal.candle_close_time >= query.candle_close_time_from
            )
            and (
                query.candle_close_time_to is None
                or signal.candle_close_time <= query.candle_close_time_to
            )
        )
