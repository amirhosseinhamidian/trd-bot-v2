from decimal import Decimal

import pytest

from trd_bot.indicators import exponential_moving_average


def test_ema_is_calculated_correctly() -> None:
    result = exponential_moving_average(
        values=[
            Decimal("1"),
            Decimal("2"),
            Decimal("3"),
            Decimal("4"),
            Decimal("5"),
        ],
        period=3,
    )

    assert result == (
        None,
        None,
        Decimal("2"),
        Decimal("3"),
        Decimal("4"),
    )


def test_ema_returns_none_during_warmup() -> None:
    result = exponential_moving_average(
        values=[
            Decimal("1"),
            Decimal("2"),
        ],
        period=3,
    )

    assert result == (None, None)


def test_ema_rejects_invalid_period() -> None:
    with pytest.raises(
        ValueError,
        match="EMA period must be at least 2",
    ):
        exponential_moving_average(
            values=[Decimal("1")],
            period=1,
        )
