from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode
from trd_bot.paper.portfolio import SimulatedPortfolio
from trd_bot.research import (
    CandidateBuilder,
    CandidateDatasetReplayOrchestrator,
    CandidateDatasetReplayRunner,
    CandidateEntryZone,
    CandidateRanker,
    CandidateReplayBatchResult,
    CandidateReplayFill,
    CandidateReplayResult,
    CandidateReplayStatus,
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
VALID_UNTIL = datetime(2026, 8, 26, 15, tzinfo=UTC)


def candle(
    hour: int,
    *,
    high_price: str,
    low_price: str,
) -> OHLCVCandle:
    midpoint = (Decimal(high_price) + Decimal(low_price)) / Decimal("2")

    return OHLCVCandle(
        source="test-exchange",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 8, 26, hour, tzinfo=UTC),
        close_time=datetime(2026, 8, 26, hour + 1, tzinfo=UTC),
        received_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
        open_price=midpoint,
        high_price=Decimal(high_price),
        low_price=Decimal(low_price),
        close_price=midpoint,
        volume=Decimal("1000"),
        is_closed=True,
    )


def replay_dataset() -> DatasetSnapshot:
    return DatasetBuilder().build(
        name="multi-candidate replay dataset",
        candles=(
            candle(
                10,
                high_price="103",
                low_price="99",
            ),
            candle(
                11,
                high_price="104",
                low_price="100",
            ),
            candle(
                12,
                high_price="101",
                low_price="99",
            ),
            candle(
                13,
                high_price="102",
                low_price="98",
            ),
            candle(
                14,
                high_price="103",
                low_price="99",
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
    close_time = datetime(2026, 8, 26, 11, tzinfo=UTC)
    source_signal = StrategySignal(
        signal_id=build_signal_id(
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            dataset_id=dataset_id,
            candle_close_time=close_time,
            direction=SignalDirection.LONG,
        ),
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id=dataset_id,
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        candle_open_time=datetime(2026, 8, 26, 10, tzinfo=UTC),
        candle_close_time=close_time,
        generated_at=close_time,
        direction=SignalDirection.LONG,
        score=Decimal("0.80"),
        reason="Historical signal for multi-candidate replay.",
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
    candidates = (
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
            invalidation="97",
            target="112",
        ),
        candidate(
            dataset_id=dataset_id,
            experiment_id="experiment-3333333333333333",
            confidence="0.70",
            entry_low="100",
            entry_high="102",
            invalidation="97",
            target="112",
        ),
    )

    return (
        CandidateRanker()
        .rank(
            candidates=candidates,
            at=EVALUATED_AT,
        )
        .entries
    )


def portfolio(*, dataset_id: str) -> SimulatedPortfolio:
    return SimulatedPortfolioLedger().create(
        mode=SimulationMode.PAPER,
        dataset_id=dataset_id,
        starting_cash=Decimal("10000"),
        created_at=datetime(2026, 8, 26, 11, tzinfo=UTC),
    )


def test_orchestrator_tries_next_rank_after_no_fill_then_stops_on_open() -> None:
    dataset = replay_dataset()
    entries = ranked_entries(
        dataset_id=dataset.dataset_id,
    )
    initial_portfolio = portfolio(
        dataset_id=dataset.dataset_id,
    )

    result = CandidateDatasetReplayOrchestrator().run(
        entries=entries,
        portfolio=initial_portfolio,
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.total_candidates == 3
    assert result.attempted_count == 2
    assert result.skipped_count == 1
    assert tuple(item.status for item in result.attempted) == (
        CandidateReplayStatus.NO_FILL,
        CandidateReplayStatus.OPENED,
    )
    assert result.selected_candidate_id == entries[1].candidate.candidate_id
    assert result.skipped_candidate_ids == (entries[2].candidate.candidate_id,)
    assert len(result.portfolio.positions) == 1


def test_orchestration_is_independent_of_input_order() -> None:
    dataset = replay_dataset()
    entries = ranked_entries(
        dataset_id=dataset.dataset_id,
    )
    initial_portfolio = portfolio(
        dataset_id=dataset.dataset_id,
    )

    forward = CandidateDatasetReplayOrchestrator().run(
        entries=entries,
        portfolio=initial_portfolio,
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )
    reverse = CandidateDatasetReplayOrchestrator().run(
        entries=tuple(reversed(entries)),
        portfolio=initial_portfolio,
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert tuple(item.ranking_entry.candidate.candidate_id for item in forward.attempted) == tuple(
        item.ranking_entry.candidate.candidate_id for item in reverse.attempted
    )
    assert forward.skipped_candidate_ids == reverse.skipped_candidate_ids
    assert forward.selected_candidate_id == reverse.selected_candidate_id


def test_orchestrator_rejects_duplicate_candidate_entries() -> None:
    dataset = replay_dataset()
    entries = ranked_entries(
        dataset_id=dataset.dataset_id,
    )

    with pytest.raises(
        ValueError,
        match="candidate IDs must be unique",
    ):
        CandidateDatasetReplayOrchestrator().run(
            entries=(entries[0], entries[0]),
            portfolio=portfolio(
                dataset_id=dataset.dataset_id,
            ),
            dataset=dataset,
            evaluated_at=EVALUATED_AT,
        )


def test_empty_batch_preserves_portfolio_snapshot() -> None:
    dataset = replay_dataset()
    initial_portfolio = portfolio(
        dataset_id=dataset.dataset_id,
    )

    result = CandidateDatasetReplayOrchestrator().run(
        entries=(),
        portfolio=initial_portfolio,
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.total_candidates == 0
    assert result.attempted == ()
    assert result.skipped_candidate_ids == ()
    assert result.selected_candidate_id is None
    assert result.portfolio == initial_portfolio


def test_dataset_replay_contracts_are_available_from_research_public_api() -> None:
    exported_symbols = (
        CandidateDatasetReplayOrchestrator,
        CandidateDatasetReplayRunner,
        CandidateReplayBatchResult,
        CandidateReplayFill,
        CandidateReplayResult,
        CandidateReplayStatus,
    )

    assert all(symbol is not None for symbol in exported_symbols)
