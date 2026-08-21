from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.backtesting import (
    BacktestConfig,
    BacktestEngine,
    BacktestPerformanceAnalyzer,
    PositionSide,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import DatasetBuilder, DatasetSnapshot
from trd_bot.strategies import SignalDirection, StrategySignal, build_signal_id

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")

NO_COST_CONFIG = BacktestConfig(
    starting_balance=Decimal("10000"),
    allocation_fraction=Decimal("0.10"),
    fee_rate=Decimal("0"),
    slippage_rate=Decimal("0"),
)


def create_dataset(prices: list[str]) -> DatasetSnapshot:
    candles = []
    for index, price_text in enumerate(prices):
        price = Decimal(price_text)
        hour = 10 + index
        candles.append(
            OHLCVCandle(
                source="test-exchange",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=datetime(2026, 8, 21, hour, tzinfo=UTC),
                close_time=datetime(2026, 8, 21, hour + 1, tzinfo=UTC),
                received_at=datetime(2026, 8, 21, 20, tzinfo=UTC),
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )
    return DatasetBuilder().build(name="Backtest performance dataset", candles=candles)


def create_signal(
    *,
    dataset: DatasetSnapshot,
    candle_index: int,
    direction: SignalDirection,
) -> StrategySignal:
    candle = dataset.candles[candle_index]
    signal_id = build_signal_id(
        strategy_name="test-strategy",
        strategy_version="1.0.0",
        dataset_id=dataset.dataset_id,
        candle_close_time=candle.close_time,
        direction=direction,
    )
    score = Decimal("0.5") if direction == SignalDirection.LONG else Decimal("-0.5")
    return StrategySignal(
        signal_id=signal_id,
        strategy_name="test-strategy",
        strategy_version="1.0.0",
        dataset_id=dataset.dataset_id,
        pair=dataset.pair,
        timeframe=dataset.timeframe,
        candle_open_time=candle.open_time,
        candle_close_time=candle.close_time,
        generated_at=candle.close_time,
        direction=direction,
        score=score,
        reason="Backtest performance test signal.",
    )


def test_empty_events_produce_an_empty_report() -> None:
    report = BacktestPerformanceAnalyzer().analyze(
        run_id="empty-run",
        dataset_id="dataset-empty",
        events=(),
        config=NO_COST_CONFIG,
    )
    assert report.total_trades == 0
    assert report.ending_balance == Decimal("10000")
    assert report.net_pnl == Decimal("0")
    assert report.total_return == Decimal("0")
    assert report.win_rate is None
    assert report.trades == ()
    assert report.equity_curve == ()
    assert report.peak_balance == Decimal("10000")
    assert report.max_drawdown == Decimal("0")
    assert report.max_drawdown_fraction == Decimal("0")
    assert report.profit_factor is None


def test_long_trade_performance_includes_fees() -> None:
    dataset = create_dataset(["100", "100", "120"])
    signal = create_signal(dataset=dataset, candle_index=0, direction=SignalDirection.LONG)
    config = NO_COST_CONFIG.model_copy(update={"fee_rate": Decimal("0.001")})
    events = BacktestEngine().run(
        run_id="long-with-fees", dataset=dataset, signals=[signal], config=config
    )
    report = BacktestPerformanceAnalyzer().analyze(
        run_id="long-with-fees",
        dataset_id=dataset.dataset_id,
        events=events,
        config=config,
    )
    trade = report.trades[0]
    assert trade.side == PositionSide.LONG
    assert trade.quantity == Decimal("10")
    assert trade.gross_pnl == Decimal("200")
    assert trade.fees == Decimal("2.200")
    assert trade.net_pnl == Decimal("197.800")
    assert report.ending_balance == Decimal("10197.800")
    assert report.total_return == Decimal("0.01978")
    assert report.winning_trades == 1
    assert report.win_rate == Decimal("1")
    assert report.gross_profit == Decimal("197.800")
    assert report.gross_loss == Decimal("0")
    assert report.profit_factor is None
    assert report.equity_curve[0].balance == report.ending_balance
    assert report.max_drawdown == Decimal("0")


def test_short_trade_profit_is_calculated_correctly() -> None:
    dataset = create_dataset(["100", "100", "80"])
    signal = create_signal(dataset=dataset, candle_index=0, direction=SignalDirection.SHORT)
    events = BacktestEngine().run(
        run_id="short-profit", dataset=dataset, signals=[signal], config=NO_COST_CONFIG
    )
    report = BacktestPerformanceAnalyzer().analyze(
        run_id="short-profit",
        dataset_id=dataset.dataset_id,
        events=events,
        config=NO_COST_CONFIG,
    )
    trade = report.trades[0]
    assert trade.side == PositionSide.SHORT
    assert trade.gross_pnl == Decimal("200")
    assert trade.net_pnl == Decimal("200")
    assert report.ending_balance == Decimal("10200")


def test_reversal_produces_separate_trade_outcomes() -> None:
    dataset = create_dataset(["100", "100", "90", "80"])
    long_signal = create_signal(dataset=dataset, candle_index=0, direction=SignalDirection.LONG)
    short_signal = create_signal(dataset=dataset, candle_index=1, direction=SignalDirection.SHORT)
    events = BacktestEngine().run(
        run_id="reversal-performance",
        dataset=dataset,
        signals=[long_signal, short_signal],
        config=NO_COST_CONFIG,
    )
    report = BacktestPerformanceAnalyzer().analyze(
        run_id="reversal-performance",
        dataset_id=dataset.dataset_id,
        events=events,
        config=NO_COST_CONFIG,
    )
    assert report.total_trades == 2
    assert report.winning_trades == 1
    assert report.losing_trades == 1
    assert report.flat_trades == 0
    assert report.win_rate == Decimal("0.5")
    assert len(report.equity_curve) == 2
    assert report.equity_curve[0].balance == Decimal("9900")
    assert report.max_drawdown == Decimal("100")
    assert report.max_drawdown_fraction == Decimal("0.01")
    assert report.profit_factor == report.gross_profit / report.gross_loss


def test_equity_curve_tracks_new_peaks_and_later_drawdown() -> None:
    dataset = create_dataset(["100", "100", "120", "110", "90"])
    long_signal = create_signal(
        dataset=dataset,
        candle_index=0,
        direction=SignalDirection.LONG,
    )
    short_signal = create_signal(
        dataset=dataset,
        candle_index=1,
        direction=SignalDirection.SHORT,
    )
    final_long_signal = create_signal(
        dataset=dataset,
        candle_index=2,
        direction=SignalDirection.LONG,
    )

    events = BacktestEngine().run(
        run_id="equity-drawdown",
        dataset=dataset,
        signals=[long_signal, short_signal, final_long_signal],
        config=NO_COST_CONFIG,
    )
    report = BacktestPerformanceAnalyzer().analyze(
        run_id="equity-drawdown",
        dataset_id=dataset.dataset_id,
        events=events,
        config=NO_COST_CONFIG,
    )

    assert report.total_trades == 3
    assert len(report.equity_curve) == 3
    assert report.equity_curve[-1].balance == report.ending_balance
    assert report.peak_balance > report.starting_balance
    assert report.max_drawdown == report.equity_curve[-1].drawdown
    assert report.max_drawdown_fraction > Decimal("0")
    assert report.gross_profit > Decimal("0")
    assert report.gross_loss > Decimal("0")
    assert report.profit_factor == report.gross_profit / report.gross_loss


def test_analyzer_rejects_unordered_event_sequences() -> None:
    dataset = create_dataset(["100", "100", "120"])
    signal = create_signal(dataset=dataset, candle_index=0, direction=SignalDirection.LONG)
    events = BacktestEngine().run(
        run_id="unordered-events", dataset=dataset, signals=[signal], config=NO_COST_CONFIG
    )
    with pytest.raises(ValueError, match="continuous and ordered"):
        BacktestPerformanceAnalyzer().analyze(
            run_id="unordered-events",
            dataset_id=dataset.dataset_id,
            events=tuple(reversed(events)),
            config=NO_COST_CONFIG,
        )


def test_analyzer_rejects_mismatched_trade_sides() -> None:
    dataset = create_dataset(["100", "100", "120"])
    signal = create_signal(dataset=dataset, candle_index=0, direction=SignalDirection.LONG)
    events = BacktestEngine().run(
        run_id="mismatched-sides", dataset=dataset, signals=[signal], config=NO_COST_CONFIG
    )
    invalid_close = events[1].model_copy(update={"side": PositionSide.SHORT})
    with pytest.raises(ValueError, match="same position side"):
        BacktestPerformanceAnalyzer().analyze(
            run_id="mismatched-sides",
            dataset_id=dataset.dataset_id,
            events=(events[0], invalid_close),
            config=NO_COST_CONFIG,
        )


def test_analyzer_rejects_an_unclosed_position() -> None:
    dataset = create_dataset(["100", "100", "120"])
    signal = create_signal(dataset=dataset, candle_index=0, direction=SignalDirection.LONG)
    events = BacktestEngine().run(
        run_id="unclosed-position", dataset=dataset, signals=[signal], config=NO_COST_CONFIG
    )
    with pytest.raises(ValueError, match="unclosed position"):
        BacktestPerformanceAnalyzer().analyze(
            run_id="unclosed-position",
            dataset_id=dataset.dataset_id,
            events=events[:1],
            config=NO_COST_CONFIG,
        )
