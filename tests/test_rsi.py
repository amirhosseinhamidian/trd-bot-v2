from decimal import Decimal

import pytest

from trd_bot.indicators import relative_strength_index


def test_rsi_reaches_100_when_initial_window_has_only_gains() -> None:
    result = relative_strength_index(
        values=[
            Decimal("1"),
            Decimal("2"),
            Decimal("3"),
            Decimal("4"),
        ],
        period=3,
    )

    assert result == (
        None,
        None,
        None,
        Decimal("100"),
    )


def test_rsi_reaches_zero_when_initial_window_has_only_losses() -> None:
    result = relative_strength_index(
        values=[
            Decimal("4"),
            Decimal("3"),
            Decimal("2"),
            Decimal("1"),
        ],
        period=3,
    )

    assert result == (
        None,
        None,
        None,
        Decimal("0"),
    )


def test_rsi_is_neutral_when_prices_are_flat() -> None:
    result = relative_strength_index(
        values=[
            Decimal("5"),
            Decimal("5"),
            Decimal("5"),
            Decimal("5"),
        ],
        period=3,
    )

    assert result[-1] == Decimal("50")


def test_rsi_returns_none_during_warmup() -> None:
    result = relative_strength_index(
        values=[
            Decimal("1"),
            Decimal("2"),
            Decimal("3"),
        ],
        period=3,
    )

    assert result == (None, None, None)


def test_rsi_rejects_invalid_period() -> None:
    with pytest.raises(
        ValueError,
        match="RSI period must be at least 2",
    ):
        relative_strength_index(
            values=[Decimal("1")],
            period=1,
        )
