from datetime import UTC, datetime
from decimal import Decimal

import pytest

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
