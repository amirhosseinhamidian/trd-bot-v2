from datetime import UTC, datetime
from decimal import Decimal

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode
from trd_bot.paper.portfolio import SimulatedPortfolio
from trd_bot.research import (
    CandidateBuilder,
    CandidateEntryZone,
    CandidateExitReason,
    CandidateExitTrigger,
    CandidatePositionMonitor,
    CandidatePositionMonitoringResult,
    CandidateRanker,
    CandidateReplayLifecycleResult,
    CandidateReplayLifecycleRunner,
    CandidateReplayLifecycleStatus,
    CandidateTarget,
    CandidateTradePlan,
    DatasetBuilder,
)
from trd_bot.research.candidate_ranking import CandidateRankingEntry
from trd_bot.research.candidates import ResearchCandidate
from trd_bot.research.datasets import DatasetSnapshot
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

EVALUATED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)
CANDIDATE_CREATED_AT = datetime(2026, 8, 26, 11, 1, tzinfo=UTC)
VALID_UNTIL = datetime(2026, 8, 26, 16, tzinfo=UTC)


def candle(
    hour: int,
    *,
    high_price: str,
    low_price: str,
    close_price: str,
) -> OHLCVCandle:
    close = Decimal(close_price)

    return OHLCVCandle(
        source="test-exchange",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 8, 26, hour, tzinfo=UTC),
        close_time=datetime(2026, 8, 26, hour + 1, tzinfo=UTC),
        received_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
        open_price=close,
        high_price=Decimal(high_price),
        low_price=Decimal(low_price),
        close_price=close,
        volume=Decimal("1000"),
        is_closed=True,
    )


def lifecycle_dataset() -> DatasetSnapshot:
    return DatasetBuilder().build(
        name="candidate lifecycle replay dataset",
        candles=(
            candle(
                10,
                high_price="103",
                low_price="99",
                close_price="102",
            ),
            candle(
                11,
                high_price="104",
                low_price="100",
                close_price="101",
            ),
            candle(
                12,
                high_price="99",
                low_price="96",
                close_price="98",
            ),
            candle(
                13,
                high_price="101",
                low_price="99",
                close_price="100",
            ),
            candle(
                14,
                high_price="109",
                low_price="103",
                close_price="107",
            ),
        ),
        created_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
    )


def candidate(
    *,
    dataset_id: str,
    experiment_id: str,
    confidence: str,
    entry_low: str,
    entry_high: str,
    invalidation: str,
    target: str,
) -> ResearchCandidate:
    signal_close = datetime(2026, 8, 26, 11, tzinfo=UTC)
    source_signal = StrategySignal(
        signal_id=build_signal_id(
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            dataset_id=dataset_id,
            candle_close_time=signal_close,
            direction=SignalDirection.LONG,
        ),
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id=dataset_id,
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        candle_open_time=datetime(2026, 8, 26, 10, tzinfo=UTC),
        candle_close_time=signal_close,
        generated_at=signal_close,
        direction=SignalDirection.LONG,
        score=Decimal("0.80"),
        reason="Historical signal for full candidate lifecycle.",
        features=(
            StrategyFeature(
                name="test_feature",
                value=Decimal("1"),
            ),
        ),
    )

    return CandidateBuilder.from_signal(
        signal=source_signal,
        experiment_id=experiment_id,
        horizon_candles=4,
        confidence=Decimal(confidence),
        created_at=CANDIDATE_CREATED_AT,
        valid_until=VALID_UNTIL,
        trade_plan=CandidateTradePlan(
            entry_zone=CandidateEntryZone(
                lower_price=Decimal(entry_low),
                upper_price=Decimal(entry_high),
            ),
            invalidation_price=Decimal(invalidation),
            targets=(
                CandidateTarget(
                    label="target-1",
                    price=Decimal(target),
                ),
            ),
        ),
    )


def ranked_entries(*, dataset_id: str) -> tuple[CandidateRankingEntry, ...]:
    return (
        CandidateRanker()
        .rank(
            candidates=(
                candidate(
                    dataset_id=dataset_id,
                    experiment_id="experiment-1111111111111111",
                    confidence="0.95",
                    entry_low="120",
                    entry_high="122",
                    invalidation="117",
                    target="132",
                ),
                candidate(
                    dataset_id=dataset_id,
                    experiment_id="experiment-2222222222222222",
                    confidence="0.80",
                    entry_low="100",
                    entry_high="102",
                    invalidation="98",
                    target="108",
                ),
            ),
            at=EVALUATED_AT,
        )
        .entries
    )


def simulated_portfolio(*, dataset_id: str) -> SimulatedPortfolio:
    return SimulatedPortfolioLedger().create(
        mode=SimulationMode.PAPER,
        dataset_id=dataset_id,
        starting_cash=Decimal("10000"),
        created_at=datetime(2026, 8, 26, 11, tzinfo=UTC),
    )


def test_lifecycle_replays_ranked_candidates_then_closes_opened_position() -> None:
    dataset = lifecycle_dataset()
    entries = ranked_entries(
        dataset_id=dataset.dataset_id,
    )

    result = CandidateReplayLifecycleRunner().run(
        entries=entries,
        portfolio=simulated_portfolio(
            dataset_id=dataset.dataset_id,
        ),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.status is CandidateReplayLifecycleStatus.CLOSED
    assert result.replay.attempted_count == 2
    assert result.replay.selected_candidate_id == entries[1].candidate.candidate_id
    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.TARGET
    assert result.monitoring.trigger.price == Decimal("108")
    assert result.monitoring.closed_position.status.value == "closed"
    assert result.portfolio.positions == (result.monitoring.closed_position,)


def test_lifecycle_preserves_portfolio_when_no_candidate_fills() -> None:
    dataset = lifecycle_dataset()
    no_fill = (
        CandidateRanker()
        .rank(
            candidates=(
                candidate(
                    dataset_id=dataset.dataset_id,
                    experiment_id="experiment-3333333333333333",
                    confidence="0.90",
                    entry_low="130",
                    entry_high="132",
                    invalidation="127",
                    target="142",
                ),
            ),
            at=EVALUATED_AT,
        )
        .entries
    )
    initial_portfolio = simulated_portfolio(
        dataset_id=dataset.dataset_id,
    )

    result = CandidateReplayLifecycleRunner().run(
        entries=no_fill,
        portfolio=initial_portfolio,
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.status is CandidateReplayLifecycleStatus.NO_POSITION
    assert result.replay.selected_candidate_id is None
    assert result.monitoring is None
    assert result.portfolio == initial_portfolio


def test_position_monitoring_and_lifecycle_contracts_are_public() -> None:
    exported_symbols = (
        CandidateExitReason,
        CandidateExitTrigger,
        CandidatePositionMonitor,
        CandidatePositionMonitoringResult,
        CandidateReplayLifecycleResult,
        CandidateReplayLifecycleRunner,
        CandidateReplayLifecycleStatus,
    )

    assert all(symbol is not None for symbol in exported_symbols)
