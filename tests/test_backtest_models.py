from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.backtesting import (
    BacktestConfig,
    BacktestEvent,
    BacktestEventType,
    ExitReason,
    PositionSide,
    build_backtest_event_id,
)
from trd_bot.domain.market_data import TradingPair

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)

EVENT_TIME = datetime(
    2026,
    8,
    21,
    12,
    tzinfo=UTC,
)

SIGNAL_ID = "signal-0123456789abcdef"


def create_event(
    *,
    event_type: BacktestEventType,
    signal_id: str | None = SIGNAL_ID,
    exit_reason: ExitReason | None = None,
) -> BacktestEvent:
    event_id = build_backtest_event_id(
        run_id="backtest-test",
        sequence_number=1,
        event_type=event_type,
        timestamp=EVENT_TIME,
    )

    return BacktestEvent(
        event_id=event_id,
        sequence_number=1,
        event_type=event_type,
        timestamp=EVENT_TIME,
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("2"),
        signal_id=signal_id,
        exit_reason=exit_reason,
    )


def test_valid_backtest_config_is_created() -> None:
    config = BacktestConfig(
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )

    assert config.starting_balance == Decimal("10000")
    assert config.allocation_fraction == Decimal("0.10")


def test_invalid_allocation_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BacktestConfig(
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("1.1"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        )


def test_position_opened_event_is_created() -> None:
    event = create_event(
        event_type=BacktestEventType.POSITION_OPENED,
    )

    assert event.signal_id == SIGNAL_ID
    assert event.exit_reason is None


def test_position_opened_requires_signal_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a signal ID",
    ):
        create_event(
            event_type=BacktestEventType.POSITION_OPENED,
            signal_id=None,
        )


def test_position_closed_requires_exit_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="requires an exit reason",
    ):
        create_event(
            event_type=BacktestEventType.POSITION_CLOSED,
        )


def test_backtest_event_id_is_deterministic() -> None:
    first_id = build_backtest_event_id(
        run_id="backtest-test",
        sequence_number=1,
        event_type=BacktestEventType.POSITION_OPENED,
        timestamp=EVENT_TIME,
    )

    second_id = build_backtest_event_id(
        run_id="backtest-test",
        sequence_number=1,
        event_type=BacktestEventType.POSITION_OPENED,
        timestamp=EVENT_TIME,
    )

    assert first_id == second_id
    assert first_id.startswith("event-")
