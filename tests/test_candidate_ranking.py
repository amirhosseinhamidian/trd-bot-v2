from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.research.candidate_ranking import (
    CandidateRanker,
    CandidateRankingComponentName,
    CandidateRankingPolicy,
)
from trd_bot.research.candidates import (
    CandidateAction,
    CandidateBuilder,
    CandidateEntryZone,
    CandidateTarget,
    CandidateTradePlan,
    ResearchCandidate,
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

OPEN_TIME = datetime(2026, 8, 26, 10, tzinfo=UTC)
CLOSE_TIME = datetime(2026, 8, 26, 11, tzinfo=UTC)
CREATED_AT = datetime(2026, 8, 26, 11, 1, tzinfo=UTC)
RANKED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)


def create_signal(
    *,
    score: Decimal,
) -> StrategySignal:
    signal_id = build_signal_id(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id="dataset-test",
        candle_close_time=CLOSE_TIME,
        direction=SignalDirection.LONG,
    )

    return StrategySignal(
        signal_id=signal_id,
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id="dataset-test",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        candle_open_time=OPEN_TIME,
        candle_close_time=CLOSE_TIME,
        generated_at=CLOSE_TIME,
        direction=SignalDirection.LONG,
        score=score,
        reason="EMA crossover produced directional evidence.",
        features=(
            StrategyFeature(
                name="fast_ema",
                value=Decimal("101.25"),
            ),
        ),
    )


def trade_plan() -> CandidateTradePlan:
    return CandidateTradePlan(
        entry_zone=CandidateEntryZone(
            lower_price=Decimal("100"),
            upper_price=Decimal("102"),
        ),
        invalidation_price=Decimal("97"),
        targets=(
            CandidateTarget(
                label="target-1",
                price=Decimal("106"),
            ),
        ),
    )


def create_candidate(
    *,
    experiment_id: str,
    confidence: Decimal,
    signal_score: Decimal,
    created_at: datetime = CREATED_AT,
    valid_until: datetime | None = None,
    action: CandidateAction | None = None,
) -> ResearchCandidate:
    return CandidateBuilder.from_signal(
        signal=create_signal(
            score=signal_score,
        ),
        experiment_id=experiment_id,
        horizon_candles=4,
        confidence=confidence,
        created_at=created_at,
        valid_until=valid_until or created_at + timedelta(hours=4),
        action=action,
        trade_plan=(trade_plan() if action is not CandidateAction.NO_TRADE else None),
    )


def test_ranker_orders_candidates_by_explainable_weighted_score() -> None:
    stronger = create_candidate(
        experiment_id="experiment-1111111111111111",
        confidence=Decimal("0.90"),
        signal_score=Decimal("0.80"),
    )
    weaker = create_candidate(
        experiment_id="experiment-2222222222222222",
        confidence=Decimal("0.60"),
        signal_score=Decimal("0.50"),
    )

    result = CandidateRanker().rank(
        candidates=(weaker, stronger),
        at=RANKED_AT,
    )

    assert result.total_candidates == 2
    assert result.eligible_count == 2
    assert result.excluded_count == 0
    assert result.entries[0].candidate.candidate_id == stronger.candidate_id
    assert result.entries[1].candidate.candidate_id == weaker.candidate_id
    assert result.entries[0].total_score > result.entries[1].total_score

    component_names = tuple(component.name for component in result.entries[0].components)
    assert component_names == (
        CandidateRankingComponentName.CONFIDENCE,
        CandidateRankingComponentName.SIGNAL_STRENGTH,
        CandidateRankingComponentName.FRESHNESS,
    )


def test_ranking_is_deterministic_for_input_order() -> None:
    first = create_candidate(
        experiment_id="experiment-3333333333333333",
        confidence=Decimal("0.70"),
        signal_score=Decimal("0.70"),
    )
    second = create_candidate(
        experiment_id="experiment-4444444444444444",
        confidence=Decimal("0.70"),
        signal_score=Decimal("0.70"),
    )

    ranker = CandidateRanker()

    forward = ranker.rank(
        candidates=(first, second),
        at=RANKED_AT,
    )
    reverse = ranker.rank(
        candidates=(second, first),
        at=RANKED_AT,
    )

    assert tuple(entry.candidate.candidate_id for entry in forward.entries) == tuple(
        entry.candidate.candidate_id for entry in reverse.entries
    )


def test_ranker_excludes_non_selectable_candidates() -> None:
    selectable = create_candidate(
        experiment_id="experiment-5555555555555555",
        confidence=Decimal("0.80"),
        signal_score=Decimal("0.70"),
    )
    no_trade = create_candidate(
        experiment_id="experiment-6666666666666666",
        confidence=Decimal("0.95"),
        signal_score=Decimal("0.95"),
        action=CandidateAction.NO_TRADE,
    )
    expired = create_candidate(
        experiment_id="experiment-7777777777777777",
        confidence=Decimal("0.99"),
        signal_score=Decimal("0.99"),
        valid_until=RANKED_AT,
    )

    result = CandidateRanker().rank(
        candidates=(no_trade, expired, selectable),
        at=RANKED_AT,
    )

    assert result.total_candidates == 3
    assert result.eligible_count == 1
    assert result.excluded_count == 2
    assert result.entries[0].candidate.candidate_id == selectable.candidate_id


def test_selected_candidate_is_excluded_from_ranking() -> None:
    candidate = create_candidate(
        experiment_id="experiment-8888888888888888",
        confidence=Decimal("0.80"),
        signal_score=Decimal("0.70"),
    )
    selected = candidate.select(
        selected_at=CREATED_AT + timedelta(minutes=5),
    )

    result = CandidateRanker().rank(
        candidates=(selected,),
        at=RANKED_AT,
    )

    assert result.eligible_count == 0
    assert result.excluded_count == 1
    assert result.entries == ()


def test_freshness_breaks_equal_quality_scores() -> None:
    fresher = create_candidate(
        experiment_id="experiment-9999999999999999",
        confidence=Decimal("0.70"),
        signal_score=Decimal("0.70"),
        created_at=CREATED_AT,
        valid_until=CREATED_AT + timedelta(hours=8),
    )
    older = create_candidate(
        experiment_id="experiment-aaaaaaaaaaaaaaaa",
        confidence=Decimal("0.70"),
        signal_score=Decimal("0.70"),
        created_at=CREATED_AT,
        valid_until=CREATED_AT + timedelta(hours=2),
    )

    result = CandidateRanker().rank(
        candidates=(older, fresher),
        at=RANKED_AT,
    )

    assert result.entries[0].candidate.candidate_id == fresher.candidate_id
    assert result.entries[0].total_score > result.entries[1].total_score


def test_custom_policy_changes_ranking_without_hidden_rules() -> None:
    high_confidence = create_candidate(
        experiment_id="experiment-bbbbbbbbbbbbbbbb",
        confidence=Decimal("0.95"),
        signal_score=Decimal("0.30"),
    )
    high_signal = create_candidate(
        experiment_id="experiment-cccccccccccccccc",
        confidence=Decimal("0.40"),
        signal_score=Decimal("0.95"),
    )

    confidence_policy = CandidateRankingPolicy(
        confidence_weight=Decimal("0.80"),
        signal_strength_weight=Decimal("0.20"),
        freshness_weight=Decimal("0"),
    )
    signal_policy = CandidateRankingPolicy(
        confidence_weight=Decimal("0.10"),
        signal_strength_weight=Decimal("0.90"),
        freshness_weight=Decimal("0"),
    )

    confidence_result = CandidateRanker(
        policy=confidence_policy,
    ).rank(
        candidates=(high_signal, high_confidence),
        at=RANKED_AT,
    )
    signal_result = CandidateRanker(
        policy=signal_policy,
    ).rank(
        candidates=(high_signal, high_confidence),
        at=RANKED_AT,
    )

    assert confidence_result.entries[0].candidate.candidate_id == high_confidence.candidate_id
    assert signal_result.entries[0].candidate.candidate_id == high_signal.candidate_id


def test_ranking_components_reconcile_to_total_score() -> None:
    candidate = create_candidate(
        experiment_id="experiment-dddddddddddddddd",
        confidence=Decimal("0.83"),
        signal_score=Decimal("0.74"),
    )

    entry = (
        CandidateRanker()
        .rank(
            candidates=(candidate,),
            at=RANKED_AT,
        )
        .entries[0]
    )

    assert (
        sum(
            (component.weighted_value for component in entry.components),
            start=Decimal("0"),
        )
        == entry.total_score
    )


def test_policy_rejects_weights_that_do_not_sum_to_one() -> None:
    with pytest.raises(
        ValidationError,
        match="weights must sum to one",
    ):
        CandidateRankingPolicy(
            confidence_weight=Decimal("0.50"),
            signal_strength_weight=Decimal("0.30"),
            freshness_weight=Decimal("0.10"),
        )
