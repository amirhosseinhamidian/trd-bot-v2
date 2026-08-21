from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import (
    DatasetBuilder,
    DatasetSnapshot,
    WalkForwardConfig,
    WalkForwardDatasetMaterializer,
    WalkForwardMode,
    WalkForwardPlan,
    WalkForwardPlanner,
    build_walk_forward_split_id,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
CREATED_AT = datetime(2026, 8, 22, 10, tzinfo=UTC)


def create_dataset(candle_count: int, *, price_offset: int = 0) -> DatasetSnapshot:
    start = datetime(2026, 8, 1, 10, tzinfo=UTC)
    candles = []

    for index in range(candle_count):
        price = Decimal("100") + Decimal(index + price_offset)
        open_time = start + timedelta(hours=index)
        candles.append(
            OHLCVCandle(
                source="test-exchange",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                received_at=CREATED_AT,
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(
        name="Materialization source",
        candles=candles,
        created_at=CREATED_AT,
    )


def build_plan(
    dataset: DatasetSnapshot,
    *,
    mode: WalkForwardMode = WalkForwardMode.ROLLING,
    gap_candles: int = 1,
) -> WalkForwardPlan:
    return WalkForwardPlanner().plan(
        dataset=dataset,
        config=WalkForwardConfig(
            train_candles=4,
            test_candles=2,
            step_candles=2,
            gap_candles=gap_candles,
            mode=mode,
        ),
    )


def test_materializer_slices_train_and_test_and_excludes_gap() -> None:
    dataset = create_dataset(11)
    plan = build_plan(dataset)

    materialization = WalkForwardDatasetMaterializer().materialize(
        dataset=dataset,
        plan=plan,
    )

    first = materialization.splits[0]
    assert first.train_dataset.candles == dataset.candles[0:4]
    assert first.test_dataset.candles == dataset.candles[5:7]
    assert dataset.candles[4] not in first.train_dataset.candles
    assert dataset.candles[4] not in first.test_dataset.candles


def test_expanding_materialization_grows_training_datasets() -> None:
    dataset = create_dataset(11)
    plan = build_plan(dataset, mode=WalkForwardMode.EXPANDING)

    materialization = WalkForwardDatasetMaterializer().materialize(
        dataset=dataset,
        plan=plan,
    )

    assert [split.train_dataset.candle_count for split in materialization.splits] == [
        4,
        6,
        8,
    ]
    assert all(split.test_dataset.candle_count == 2 for split in materialization.splits)


def test_materialized_datasets_preserve_source_metadata() -> None:
    dataset = create_dataset(11)
    plan = build_plan(dataset)

    split = (
        WalkForwardDatasetMaterializer()
        .materialize(
            dataset=dataset,
            plan=plan,
        )
        .splits[0]
    )

    for child in (split.train_dataset, split.test_dataset):
        assert child.source == dataset.source
        assert child.pair == dataset.pair
        assert child.timeframe == dataset.timeframe
        assert child.created_at == dataset.created_at


def test_materialization_is_fully_deterministic() -> None:
    dataset = create_dataset(11)
    plan = build_plan(dataset)
    materializer = WalkForwardDatasetMaterializer()

    first = materializer.materialize(dataset=dataset, plan=plan)
    second = materializer.materialize(dataset=dataset, plan=plan)

    assert first == second
    assert first.splits[0].split_id == build_walk_forward_split_id(
        source_dataset_id=dataset.dataset_id,
        plan_id=plan.plan_id,
        fold_number=1,
        train_dataset_id=first.splits[0].train_dataset.dataset_id,
        test_dataset_id=first.splits[0].test_dataset.dataset_id,
    )


def test_materialized_boundaries_match_their_fold() -> None:
    dataset = create_dataset(11)
    plan = build_plan(dataset)

    materialization = WalkForwardDatasetMaterializer().materialize(
        dataset=dataset,
        plan=plan,
    )

    for split in materialization.splits:
        assert split.train_dataset.start_time == split.fold.train_start_time
        assert split.train_dataset.end_time == split.fold.train_end_time
        assert split.test_dataset.start_time == split.fold.test_start_time
        assert split.test_dataset.end_time == split.fold.test_end_time
        assert split.train_dataset.end_time < split.test_dataset.start_time


def test_materializer_rejects_plan_from_another_dataset() -> None:
    dataset = create_dataset(11)
    other_dataset = create_dataset(11, price_offset=1)
    other_plan = build_plan(other_dataset)

    with pytest.raises(ValueError, match="does not belong"):
        WalkForwardDatasetMaterializer().materialize(
            dataset=dataset,
            plan=other_plan,
        )


def test_materializer_rejects_incorrect_plan_candle_count() -> None:
    dataset = create_dataset(11)
    plan = build_plan(dataset).model_copy(update={"candle_count": 99})

    with pytest.raises(ValueError, match="candle count"):
        WalkForwardDatasetMaterializer().materialize(
            dataset=dataset,
            plan=plan,
        )


def test_dataset_builder_rejects_naive_created_time() -> None:
    dataset = create_dataset(11)

    with pytest.raises(ValueError, match="timezone information"):
        DatasetBuilder().build(
            name="Invalid created time",
            candles=dataset.candles,
            created_at=datetime(2026, 8, 22, 10),
        )
