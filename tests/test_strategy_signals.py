from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.strategies import (
    SignalDirection,
    StrategyFeature,
    StrategySignal,
    build_signal_id,
)

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)

OPEN_TIME = datetime(2026, 8, 21, 10, tzinfo=UTC)
CLOSE_TIME = datetime(2026, 8, 21, 11, tzinfo=UTC)


def create_signal(
    *,
    direction: SignalDirection,
    score: Decimal,
) -> StrategySignal:
    signal_id = build_signal_id(
        strategy_name="test-strategy",
        strategy_version="1.0.0",
        dataset_id="dataset-test",
        candle_close_time=CLOSE_TIME,
        direction=direction,
    )

    return StrategySignal(
        signal_id=signal_id,
        strategy_name="test-strategy",
        strategy_version="1.0.0",
        dataset_id="dataset-test",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        candle_open_time=OPEN_TIME,
        candle_close_time=CLOSE_TIME,
        generated_at=CLOSE_TIME,
        direction=direction,
        score=score,
        reason="Test research signal.",
        features=(
            StrategyFeature(
                name="test_feature",
                value=Decimal("1.25"),
            ),
        ),
    )


def test_valid_long_signal_is_created() -> None:
    signal = create_signal(
        direction=SignalDirection.LONG,
        score=Decimal("0.75"),
    )

    assert signal.direction == SignalDirection.LONG
    assert signal.score == Decimal("0.75")
    assert signal.signal_id.startswith("signal-")
    assert len(signal.features) == 1


def test_long_signal_rejects_negative_score() -> None:
    with pytest.raises(
        ValidationError,
        match="long signal score",
    ):
        create_signal(
            direction=SignalDirection.LONG,
            score=Decimal("-0.50"),
        )


def test_short_signal_rejects_positive_score() -> None:
    with pytest.raises(
        ValidationError,
        match="short signal score",
    ):
        create_signal(
            direction=SignalDirection.SHORT,
            score=Decimal("0.50"),
        )


def test_neutral_signal_rejects_nonzero_score() -> None:
    with pytest.raises(
        ValidationError,
        match="neutral signal score",
    ):
        create_signal(
            direction=SignalDirection.NEUTRAL,
            score=Decimal("0.10"),
        )
