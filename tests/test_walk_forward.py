from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import (
    DatasetBuilder,
    DatasetSnapshot,
    WalkForwardConfig,
    WalkForwardMode,
    WalkForwardPlanner,
    build_walk_forward_plan_id,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")


def create_dataset(candle_count: int) -> DatasetSnapshot:
    start = datetime(2026, 8, 1, 10, tzinfo=UTC)
    candles = []

    for index in range(candle_count):
        price = Decimal("100") + Decimal(index)
        open_time = start + timedelta(hours=index)
        candles.append(
            OHLCVCandle(
                source="test-exchange",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                received_at=start + timedelta(days=2),
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(name="Walk-forward dataset", candles=candles)


def test_rolling_plan_keeps_training_window_size_fixed() -> None:
    dataset = create_dataset(10)
    config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
        mode=WalkForwardMode.ROLLING,
    )

    plan = WalkForwardPlanner().plan(dataset=dataset, config=config)

    assert len(plan.folds) == 3
    assert [
        (
            fold.train_start_index,
            fold.train_end_index,
            fold.test_start_index,
            fold.test_end_index,
        )
        for fold in plan.folds
    ] == [
        (0, 4, 4, 6),
        (2, 6, 6, 8),
        (4, 8, 8, 10),
    ]


def test_expanding_plan_grows_training_window_from_start() -> None:
    dataset = create_dataset(10)
    config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
        mode=WalkForwardMode.EXPANDING,
    )

    plan = WalkForwardPlanner().plan(dataset=dataset, config=config)

    assert [(fold.train_start_index, fold.train_end_index) for fold in plan.folds] == [
        (0, 4),
        (0, 6),
        (0, 8),
    ]


def test_gap_separates_training_and_test_windows() -> None:
    dataset = create_dataset(11)
    config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
        gap_candles=1,
    )

    plan = WalkForwardPlanner().plan(dataset=dataset, config=config)

    assert len(plan.folds) == 3
    assert all(fold.test_start_index - fold.train_end_index == 1 for fold in plan.folds)
    assert all(fold.train_end_time < fold.test_start_time for fold in plan.folds)


def test_incomplete_final_test_window_is_excluded() -> None:
    dataset = create_dataset(9)
    config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
    )

    plan = WalkForwardPlanner().plan(dataset=dataset, config=config)

    assert len(plan.folds) == 2
    assert plan.folds[-1].test_end_index == 8


def test_dataset_too_short_for_one_fold_is_rejected() -> None:
    dataset = create_dataset(5)
    config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
    )

    with pytest.raises(ValueError, match="at least 6 candles"):
        WalkForwardPlanner().plan(dataset=dataset, config=config)


def test_walk_forward_plan_is_deterministic() -> None:
    dataset = create_dataset(10)
    config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
    )

    first = WalkForwardPlanner().plan(dataset=dataset, config=config)
    second = WalkForwardPlanner().plan(dataset=dataset, config=config)

    assert first == second
    assert first.plan_id == build_walk_forward_plan_id(
        dataset_id=dataset.dataset_id,
        config=config,
    )


def test_overlapping_test_windows_are_rejected() -> None:
    with pytest.raises(ValidationError, match="step candles must be at least test candles"):
        WalkForwardConfig(
            train_candles=4,
            test_candles=3,
            step_candles=2,
        )


def test_every_test_window_starts_after_its_training_window() -> None:
    dataset = create_dataset(12)
    config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
    )

    plan = WalkForwardPlanner().plan(dataset=dataset, config=config)

    for fold in plan.folds:
        assert fold.train_end_index <= fold.test_start_index
        assert fold.train_end_time <= fold.test_start_time
