from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise

from pydantic import BaseModel, ConfigDict

from trd_bot.domain.market_data import OHLCVCandle, Timeframe


class DataIssueCode(StrEnum):
    """Types of market-data quality issues."""

    EMPTY_DATA = "empty_data"
    MIXED_SERIES = "mixed_series"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    OUT_OF_ORDER = "out_of_order"
    MISSING_CANDLE = "missing_candle"
    OPEN_CANDLE = "open_candle"


class DataQualityIssue(BaseModel):
    """A single market-data quality issue."""

    model_config = ConfigDict(frozen=True)

    code: DataIssueCode
    message: str
    timestamp: datetime | None = None


class DataQualityReport(BaseModel):
    """Result of checking a candle collection."""

    model_config = ConfigDict(frozen=True)

    candles_checked: int
    issues: tuple[DataQualityIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return whether the dataset passed all checks."""

        return not self.issues


_TIMEFRAME_INTERVALS: dict[Timeframe, timedelta] = {
    Timeframe.MINUTES_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.HOURS_4: timedelta(hours=4),
    Timeframe.DAY_1: timedelta(days=1),
}


class MarketDataQualityChecker:
    """Validate a collection of OHLCV candles."""

    def check(
        self,
        candles: Sequence[OHLCVCandle],
    ) -> DataQualityReport:
        issues: list[DataQualityIssue] = []

        if not candles:
            issues.append(
                DataQualityIssue(
                    code=DataIssueCode.EMPTY_DATA,
                    message="The candle collection is empty.",
                )
            )

            return DataQualityReport(
                candles_checked=0,
                issues=tuple(issues),
            )

        reference_pair = candles[0].pair
        reference_timeframe = candles[0].timeframe
        reference_source = candles[0].source

        has_mixed_series = any(
            candle.source != reference_source
            or candle.pair != reference_pair
            or candle.timeframe != reference_timeframe
            for candle in candles[1:]
        )

        if has_mixed_series:
            issues.append(
                DataQualityIssue(
                    code=DataIssueCode.MIXED_SERIES,
                    message=("All candles must have the same source, pair, and timeframe."),
                )
            )

        seen_timestamps: set[datetime] = set()

        for candle in candles:
            if candle.open_time in seen_timestamps:
                issues.append(
                    DataQualityIssue(
                        code=DataIssueCode.DUPLICATE_TIMESTAMP,
                        message="Duplicate candle open time detected.",
                        timestamp=candle.open_time,
                    )
                )

            seen_timestamps.add(candle.open_time)

            if not candle.is_closed:
                issues.append(
                    DataQualityIssue(
                        code=DataIssueCode.OPEN_CANDLE,
                        message="An unclosed candle was detected.",
                        timestamp=candle.open_time,
                    )
                )

        for previous, current in pairwise(candles):
            if current.open_time < previous.open_time:
                issues.append(
                    DataQualityIssue(
                        code=DataIssueCode.OUT_OF_ORDER,
                        message="Candles are not in chronological order.",
                        timestamp=current.open_time,
                    )
                )

        if not has_mixed_series:
            unique_candles = {candle.open_time: candle for candle in candles}

            ordered_candles = sorted(
                unique_candles.values(),
                key=lambda candle: candle.open_time,
            )

            expected_interval = _TIMEFRAME_INTERVALS[reference_timeframe]

            for previous, current in pairwise(ordered_candles):
                actual_interval = current.open_time - previous.open_time

                if actual_interval > expected_interval:
                    missing_count = int(actual_interval / expected_interval) - 1

                    issues.append(
                        DataQualityIssue(
                            code=DataIssueCode.MISSING_CANDLE,
                            message=(
                                f"{missing_count} missing candle(s) "
                                f"detected after "
                                f"{previous.open_time.isoformat()}."
                            ),
                            timestamp=(previous.open_time + expected_interval),
                        )
                    )

        return DataQualityReport(
            candles_checked=len(candles),
            issues=tuple(issues),
        )
