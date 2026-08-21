from datetime import UTC, datetime
from decimal import Decimal

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import DataIssueCode, MarketDataQualityChecker

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)


def create_candle(
    hour: int,
    *,
    is_closed: bool = True,
) -> OHLCVCandle:
    return OHLCVCandle(
        source="test-exchange",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 8, 21, hour, tzinfo=UTC),
        close_time=datetime(2026, 8, 21, hour + 1, tzinfo=UTC),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1000"),
        is_closed=is_closed,
    )


def issue_codes(
    candles: list[OHLCVCandle],
) -> set[DataIssueCode]:
    report = MarketDataQualityChecker().check(candles)

    return {issue.code for issue in report.issues}


def test_valid_candles_pass_quality_check() -> None:
    report = MarketDataQualityChecker().check(
        [
            create_candle(10),
            create_candle(11),
            create_candle(12),
        ]
    )

    assert report.is_valid is True
    assert report.candles_checked == 3
    assert report.issues == ()


def test_empty_collection_is_rejected() -> None:
    report = MarketDataQualityChecker().check([])

    assert report.is_valid is False
    assert DataIssueCode.EMPTY_DATA in {issue.code for issue in report.issues}


def test_duplicate_timestamp_is_detected() -> None:
    codes = issue_codes(
        [
            create_candle(10),
            create_candle(10),
        ]
    )

    assert DataIssueCode.DUPLICATE_TIMESTAMP in codes


def test_out_of_order_candles_are_detected() -> None:
    codes = issue_codes(
        [
            create_candle(11),
            create_candle(10),
        ]
    )

    assert DataIssueCode.OUT_OF_ORDER in codes


def test_missing_candle_is_detected() -> None:
    codes = issue_codes(
        [
            create_candle(10),
            create_candle(12),
        ]
    )

    assert DataIssueCode.MISSING_CANDLE in codes


def test_open_candle_is_detected() -> None:
    codes = issue_codes(
        [
            create_candle(10, is_closed=False),
        ]
    )

    assert DataIssueCode.OPEN_CANDLE in codes
