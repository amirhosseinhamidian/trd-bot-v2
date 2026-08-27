from datetime import UTC, datetime

from tests.test_candidate_position_monitoring import candle
from trd_bot.market_data.quality import (
    DataIssueCode,
    DataQualityIssue,
    DataQualityReport,
)
from trd_bot.research.data_quality_exit import (
    CandidateDataQualityExitDirectiveProducer,
)
from trd_bot.research.position_monitoring import CandidateExitReason


def test_valid_quality_report_produces_no_exit_directive() -> None:
    directives = CandidateDataQualityExitDirectiveProducer.from_report(
        report=DataQualityReport(
            candles_checked=2,
        ),
        monitoring_candles=(
            candle(13, high_price="101", low_price="99", close_price="100"),
            candle(14, high_price="101", low_price="99", close_price="100"),
        ),
    )

    assert directives == ()


def test_missing_candle_maps_to_first_closed_candle_after_gap() -> None:
    monitoring_candles = (
        candle(13, high_price="101", low_price="99", close_price="100"),
        candle(15, high_price="101", low_price="99", close_price="100"),
    )

    directives = CandidateDataQualityExitDirectiveProducer().produce(
        observed_candles=monitoring_candles,
        monitoring_candles=monitoring_candles,
    )

    assert len(directives) == 1
    assert directives[0].reason is CandidateExitReason.DATA_UNRELIABLE
    assert directives[0].occurred_at == datetime(2026, 8, 26, 16, tzinfo=UTC)


def test_quality_issue_without_timestamp_exits_on_first_closed_candle() -> None:
    directives = CandidateDataQualityExitDirectiveProducer.from_report(
        report=DataQualityReport(
            candles_checked=2,
            issues=(
                DataQualityIssue(
                    code=DataIssueCode.MIXED_SERIES,
                    message="mixed series",
                ),
            ),
        ),
        monitoring_candles=(
            candle(13, high_price="101", low_price="99", close_price="100"),
            candle(14, high_price="101", low_price="99", close_price="100"),
        ),
    )

    assert len(directives) == 1
    assert directives[0].reason is CandidateExitReason.DATA_UNRELIABLE
    assert directives[0].occurred_at == datetime(2026, 8, 26, 14, tzinfo=UTC)


def test_multiple_quality_issues_choose_earliest_actionable_exit() -> None:
    directives = CandidateDataQualityExitDirectiveProducer.from_report(
        report=DataQualityReport(
            candles_checked=3,
            issues=(
                DataQualityIssue(
                    code=DataIssueCode.MISSING_CANDLE,
                    message="later gap",
                    timestamp=datetime(2026, 8, 26, 15, tzinfo=UTC),
                ),
                DataQualityIssue(
                    code=DataIssueCode.DUPLICATE_TIMESTAMP,
                    message="earlier duplicate",
                    timestamp=datetime(2026, 8, 26, 14, tzinfo=UTC),
                ),
            ),
        ),
        monitoring_candles=(
            candle(13, high_price="101", low_price="99", close_price="100"),
            candle(14, high_price="101", low_price="99", close_price="100"),
            candle(15, high_price="101", low_price="99", close_price="100"),
        ),
    )

    assert len(directives) == 1
    assert directives[0].occurred_at == datetime(2026, 8, 26, 15, tzinfo=UTC)


def test_issue_after_monitoring_horizon_produces_no_directive() -> None:
    directives = CandidateDataQualityExitDirectiveProducer.from_report(
        report=DataQualityReport(
            candles_checked=1,
            issues=(
                DataQualityIssue(
                    code=DataIssueCode.MISSING_CANDLE,
                    message="outside horizon",
                    timestamp=datetime(2026, 8, 26, 17, tzinfo=UTC),
                ),
            ),
        ),
        monitoring_candles=(
            candle(13, high_price="101", low_price="99", close_price="100"),
            candle(14, high_price="101", low_price="99", close_price="100"),
        ),
    )

    assert directives == ()
