from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from itertools import pairwise
from math import ceil
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import OHLCVCandle, Timeframe


class DataIssueCode(StrEnum):
    """Types of market-data quality issues."""

    EMPTY_DATA = "empty_data"
    MIXED_SERIES = "mixed_series"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    OUT_OF_ORDER = "out_of_order"
    MISSING_CANDLE = "missing_candle"
    OPEN_CANDLE = "open_candle"
    INCOMPLETE_START = "incomplete_start"
    INCOMPLETE_END = "incomplete_end"
    OUTSIDE_REQUESTED_RANGE = "outside_requested_range"
    UNALIGNED_CANDLE = "unaligned_candle"


class DataQualityIssue(BaseModel):
    """A single market-data quality issue."""

    model_config = ConfigDict(frozen=True)

    code: DataIssueCode
    message: str
    timestamp: datetime | None = None


class DataCoverageReport(BaseModel):
    """Deterministic candle-open coverage for one requested half-open range."""

    model_config = ConfigDict(frozen=True)

    requested_start_time: datetime
    requested_end_time: datetime
    expected_first_open_time: datetime | None
    expected_last_open_time: datetime | None
    actual_first_open_time: datetime | None
    actual_last_close_time: datetime | None
    expected_candles: int = Field(ge=0)
    received_candles: int = Field(ge=0)
    missing_candles: int = Field(ge=0)
    coverage_percent: float = Field(ge=0, le=100)
    complete: bool

    @field_validator(
        "requested_start_time",
        "requested_end_time",
        "expected_first_open_time",
        "expected_last_open_time",
        "actual_first_open_time",
        "actual_last_close_time",
    )
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("coverage timestamps must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.requested_end_time <= self.requested_start_time:
            raise ValueError("coverage end time must be after start time")
        if self.received_candles > self.expected_candles:
            raise ValueError("received candle count cannot exceed expected candle count")
        if self.missing_candles != self.expected_candles - self.received_candles:
            raise ValueError("coverage missing candle count is inconsistent")
        expected_percent = (
            round((self.received_candles / self.expected_candles) * 100, 2)
            if self.expected_candles
            else 0.0
        )
        if self.coverage_percent != expected_percent:
            raise ValueError("coverage percentage is inconsistent")
        if self.complete != (self.expected_candles > 0 and self.missing_candles == 0):
            raise ValueError("coverage completeness is inconsistent")
        return self


QUALITY_SCORE_VERSION: Final = "quality-score-v1"
QUALITY_ACCEPTANCE_POLICY_VERSION: Final = "strict-quality-v1"


class DataQualityScore(BaseModel):
    """Versioned, non-compensating score for normalized market data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score_version: Literal["quality-score-v1"] = QUALITY_SCORE_VERSION
    score_percent: float = Field(ge=0, le=100)
    coverage_percent: float = Field(ge=0, le=100)
    integrity_percent: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_formula(self) -> Self:
        expected = round(
            (self.coverage_percent * self.integrity_percent) / 100,
            2,
        )
        if self.score_percent != expected:
            raise ValueError("quality score does not match its versioned formula")
        return self


class DataQualityAcceptance(BaseModel):
    """Persisted decision made by one explicit quality-acceptance policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: Literal["strict-quality-v1"] = QUALITY_ACCEPTANCE_POLICY_VERSION
    accepted: bool
    minimum_score_percent: float = Field(default=100.0, ge=100, le=100)
    blocking_issue_codes: tuple[DataIssueCode, ...] = ()


class DataQualityReport(BaseModel):
    """Result of checking a candle collection."""

    model_config = ConfigDict(frozen=True)

    candles_checked: int
    issues: tuple[DataQualityIssue, ...] = ()
    coverage: DataCoverageReport | None = None
    score: DataQualityScore | None = None
    acceptance: DataQualityAcceptance | None = None

    @model_validator(mode="after")
    def validate_score_and_acceptance(self) -> Self:
        if (self.score is None) != (self.acceptance is None):
            raise ValueError("quality score and acceptance must be recorded together")

        if self.score is None or self.acceptance is None:
            return self

        blocking_codes = tuple(dict.fromkeys(issue.code for issue in self.issues))
        if self.acceptance.blocking_issue_codes != blocking_codes:
            raise ValueError("quality acceptance does not match report issues")

        expected_accepted = (
            not blocking_codes and self.score.score_percent >= self.acceptance.minimum_score_percent
        )
        if self.acceptance.accepted != expected_accepted:
            raise ValueError("quality acceptance decision is inconsistent")

        return self

    @property
    def is_valid(self) -> bool:
        """Return whether the dataset passed all checks."""

        if self.acceptance is not None:
            return self.acceptance.accepted
        return not self.issues


_TIMEFRAME_INTERVALS: dict[Timeframe, timedelta] = {
    Timeframe.MINUTES_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.HOURS_4: timedelta(hours=4),
    Timeframe.DAY_1: timedelta(days=1),
}
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_INTEGRITY_ISSUE_CODES = frozenset(
    {
        DataIssueCode.EMPTY_DATA,
        DataIssueCode.MIXED_SERIES,
        DataIssueCode.DUPLICATE_TIMESTAMP,
        DataIssueCode.OUT_OF_ORDER,
        DataIssueCode.OPEN_CANDLE,
        DataIssueCode.OUTSIDE_REQUESTED_RANGE,
        DataIssueCode.UNALIGNED_CANDLE,
    }
)


def _to_epoch_microseconds(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("coverage timestamps must include timezone information")
    delta = value.astimezone(UTC) - _EPOCH
    return ((delta.days * 86_400) + delta.seconds) * 1_000_000 + delta.microseconds


def _from_epoch_microseconds(value: int) -> datetime:
    return _EPOCH + timedelta(microseconds=value)


def _ceil_div(value: int, divisor: int) -> int:
    return -(-value // divisor)


def _expected_open_range(
    *,
    start_time: datetime,
    end_time: datetime,
    timeframe: Timeframe,
) -> tuple[datetime | None, datetime | None, int, int, int]:
    start_microseconds = _to_epoch_microseconds(start_time)
    end_microseconds = _to_epoch_microseconds(end_time)
    normalized_start = start_time.astimezone(UTC)
    normalized_end = end_time.astimezone(UTC)
    if normalized_end <= normalized_start:
        raise ValueError("coverage end time must be after start time")

    interval_microseconds = int(_TIMEFRAME_INTERVALS[timeframe].total_seconds() * 1_000_000)
    first_index = _ceil_div(start_microseconds, interval_microseconds)
    end_index = _ceil_div(end_microseconds, interval_microseconds)
    expected_candles = max(0, end_index - first_index)
    if expected_candles == 0:
        return None, None, 0, first_index, interval_microseconds

    return (
        _from_epoch_microseconds(first_index * interval_microseconds),
        _from_epoch_microseconds((end_index - 1) * interval_microseconds),
        expected_candles,
        first_index,
        interval_microseconds,
    )


class MarketDataQualityChecker:
    """Validate a collection of OHLCV candles."""

    def check(
        self,
        candles: Sequence[OHLCVCandle],
        *,
        requested_start_time: datetime | None = None,
        requested_end_time: datetime | None = None,
        requested_timeframe: Timeframe | None = None,
    ) -> DataQualityReport:
        issues: list[DataQualityIssue] = []
        coverage_requested = (
            requested_start_time is not None,
            requested_end_time is not None,
            requested_timeframe is not None,
        )
        if any(coverage_requested) and not all(coverage_requested):
            raise ValueError("coverage checking requires start, end, and timeframe")

        coverage: DataCoverageReport | None = None

        if not candles:
            issues.append(
                DataQualityIssue(
                    code=DataIssueCode.EMPTY_DATA,
                    message="The candle collection is empty.",
                )
            )

            empty_coverage: DataCoverageReport | None = None
            if all(coverage_requested):
                assert requested_start_time is not None
                assert requested_end_time is not None
                assert requested_timeframe is not None
                empty_coverage = self._coverage_report(
                    candles=candles,
                    start_time=requested_start_time,
                    end_time=requested_end_time,
                    timeframe=requested_timeframe,
                )

            return self._build_report(
                candles=candles,
                issues=issues,
                coverage=empty_coverage,
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

        if all(coverage_requested):
            assert requested_start_time is not None
            assert requested_end_time is not None
            assert requested_timeframe is not None
            coverage = self._coverage_report(
                candles=candles,
                start_time=requested_start_time,
                end_time=requested_end_time,
                timeframe=requested_timeframe,
            )
            expected_first = coverage.expected_first_open_time
            expected_last = coverage.expected_last_open_time
            interval_microseconds = int(
                _TIMEFRAME_INTERVALS[requested_timeframe].total_seconds() * 1_000_000
            )
            actual_opens = {
                candle.open_time.astimezone(UTC)
                for candle in candles
                if candle.timeframe == requested_timeframe
                and _to_epoch_microseconds(candle.open_time) % interval_microseconds == 0
                and requested_start_time.astimezone(UTC)
                <= candle.open_time.astimezone(UTC)
                < requested_end_time.astimezone(UTC)
            }

            if expected_first is not None and expected_first not in actual_opens:
                first_actual = coverage.actual_first_open_time
                missing_at_start = (
                    coverage.expected_candles
                    if first_actual is None
                    else int(
                        (first_actual - expected_first) / _TIMEFRAME_INTERVALS[requested_timeframe]
                    )
                )
                issues.append(
                    DataQualityIssue(
                        code=DataIssueCode.INCOMPLETE_START,
                        message=(
                            f"{missing_at_start} candle(s) are missing at the start "
                            "of the requested range."
                        ),
                        timestamp=expected_first,
                    )
                )

            if expected_last is not None and expected_last not in actual_opens:
                last_actual = max(
                    (value for value in actual_opens if value <= expected_last),
                    default=None,
                )
                missing_at_end = (
                    coverage.expected_candles
                    if last_actual is None
                    else int(
                        (expected_last - last_actual) / _TIMEFRAME_INTERVALS[requested_timeframe]
                    )
                )
                issues.append(
                    DataQualityIssue(
                        code=DataIssueCode.INCOMPLETE_END,
                        message=(
                            f"{missing_at_end} candle(s) are missing at the end "
                            "of the requested range."
                        ),
                        timestamp=expected_last,
                    )
                )

            normalized_start = requested_start_time.astimezone(UTC)
            normalized_end = requested_end_time.astimezone(UTC)
            for candle in candles:
                normalized_open = candle.open_time.astimezone(UTC)
                if not normalized_start <= normalized_open < normalized_end:
                    issues.append(
                        DataQualityIssue(
                            code=DataIssueCode.OUTSIDE_REQUESTED_RANGE,
                            message="A candle is outside the requested half-open range.",
                            timestamp=normalized_open,
                        )
                    )
                if _to_epoch_microseconds(normalized_open) % interval_microseconds != 0:
                    issues.append(
                        DataQualityIssue(
                            code=DataIssueCode.UNALIGNED_CANDLE,
                            message="A candle is not aligned to its UTC timeframe boundary.",
                            timestamp=normalized_open,
                        )
                    )

        return self._build_report(
            candles=candles,
            issues=issues,
            coverage=coverage,
        )

    @staticmethod
    def _build_report(
        *,
        candles: Sequence[OHLCVCandle],
        issues: Sequence[DataQualityIssue],
        coverage: DataCoverageReport | None,
    ) -> DataQualityReport:
        coverage_percent = MarketDataQualityChecker._score_coverage_percent(
            candles=candles,
            coverage=coverage,
        )
        integrity_percent = MarketDataQualityChecker._score_integrity_percent(
            candles=candles,
            issues=issues,
        )
        score = DataQualityScore(
            score_percent=round((coverage_percent * integrity_percent) / 100, 2),
            coverage_percent=coverage_percent,
            integrity_percent=integrity_percent,
        )
        blocking_codes = tuple(dict.fromkeys(issue.code for issue in issues))
        acceptance = DataQualityAcceptance(
            accepted=not blocking_codes and score.score_percent == 100.0,
            blocking_issue_codes=blocking_codes,
        )

        return DataQualityReport(
            candles_checked=len(candles),
            issues=tuple(issues),
            coverage=coverage,
            score=score,
            acceptance=acceptance,
        )

    @staticmethod
    def _score_coverage_percent(
        *,
        candles: Sequence[OHLCVCandle],
        coverage: DataCoverageReport | None,
    ) -> float:
        if coverage is not None:
            return coverage.coverage_percent
        if not candles:
            return 0.0

        reference_timeframe = candles[0].timeframe
        interval = _TIMEFRAME_INTERVALS[reference_timeframe]
        unique_open_times = sorted(
            {
                candle.open_time.astimezone(UTC)
                for candle in candles
                if candle.timeframe is reference_timeframe
            }
        )
        if not unique_open_times:
            return 0.0

        expected_candles = 1 + sum(
            max(1, ceil((current - previous) / interval))
            for previous, current in pairwise(unique_open_times)
        )
        return round((len(unique_open_times) / expected_candles) * 100, 2)

    @staticmethod
    def _score_integrity_percent(
        *,
        candles: Sequence[OHLCVCandle],
        issues: Sequence[DataQualityIssue],
    ) -> float:
        if not candles:
            return 0.0

        integrity_issues = tuple(issue for issue in issues if issue.code in _INTEGRITY_ISSUE_CODES)
        if any(issue.timestamp is None for issue in integrity_issues):
            return 0.0

        affected_timestamps = {
            issue.timestamp.astimezone(UTC)
            for issue in integrity_issues
            if issue.timestamp is not None
        }
        affected_candles = sum(
            candle.open_time.astimezone(UTC) in affected_timestamps for candle in candles
        )
        unaffected_candles = max(0, len(candles) - affected_candles)
        return round((unaffected_candles / len(candles)) * 100, 2)

    @staticmethod
    def _coverage_report(
        *,
        candles: Sequence[OHLCVCandle],
        start_time: datetime,
        end_time: datetime,
        timeframe: Timeframe,
    ) -> DataCoverageReport:
        expected_first, expected_last, expected_count, first_index, interval_microseconds = (
            _expected_open_range(
                start_time=start_time,
                end_time=end_time,
                timeframe=timeframe,
            )
        )
        end_index = first_index + expected_count
        candles_by_open_time = {
            candle.open_time.astimezone(UTC): candle
            for candle in candles
            if candle.timeframe is timeframe
            and _to_epoch_microseconds(candle.open_time) % interval_microseconds == 0
            and first_index
            <= _to_epoch_microseconds(candle.open_time) // interval_microseconds
            < end_index
        }
        ordered = sorted(candles_by_open_time.values(), key=lambda candle: candle.open_time)
        received_count = len(ordered)
        missing_count = expected_count - received_count
        coverage_percent = (
            round((received_count / expected_count) * 100, 2) if expected_count else 0.0
        )

        return DataCoverageReport(
            requested_start_time=start_time.astimezone(UTC),
            requested_end_time=end_time.astimezone(UTC),
            expected_first_open_time=expected_first,
            expected_last_open_time=expected_last,
            actual_first_open_time=ordered[0].open_time if ordered else None,
            actual_last_close_time=ordered[-1].close_time if ordered else None,
            expected_candles=expected_count,
            received_candles=received_count,
            missing_candles=missing_count,
            coverage_percent=coverage_percent,
            complete=expected_count > 0 and missing_count == 0,
        )
