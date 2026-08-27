from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode
from trd_bot.paper.portfolio import SimulatedPortfolio
from trd_bot.research.candidate_ranking import CandidateRanker, CandidateRankingEntry
from trd_bot.research.candidates import (
    CandidateBuilder,
    CandidateEntryZone,
    CandidateTarget,
    CandidateTradePlan,
)
from trd_bot.research.dataset_replay import (
    CandidateDatasetReplayRunner,
    CandidateReplayStatus,
)
from trd_bot.research.datasets import DatasetBuilder, DatasetSnapshot
from trd_bot.research.risk_policy import (
    CandidateRiskEvaluator,
    CandidateRiskPolicy,
)
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
EXPERIMENT_ID = "experiment-0123456789abcdef"


def candle(
    hour: int,
    *,
    open_price: str,
    high_price: str,
    low_price: str,
    close_price: str,
) -> OHLCVCandle:
    return OHLCVCandle(
        source="test-exchange",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 8, 26, hour, tzinfo=UTC),
        close_time=datetime(2026, 8, 26, hour + 1, tzinfo=UTC),
        received_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
        open_price=Decimal(open_price),
        high_price=Decimal(high_price),
        low_price=Decimal(low_price),
        close_price=Decimal(close_price),
        volume=Decimal("1000"),
        is_closed=True,
    )


def dataset(
    *,
    replay_candles: tuple[OHLCVCandle, ...],
) -> DatasetSnapshot:
    all_candles = (
        candle(
            10,
            open_price="98",
            high_price="101",
            low_price="97",
            close_price="100",
        ),
        candle(
            11,
            open_price="100",
            high_price="103",
            low_price="99",
            close_price="102",
        ),
        *replay_candles,
    )

    return DatasetBuilder().build(
        name="candidate replay dataset",
        candles=all_candles,
        created_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
    )


def signal(
    *,
    dataset_id: str,
    direction: SignalDirection,
    score: Decimal,
) -> StrategySignal:
    close_time = datetime(2026, 8, 26, 11, tzinfo=UTC)

    return StrategySignal(
        signal_id=build_signal_id(
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            dataset_id=dataset_id,
            candle_close_time=close_time,
            direction=direction,
        ),
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id=dataset_id,
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        candle_open_time=datetime(2026, 8, 26, 10, tzinfo=UTC),
        candle_close_time=close_time,
        generated_at=close_time,
        direction=direction,
        score=score,
        reason="Historical signal used for deterministic replay.",
        features=(
            StrategyFeature(
                name="test_feature",
                value=Decimal("1"),
            ),
        ),
    )


def long_entry(
    *,
    replay_dataset: DatasetSnapshot,
    valid_until: datetime = VALID_UNTIL,
) -> CandidateRankingEntry:
    candidate = CandidateBuilder.from_signal(
        signal=signal(
            dataset_id=replay_dataset.dataset_id,
            direction=SignalDirection.LONG,
            score=Decimal("0.80"),
        ),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.80"),
        created_at=CANDIDATE_CREATED_AT,
        valid_until=valid_until,
        trade_plan=CandidateTradePlan(
            entry_zone=CandidateEntryZone(
                lower_price=Decimal("100"),
                upper_price=Decimal("102"),
            ),
            invalidation_price=Decimal("97"),
            targets=(
                CandidateTarget(
                    label="target-1",
                    price=Decimal("112"),
                ),
            ),
        ),
    )

    return (
        CandidateRanker()
        .rank(
            candidates=(candidate,),
            at=EVALUATED_AT,
        )
        .entries[0]
    )


def short_entry(
    *,
    replay_dataset: DatasetSnapshot,
) -> CandidateRankingEntry:
    candidate = CandidateBuilder.from_signal(
        signal=signal(
            dataset_id=replay_dataset.dataset_id,
            direction=SignalDirection.SHORT,
            score=Decimal("-0.80"),
        ),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.80"),
        created_at=CANDIDATE_CREATED_AT,
        valid_until=VALID_UNTIL,
        trade_plan=CandidateTradePlan(
            entry_zone=CandidateEntryZone(
                lower_price=Decimal("98"),
                upper_price=Decimal("100"),
            ),
            invalidation_price=Decimal("103"),
            targets=(
                CandidateTarget(
                    label="target-1",
                    price=Decimal("90"),
                ),
            ),
        ),
    )

    return (
        CandidateRanker()
        .rank(
            candidates=(candidate,),
            at=EVALUATED_AT,
        )
        .entries[0]
    )


def portfolio(*, dataset_id: str) -> SimulatedPortfolio:
    return SimulatedPortfolioLedger().create(
        mode=SimulationMode.PAPER,
        dataset_id=dataset_id,
        starting_cash=Decimal("10000"),
        created_at=datetime(2026, 8, 26, 11, tzinfo=UTC),
    )


def test_replay_skips_non_overlapping_candle_and_opens_on_first_fill() -> None:
    replay_dataset = dataset(
        replay_candles=(
            candle(
                12,
                open_price="98",
                high_price="99",
                low_price="96",
                close_price="98",
            ),
            candle(
                13,
                open_price="99",
                high_price="101",
                low_price="98",
                close_price="100",
            ),
            candle(
                14,
                open_price="100",
                high_price="104",
                low_price="99",
                close_price="103",
            ),
        )
    )

    result = CandidateDatasetReplayRunner().run(
        entry=long_entry(
            replay_dataset=replay_dataset,
        ),
        portfolio=portfolio(
            dataset_id=replay_dataset.dataset_id,
        ),
        dataset=replay_dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.status is CandidateReplayStatus.OPENED
    assert result.fill is not None
    assert result.fill.fill_price == Decimal("101")
    assert result.fill.candle_open_time == datetime(2026, 8, 26, 13, tzinfo=UTC)
    assert result.fill.candle_close_time == datetime(2026, 8, 26, 14, tzinfo=UTC)
    assert result.simulation is not None
    assert result.simulation.opened_position.entry_price == Decimal("101")


def test_replay_returns_no_fill_when_zone_is_never_reached_before_expiry() -> None:
    replay_dataset = dataset(
        replay_candles=(
            candle(
                12,
                open_price="98",
                high_price="99",
                low_price="96",
                close_price="98",
            ),
            candle(
                13,
                open_price="97",
                high_price="99",
                low_price="95",
                close_price="98",
            ),
            candle(
                14,
                open_price="98",
                high_price="99",
                low_price="96",
                close_price="98",
            ),
        )
    )

    result = CandidateDatasetReplayRunner().run(
        entry=long_entry(
            replay_dataset=replay_dataset,
            valid_until=datetime(2026, 8, 26, 15, tzinfo=UTC),
        ),
        portfolio=portfolio(
            dataset_id=replay_dataset.dataset_id,
        ),
        dataset=replay_dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.status is CandidateReplayStatus.NO_FILL
    assert result.fill is None
    assert result.simulation is None


def test_replay_reports_risk_rejection_without_searching_for_fill() -> None:
    replay_dataset = dataset(
        replay_candles=(
            candle(
                12,
                open_price="100",
                high_price="102",
                low_price="99",
                close_price="101",
            ),
            candle(
                13,
                open_price="101",
                high_price="103",
                low_price="100",
                close_price="102",
            ),
            candle(
                14,
                open_price="102",
                high_price="104",
                low_price="101",
                close_price="103",
            ),
        )
    )
    evaluator = CandidateRiskEvaluator(
        policy=CandidateRiskPolicy(
            min_ranking_score=Decimal("0.95"),
        )
    )

    result = CandidateDatasetReplayRunner(
        risk_evaluator=evaluator,
    ).run(
        entry=long_entry(
            replay_dataset=replay_dataset,
        ),
        portfolio=portfolio(
            dataset_id=replay_dataset.dataset_id,
        ),
        dataset=replay_dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.status is CandidateReplayStatus.RISK_REJECTED
    assert result.fill is None
    assert result.simulation is None


def test_replay_rejects_dataset_lineage_mismatch() -> None:
    replay_dataset = dataset(
        replay_candles=(
            candle(
                12,
                open_price="100",
                high_price="102",
                low_price="99",
                close_price="101",
            ),
            candle(
                13,
                open_price="101",
                high_price="103",
                low_price="100",
                close_price="102",
            ),
            candle(
                14,
                open_price="102",
                high_price="104",
                low_price="101",
                close_price="103",
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="portfolio and replay dataset lineage",
    ):
        CandidateDatasetReplayRunner().run(
            entry=long_entry(
                replay_dataset=replay_dataset,
            ),
            portfolio=portfolio(
                dataset_id="dataset-other",
            ),
            dataset=replay_dataset,
            evaluated_at=EVALUATED_AT,
        )


def test_short_replay_uses_lowest_reachable_price_inside_entry_zone() -> None:
    replay_dataset = dataset(
        replay_candles=(
            candle(
                12,
                open_price="101",
                high_price="101",
                low_price="99",
                close_price="100",
            ),
            candle(
                13,
                open_price="100",
                high_price="102",
                low_price="98",
                close_price="99",
            ),
            candle(
                14,
                open_price="99",
                high_price="100",
                low_price="95",
                close_price="96",
            ),
        )
    )

    result = CandidateDatasetReplayRunner().run(
        entry=short_entry(
            replay_dataset=replay_dataset,
        ),
        portfolio=portfolio(
            dataset_id=replay_dataset.dataset_id,
        ),
        dataset=replay_dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.status is CandidateReplayStatus.OPENED
    assert result.fill is not None
    assert result.fill.fill_price == Decimal("99")
    assert result.fill.candle_close_time == datetime(2026, 8, 26, 13, tzinfo=UTC)


def test_replay_does_not_use_candle_that_started_before_evaluation() -> None:
    replay_dataset = dataset(
        replay_candles=(
            candle(
                12,
                open_price="98",
                high_price="99",
                low_price="96",
                close_price="98",
            ),
            candle(
                13,
                open_price="100",
                high_price="101",
                low_price="99",
                close_price="100",
            ),
            candle(
                14,
                open_price="101",
                high_price="102",
                low_price="100",
                close_price="101",
            ),
        )
    )

    result = CandidateDatasetReplayRunner().run(
        entry=long_entry(
            replay_dataset=replay_dataset,
        ),
        portfolio=portfolio(
            dataset_id=replay_dataset.dataset_id,
        ),
        dataset=replay_dataset,
        evaluated_at=datetime(2026, 8, 26, 12, 30, tzinfo=UTC),
    )

    assert result.status is CandidateReplayStatus.OPENED
    assert result.fill is not None
    assert result.fill.candle_open_time == datetime(2026, 8, 26, 13, tzinfo=UTC)
