from collections.abc import Sequence
from datetime import datetime

from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.market_data.quality import (
    DataQualityIssue,
    DataQualityReport,
    MarketDataQualityChecker,
)
from trd_bot.research.position_monitoring import (
    CandidateExitDirective,
    CandidateExitReason,
)


class CandidateDataQualityExitDirectiveProducer:
    """Convert detected market-data quality failures into offline exit directives."""

    def __init__(
        self,
        *,
        quality_checker: MarketDataQualityChecker | None = None,
    ) -> None:
        self._quality_checker = quality_checker or MarketDataQualityChecker()

    def produce(
        self,
        *,
        observed_candles: Sequence[OHLCVCandle],
        monitoring_candles: Sequence[OHLCVCandle],
    ) -> tuple[CandidateExitDirective, ...]:
        report = self._quality_checker.check(observed_candles)
        return self.from_report(
            report=report,
            monitoring_candles=monitoring_candles,
        )

    @staticmethod
    def from_report(
        *,
        report: DataQualityReport,
        monitoring_candles: Sequence[OHLCVCandle],
    ) -> tuple[CandidateExitDirective, ...]:
        if report.is_valid:
            return ()

        closed_candles = tuple(
            sorted(
                (candle for candle in monitoring_candles if candle.is_closed),
                key=lambda candle: (candle.open_time, candle.close_time),
            )
        )
        if not closed_candles:
            return ()

        directive_times = tuple(
            directive_time
            for issue in report.issues
            if (
                directive_time := CandidateDataQualityExitDirectiveProducer._directive_time(
                    issue=issue,
                    closed_candles=closed_candles,
                )
            )
            is not None
        )
        if not directive_times:
            return ()

        return (
            CandidateExitDirective(
                reason=CandidateExitReason.DATA_UNRELIABLE,
                occurred_at=min(directive_times),
            ),
        )

    @staticmethod
    def _directive_time(
        *,
        issue: DataQualityIssue,
        closed_candles: tuple[OHLCVCandle, ...],
    ) -> datetime | None:
        if issue.timestamp is None:
            return closed_candles[0].close_time

        matching = next(
            (candle for candle in closed_candles if candle.open_time >= issue.timestamp),
            None,
        )
        if matching is None:
            return None

        return matching.close_time
