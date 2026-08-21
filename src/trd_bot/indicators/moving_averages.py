from collections.abc import Sequence
from decimal import Decimal


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
