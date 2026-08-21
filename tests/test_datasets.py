from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import DataIssueCode
from trd_bot.research import DatasetBuilder, InvalidDatasetError

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)


def create_candle(
    hour: int,
    *,
    received_hour: int = 15,
) -> OHLCVCandle:
    return OHLCVCandle(
        source="test-exchange",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 8, 21, hour, tzinfo=UTC),
        close_time=datetime(2026, 8, 21, hour + 1, tzinfo=UTC),
        received_at=datetime(
            2026,
            8,
            21,
            received_hour,
            tzinfo=UTC,
        ),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1000"),
        is_closed=True,
    )


def test_dataset_is_created_from_valid_candles() -> None:
    dataset = DatasetBuilder().build(
        name="BTC hourly research dataset",
        candles=[
            create_candle(10),
            create_candle(11),
        ],
    )

    assert dataset.candle_count == 2
    assert dataset.source == "test-exchange"
    assert dataset.pair.symbol == "BTC/USDT"
    assert dataset.timeframe == Timeframe.HOUR_1
    assert dataset.dataset_id.startswith("dataset-")
    assert len(dataset.checksum) == 64


def test_dataset_checksum_is_deterministic() -> None:
    first_dataset = DatasetBuilder().build(
        name="First dataset",
        candles=[
            create_candle(10, received_hour=14),
            create_candle(11, received_hour=14),
        ],
    )

    second_dataset = DatasetBuilder().build(
        name="Second dataset",
        candles=[
            create_candle(10, received_hour=15),
            create_candle(11, received_hour=15),
        ],
    )

    assert first_dataset.checksum == second_dataset.checksum
    assert first_dataset.dataset_id == second_dataset.dataset_id


def test_invalid_dataset_is_rejected() -> None:
    with pytest.raises(InvalidDatasetError) as error:
        DatasetBuilder().build(
            name="Invalid dataset",
            candles=[
                create_candle(10),
                create_candle(12),
            ],
        )

    issue_codes = {issue.code for issue in error.value.report.issues}

    assert DataIssueCode.MISSING_CANDLE in issue_codes
