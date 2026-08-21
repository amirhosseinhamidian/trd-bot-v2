from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.backtesting import BacktestConfig, BenchmarkType
from trd_bot.domain.market_data import (
    OHLCVCandle,
    Timeframe,
    TradingPair,
)
from trd_bot.research import (
    DatasetBuilder,
    DatasetSnapshot,
    ResearchPipeline,
)
from trd_bot.strategies import (
    EMACrossoverStrategy,
    SignalDirection,
)

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)


def create_dataset(
    prices: list[tuple[str, str]],
) -> DatasetSnapshot:
    candles = []

    for index, (open_text, close_text) in enumerate(prices):
        open_price = Decimal(open_text)
        close_price = Decimal(close_text)
        hour = 10 + index

        candles.append(
            OHLCVCandle(
                source="test-exchange",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=datetime(
                    2026,
                    8,
                    21,
                    hour,
                    tzinfo=UTC,
                ),
                close_time=datetime(
                    2026,
                    8,
                    21,
                    hour + 1,
                    tzinfo=UTC,
                ),
                received_at=datetime(
                    2026,
                    8,
                    21,
                    20,
                    tzinfo=UTC,
                ),
                open_price=open_price,
                high_price=(max(open_price, close_price) + Decimal("1")),
                low_price=(min(open_price, close_price) - Decimal("1")),
                close_price=close_price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(
        name="Research pipeline dataset",
        candles=candles,
    )


def test_pipeline_runs_complete_research_workflow() -> None:
    dataset = create_dataset(
        [
            ("5", "5"),
            ("4", "4"),
            ("3", "3"),
            ("4", "4"),
            ("6", "6"),
            ("7", "8"),
        ]
    )

    result = ResearchPipeline().run(
        dataset=dataset,
        strategy=EMACrossoverStrategy(
            fast_period=2,
            slow_period=3,
        ),
        horizon_candles=1,
    )

    assert result.dataset_id == dataset.dataset_id
    assert result.strategy_name == "ema-crossover"
    assert result.generated_signals == 1

    assert result.signals[0].direction == SignalDirection.LONG

    assert result.evaluation_report.resolved_signals == 1
    assert result.summary.long_metrics.correct_signals == 1
    assert result.summary.overall_hit_rate == Decimal("1")
    assert result.backtest_run_id.startswith("backtest-")
    assert len(result.backtest_events) == 2
    assert result.performance_report.total_trades == 1
    assert result.performance_report.dataset_id == dataset.dataset_id
    assert result.benchmark_result.benchmark_type == BenchmarkType.BUY_AND_HOLD
    assert result.benchmark_result.dataset_id == dataset.dataset_id
    assert result.benchmark_result.config == result.backtest_config
    assert result.benchmark_comparison.strategy_run_id == result.backtest_run_id
    assert result.benchmark_comparison.benchmark_run_id == result.benchmark_result.run_id


def test_pipeline_compares_strategy_with_buy_and_hold() -> None:
    dataset = create_dataset(
        [
            ("5", "5"),
            ("4", "4"),
            ("3", "3"),
            ("4", "4"),
            ("6", "6"),
            ("7", "8"),
        ]
    )

    result = ResearchPipeline().run(
        dataset=dataset,
        strategy=EMACrossoverStrategy(fast_period=2, slow_period=3),
    )

    assert result.benchmark_result.performance_report.total_trades == 1
    assert (
        result.benchmark_comparison.return_delta
        == result.performance_report.total_return
        - result.benchmark_result.performance_report.total_return
    )
    assert (
        result.benchmark_comparison.max_drawdown_fraction_delta
        == result.performance_report.max_drawdown_fraction
        - result.benchmark_result.performance_report.max_drawdown_fraction
    )


def test_pipeline_handles_strategy_without_signals() -> None:
    dataset = create_dataset(
        [
            ("3", "3"),
            ("4", "4"),
        ]
    )

    result = ResearchPipeline().run(
        dataset=dataset,
        strategy=EMACrossoverStrategy(
            fast_period=2,
            slow_period=3,
        ),
    )

    assert result.generated_signals == 0
    assert result.signals == ()
    assert result.evaluation_report.total_signals == 0
    assert result.summary.overall_hit_rate is None


def test_pipeline_rejects_invalid_horizon() -> None:
    dataset = create_dataset(
        [
            ("3", "3"),
            ("4", "4"),
        ]
    )

    with pytest.raises(
        ValueError,
        match="horizon must be at least 1",
    ):
        ResearchPipeline().run(
            dataset=dataset,
            strategy=EMACrossoverStrategy(
                fast_period=2,
                slow_period=3,
            ),
            horizon_candles=0,
        )


def test_pipeline_is_deterministic() -> None:
    dataset = create_dataset(
        [
            ("5", "5"),
            ("4", "4"),
            ("3", "3"),
            ("4", "4"),
            ("6", "6"),
            ("7", "8"),
        ]
    )

    strategy = EMACrossoverStrategy(
        fast_period=2,
        slow_period=3,
    )

    first_result = ResearchPipeline().run(
        dataset=dataset,
        strategy=strategy,
    )

    second_result = ResearchPipeline().run(
        dataset=dataset,
        strategy=strategy,
    )

    assert first_result.signals == second_result.signals
    assert first_result.evaluation_report == second_result.evaluation_report
    assert first_result.summary == second_result.summary
    assert first_result.backtest_run_id == second_result.backtest_run_id
    assert first_result.backtest_events == second_result.backtest_events
    assert first_result.performance_report == second_result.performance_report
    assert first_result.benchmark_result == second_result.benchmark_result
    assert first_result.benchmark_comparison == second_result.benchmark_comparison


def test_pipeline_backtest_costs_change_performance_and_run_id() -> None:
    dataset = create_dataset(
        [
            ("5", "5"),
            ("4", "4"),
            ("3", "3"),
            ("4", "4"),
            ("6", "6"),
            ("7", "8"),
        ]
    )

    strategy = EMACrossoverStrategy(
        fast_period=2,
        slow_period=3,
    )

    no_cost_result = ResearchPipeline().run(
        dataset=dataset,
        strategy=strategy,
        backtest_config=BacktestConfig(
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
        ),
    )

    cost_result = ResearchPipeline().run(
        dataset=dataset,
        strategy=strategy,
        backtest_config=BacktestConfig(
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.01"),
            slippage_rate=Decimal("0"),
        ),
    )

    assert no_cost_result.backtest_run_id != cost_result.backtest_run_id
    assert cost_result.performance_report.total_fees > Decimal("0")
    assert cost_result.performance_report.net_pnl < no_cost_result.performance_report.net_pnl
    assert no_cost_result.benchmark_result.run_id != cost_result.benchmark_result.run_id
    assert cost_result.benchmark_result.performance_report.total_fees > Decimal("0")
