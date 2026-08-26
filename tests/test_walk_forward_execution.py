from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import (
    DatasetBuilder,
    DatasetSnapshot,
    WalkForwardConfig,
    WalkForwardDatasetMaterializer,
    WalkForwardExecutor,
    WalkForwardMaterialization,
    WalkForwardPlanner,
    build_walk_forward_execution_id,
)
from trd_bot.strategies import (
    BaseStrategy,
    SignalDirection,
    StrategySignal,
    build_signal_id,
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
                close_price=price + Decimal("0.5"),
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(
        name="Walk-forward execution source",
        candles=candles,
        created_at=CREATED_AT,
    )


def materialize(dataset: DatasetSnapshot) -> WalkForwardMaterialization:
    plan = WalkForwardPlanner().plan(
        dataset=dataset,
        config=WalkForwardConfig(
            train_candles=4,
            test_candles=2,
            step_candles=2,
        ),
    )
    return WalkForwardDatasetMaterializer().materialize(
        dataset=dataset,
        plan=plan,
    )


class LastCandleLongStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "last-candle-long"

    @property
    def version(self) -> str:
        return "1.0.0"

    def generate(self, dataset: DatasetSnapshot) -> tuple[StrategySignal, ...]:
        candle = dataset.candles[-1]
        return (
            StrategySignal(
                signal_id=build_signal_id(
                    strategy_name=self.name,
                    strategy_version=self.version,
                    dataset_id=dataset.dataset_id,
                    candle_close_time=candle.close_time,
                    direction=SignalDirection.LONG,
                ),
                strategy_name=self.name,
                strategy_version=self.version,
                dataset_id=dataset.dataset_id,
                pair=dataset.pair,
                timeframe=dataset.timeframe,
                candle_open_time=candle.open_time,
                candle_close_time=candle.close_time,
                generated_at=candle.close_time,
                direction=SignalDirection.LONG,
                score=Decimal("0.5"),
                reason="Latest closed candle in the available historical prefix",
            ),
        )


class RecordingStrategy(BaseStrategy):
    def __init__(self) -> None:
        self.end_times: list[datetime] = []

    @property
    def name(self) -> str:
        return "recording"

    @property
    def version(self) -> str:
        return "1.0.0"

    def generate(self, dataset: DatasetSnapshot) -> tuple[StrategySignal, ...]:
        self.end_times.append(dataset.end_time)
        return ()


class DuplicateCurrentSignalStrategy(LastCandleLongStrategy):
    def generate(self, dataset: DatasetSnapshot) -> tuple[StrategySignal, ...]:
        signal = super().generate(dataset)[0]
        return (signal, signal)


def test_executor_runs_every_test_fold_through_research_pipeline() -> None:
    dataset = create_dataset(10)
    datasets = materialize(dataset)

    execution = WalkForwardExecutor().execute(
        dataset=dataset,
        materialization=datasets,
        strategy=LastCandleLongStrategy(),
    )

    assert len(execution.fold_results) == 3
    for split, fold_result in zip(datasets.splits, execution.fold_results, strict=True):
        assert fold_result.split_id == split.split_id
        assert fold_result.test_dataset_id == split.test_dataset.dataset_id
        assert fold_result.result.dataset_id == split.test_dataset.dataset_id
        assert fold_result.result.performance_report.total_trades == 1


def test_executor_reports_each_completed_fold() -> None:
    dataset = create_dataset(10)
    datasets = materialize(dataset)
    progress_events: list[tuple[int, int]] = []

    WalkForwardExecutor().execute(
        dataset=dataset,
        materialization=datasets,
        strategy=LastCandleLongStrategy(),
        on_fold_completed=lambda completed, total: progress_events.append(
            (
                completed,
                total,
            )
        ),
    )

    assert progress_events == [
        (1, 3),
        (2, 3),
        (3, 3),
    ]


def test_executor_never_exposes_future_test_candles_to_strategy() -> None:
    dataset = create_dataset(10)
    datasets = materialize(dataset)
    strategy = RecordingStrategy()

    WalkForwardExecutor().execute(
        dataset=dataset,
        materialization=datasets,
        strategy=strategy,
    )

    expected_end_times = [
        candle.close_time for split in datasets.splits for candle in split.test_dataset.candles
    ]
    assert strategy.end_times == expected_end_times


def test_executor_rebases_signals_to_each_test_dataset() -> None:
    dataset = create_dataset(10)
    datasets = materialize(dataset)

    execution = WalkForwardExecutor().execute(
        dataset=dataset,
        materialization=datasets,
        strategy=LastCandleLongStrategy(),
    )

    for fold_result in execution.fold_results:
        for signal in fold_result.result.signals:
            assert signal.dataset_id == fold_result.test_dataset_id
            assert signal.signal_id == build_signal_id(
                strategy_name=execution.strategy_name,
                strategy_version=execution.strategy_version,
                dataset_id=fold_result.test_dataset_id,
                candle_close_time=signal.candle_close_time,
                direction=signal.direction,
            )


def test_execution_summary_aggregates_fold_results() -> None:
    dataset = create_dataset(10)
    execution = WalkForwardExecutor().execute(
        dataset=dataset,
        materialization=materialize(dataset),
        strategy=LastCandleLongStrategy(),
    )
    fold_count = Decimal(len(execution.fold_results))
    expected_strategy_average = (
        sum(
            (fold.result.performance_report.total_return for fold in execution.fold_results),
            start=Decimal("0"),
        )
        / fold_count
    )
    expected_benchmark_average = (
        sum(
            (
                fold.result.benchmark_result.performance_report.total_return
                for fold in execution.fold_results
            ),
            start=Decimal("0"),
        )
        / fold_count
    )

    assert execution.summary.total_folds == 3
    assert execution.summary.total_signals == 6
    assert execution.summary.folds_with_trades == 3
    assert execution.summary.average_strategy_return == expected_strategy_average
    assert execution.summary.average_benchmark_return == expected_benchmark_average
    assert (
        execution.summary.strategy_wins + execution.summary.benchmark_wins + execution.summary.ties
        == execution.summary.total_folds
    )


def test_execution_is_deterministic() -> None:
    dataset = create_dataset(10)
    datasets = materialize(dataset)
    executor = WalkForwardExecutor()

    first = executor.execute(
        dataset=dataset,
        materialization=datasets,
        strategy=LastCandleLongStrategy(),
    )
    second = executor.execute(
        dataset=dataset,
        materialization=datasets,
        strategy=LastCandleLongStrategy(),
    )

    assert first == second
    assert first.execution_id == build_walk_forward_execution_id(
        plan_id=datasets.plan.plan_id,
        strategy_name=first.strategy_name,
        strategy_version=first.strategy_version,
        strategy_parameters=first.strategy_parameters,
        horizon_candles=first.horizon_candles,
        backtest_config=first.backtest_config,
        fold_run_ids=tuple(fold.result.backtest_run_id for fold in first.fold_results),
    )


def test_executor_rejects_materialization_from_another_dataset() -> None:
    dataset = create_dataset(10)
    other_dataset = create_dataset(10, price_offset=1)

    with pytest.raises(ValueError, match="does not belong"):
        WalkForwardExecutor().execute(
            dataset=dataset,
            materialization=materialize(other_dataset),
            strategy=LastCandleLongStrategy(),
        )


def test_executor_rejects_invalid_horizon() -> None:
    dataset = create_dataset(10)

    with pytest.raises(ValueError, match="greater than zero"):
        WalkForwardExecutor().execute(
            dataset=dataset,
            materialization=materialize(dataset),
            strategy=LastCandleLongStrategy(),
            horizon_candles=0,
        )


def test_executor_rejects_multiple_signals_for_one_test_candle() -> None:
    dataset = create_dataset(10)

    with pytest.raises(ValueError, match="multiple signals"):
        WalkForwardExecutor().execute(
            dataset=dataset,
            materialization=materialize(dataset),
            strategy=DuplicateCurrentSignalStrategy(),
        )
