from collections.abc import Sequence
from decimal import Decimal


def simple_moving_average(
    values: Sequence[Decimal],
    period: int,
) -> tuple[Decimal | None, ...]:
    """Calculate a simple moving average over a fixed-size window."""

    if period < 2:
        raise ValueError("SMA period must be at least 2")

    if not values:
        return ()

    result: list[Decimal | None] = [None] * len(values)

    if len(values) < period:
        return tuple(result)

    period_decimal = Decimal(period)
    window_total = sum(values[:period], start=Decimal("0"))

    result[period - 1] = window_total / period_decimal

    for index in range(period, len(values)):
        window_total += values[index] - values[index - period]
        result[index] = window_total / period_decimal

    return tuple(result)


def exponential_moving_average(
    values: Sequence[Decimal],
    period: int,
) -> tuple[Decimal | None, ...]:
    """Calculate an EMA using an initial simple moving average."""

    if period < 2:
        raise ValueError("EMA period must be at least 2")

    if not values:
        return ()

    result: list[Decimal | None] = [None] * len(values)

    if len(values) < period:
        return tuple(result)

    initial_average = sum(values[:period], start=Decimal("0")) / Decimal(period)

    result[period - 1] = initial_average

    multiplier = Decimal("2") / Decimal(period + 1)
    previous_ema = initial_average

    for index in range(period, len(values)):
        current_ema = (values[index] - previous_ema) * multiplier + previous_ema

        result[index] = current_ema
        previous_ema = current_ema

    return tuple(result)
