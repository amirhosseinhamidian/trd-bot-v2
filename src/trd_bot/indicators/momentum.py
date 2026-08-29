from collections.abc import Sequence
from decimal import Decimal


def relative_strength_index(
    values: Sequence[Decimal],
    period: int = 14,
) -> tuple[Decimal | None, ...]:
    """Calculate Wilder's RSI for a sequence of values."""

    if period < 2:
        raise ValueError("RSI period must be at least 2")

    if not values:
        return ()

    result: list[Decimal | None] = [None] * len(values)

    if len(values) <= period:
        return tuple(result)

    gains: list[Decimal] = []
    losses: list[Decimal] = []

    for index in range(1, period + 1):
        change = values[index] - values[index - 1]

        gains.append(max(change, Decimal("0")))
        losses.append(max(-change, Decimal("0")))

    divisor = Decimal(period)
    average_gain = sum(gains, start=Decimal("0")) / divisor
    average_loss = sum(losses, start=Decimal("0")) / divisor

    result[period] = _rsi_value(
        average_gain=average_gain,
        average_loss=average_loss,
    )

    smoothing_weight = Decimal(period - 1)

    for index in range(period + 1, len(values)):
        change = values[index] - values[index - 1]
        gain = max(change, Decimal("0"))
        loss = max(-change, Decimal("0"))

        average_gain = (average_gain * smoothing_weight + gain) / divisor
        average_loss = (average_loss * smoothing_weight + loss) / divisor

        result[index] = _rsi_value(
            average_gain=average_gain,
            average_loss=average_loss,
        )

    return tuple(result)


def _rsi_value(
    *,
    average_gain: Decimal,
    average_loss: Decimal,
) -> Decimal:
    if average_gain == 0 and average_loss == 0:
        return Decimal("50")

    if average_loss == 0:
        return Decimal("100")

    if average_gain == 0:
        return Decimal("0")

    relative_strength = average_gain / average_loss

    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))
