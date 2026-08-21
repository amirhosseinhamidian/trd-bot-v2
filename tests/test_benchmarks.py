from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.backtesting import (
    BacktestConfig,
    BenchmarkType,
    BuyAndHoldBenchmark,
    ComparisonOutcome,
    PerformanceComparator,
    build_benchmark_run_id,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import DatasetBuilder, DatasetSnapshot

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")

NO_COST_CONFIG = BacktestConfig(
    starting_balance=Decimal("10000"),
    allocation_fraction=Decimal("0.10"),
    fee_rate=Decimal("0"),
    slippage_rate=Decimal("0"),
)


def create_dataset(prices: list[str], *, source: str = "test-exchange") -> DatasetSnapshot:
    start = datetime(2026, 8, 21, 10, tzinfo=UTC)
    candles = []

    for index, price_text in enumerate(prices):
        price = Decimal(price_text)
        open_time = start + timedelta(hours=index)
        candles.append(
            OHLCVCandle(
                source=source,
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                received_at=start + timedelta(days=1),
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(name="Benchmark dataset", candles=candles)


def test_buy_and_hold_uses_first_open_and_final_close() -> None:
    dataset = create_dataset(["100", "110", "120"])

    result = BuyAndHoldBenchmark().run(dataset=dataset, config=NO_COST_CONFIG)

    assert result.benchmark_type == BenchmarkType.BUY_AND_HOLD
    assert result.events[0].timestamp == dataset.candles[0].open_time
    assert result.events[0].price == Decimal("100")
    assert result.events[1].timestamp == dataset.candles[-1].close_time
    assert result.events[1].price == Decimal("120")
    assert result.performance_report.total_trades == 1
    assert result.performance_report.net_pnl == Decimal("200")


def test_buy_and_hold_applies_costs_and_unfavorable_slippage() -> None:
    dataset = create_dataset(["100", "120"])
    config = NO_COST_CONFIG.model_copy(
        update={"fee_rate": Decimal("0.001"), "slippage_rate": Decimal("0.01")}
    )

    result = BuyAndHoldBenchmark().run(dataset=dataset, config=config)

    assert result.events[0].price == Decimal("101.00")
    assert result.events[1].price == Decimal("118.80")
    assert result.performance_report.total_fees > 0
    assert result.performance_report.net_pnl < result.performance_report.gross_pnl


def test_benchmark_run_is_deterministic() -> None:
    dataset = create_dataset(["100", "110", "120"])

    first = BuyAndHoldBenchmark().run(dataset=dataset, config=NO_COST_CONFIG)
    second = BuyAndHoldBenchmark().run(dataset=dataset, config=NO_COST_CONFIG)

    assert first == second
    assert first.run_id == build_benchmark_run_id(
        dataset_id=dataset.dataset_id,
        benchmark_type=BenchmarkType.BUY_AND_HOLD,
        config=NO_COST_CONFIG,
    )


def test_falling_market_produces_loss_and_drawdown() -> None:
    dataset = create_dataset(["100", "90", "80"])

    result = BuyAndHoldBenchmark().run(dataset=dataset, config=NO_COST_CONFIG)
    report = result.performance_report

    assert report.net_pnl == Decimal("-200")
    assert report.max_drawdown == Decimal("200")
    assert report.max_drawdown_fraction == Decimal("0.02")
    assert report.profit_factor == Decimal("0")


def test_comparator_identifies_higher_strategy_return() -> None:
    dataset = create_dataset(["100", "110", "120"])
    benchmark = BuyAndHoldBenchmark().run(dataset=dataset, config=NO_COST_CONFIG)
    larger_allocation = NO_COST_CONFIG.model_copy(update={"allocation_fraction": Decimal("0.20")})
    strategy_report = (
        BuyAndHoldBenchmark()
        .run(
            dataset=dataset,
            config=larger_allocation,
        )
        .performance_report.model_copy(update={"run_id": "strategy-test"})
    )

    comparison = PerformanceComparator().compare(
        strategy=strategy_report,
        benchmark=benchmark,
    )

    assert comparison.outcome == ComparisonOutcome.STRATEGY
    assert comparison.return_delta > 0
    assert comparison.net_pnl_delta > 0


def test_comparator_reports_a_tie_for_equal_performance() -> None:
    dataset = create_dataset(["100", "110", "120"])
    benchmark = BuyAndHoldBenchmark().run(dataset=dataset, config=NO_COST_CONFIG)
    strategy_report = benchmark.performance_report.model_copy(update={"run_id": "strategy-test"})

    comparison = PerformanceComparator().compare(
        strategy=strategy_report,
        benchmark=benchmark,
    )

    assert comparison.outcome == ComparisonOutcome.TIE
    assert comparison.return_delta == Decimal("0")


def test_comparator_rejects_different_datasets() -> None:
    first_dataset = create_dataset(["100", "110", "120"])
    second_dataset = create_dataset(["100", "110", "121"], source="other-exchange")
    benchmark = BuyAndHoldBenchmark().run(dataset=first_dataset, config=NO_COST_CONFIG)
    other_report = (
        BuyAndHoldBenchmark()
        .run(
            dataset=second_dataset,
            config=NO_COST_CONFIG,
        )
        .performance_report
    )

    with pytest.raises(ValueError, match="same dataset"):
        PerformanceComparator().compare(strategy=other_report, benchmark=benchmark)
