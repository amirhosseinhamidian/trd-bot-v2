from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.research.candidates import (
    CandidateAction,
    CandidateBuilder,
    CandidateEntryZone,
    CandidateStatus,
    CandidateTarget,
    CandidateTradePlan,
    build_candidate_id,
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
VALID_UNTIL = datetime(2026, 8, 26, 15, tzinfo=UTC)
EXPERIMENT_ID = "experiment-0123456789abcdef"


def create_signal(
    *,
    direction: SignalDirection = SignalDirection.LONG,
    score: Decimal = Decimal("0.75"),
) -> StrategySignal:
    signal_id = build_signal_id(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id="dataset-test",
        candle_close_time=CLOSE_TIME,
        direction=direction,
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
        direction=direction,
        score=score,
        reason="EMA crossover produced directional evidence.",
        features=(
            StrategyFeature(
                name="fast_ema",
                value=Decimal("101.25"),
            ),
            StrategyFeature(
                name="slow_ema",
                value=Decimal("99.50"),
            ),
        ),
    )


def long_plan() -> CandidateTradePlan:
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
            CandidateTarget(
                label="target-2",
                price=Decimal("110"),
            ),
        ),
    )


def test_builder_creates_traceable_directional_candidate() -> None:
    signal = create_signal()

    candidate = CandidateBuilder.from_signal(
        signal=signal,
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.70"),
        created_at=CREATED_AT,
        valid_until=VALID_UNTIL,
        trade_plan=long_plan(),
    )

    assert candidate.action is CandidateAction.LONG
    assert candidate.status is CandidateStatus.CANDIDATE
    assert candidate.dataset_id == signal.dataset_id
    assert candidate.experiment_id == EXPERIMENT_ID
    assert candidate.signal_id == signal.signal_id
    assert candidate.signal_score == signal.score
    assert candidate.confidence == Decimal("0.70")
    assert candidate.trade_plan == long_plan()
    assert tuple(item.name for item in candidate.evidence) == (
        "reason",
        "fast_ema",
        "slow_ema",
    )


def test_candidate_id_is_deterministic() -> None:
    signal = create_signal()

    first = build_candidate_id(
        experiment_id=EXPERIMENT_ID,
        signal_id=signal.signal_id,
        action=CandidateAction.LONG,
        horizon_candles=4,
    )
    second = build_candidate_id(
        experiment_id=EXPERIMENT_ID,
        signal_id=signal.signal_id,
        action=CandidateAction.LONG,
        horizon_candles=4,
    )

    assert first == second
    assert first.startswith("candidate-")


def test_neutral_signal_builds_non_directional_candidate() -> None:
    signal = create_signal(
        direction=SignalDirection.NEUTRAL,
        score=Decimal("0"),
    )

    candidate = CandidateBuilder.from_signal(
        signal=signal,
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.25"),
        created_at=CREATED_AT,
        valid_until=VALID_UNTIL,
    )

    assert candidate.action is CandidateAction.NEUTRAL
    assert candidate.trade_plan is None
    assert candidate.is_selectable(at=CREATED_AT) is False


def test_directional_signal_can_be_downgraded_to_no_trade() -> None:
    candidate = CandidateBuilder.from_signal(
        signal=create_signal(),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.40"),
        created_at=CREATED_AT,
        valid_until=VALID_UNTIL,
        action=CandidateAction.NO_TRADE,
    )

    assert candidate.action is CandidateAction.NO_TRADE
    assert candidate.trade_plan is None
    assert candidate.is_selectable(at=CREATED_AT) is False


def test_builder_rejects_direction_reversal() -> None:
    with pytest.raises(
        ValueError,
        match="cannot reverse",
    ):
        CandidateBuilder.from_signal(
            signal=create_signal(),
            experiment_id=EXPERIMENT_ID,
            horizon_candles=4,
            confidence=Decimal("0.70"),
            created_at=CREATED_AT,
            valid_until=VALID_UNTIL,
            action=CandidateAction.SHORT,
            trade_plan=long_plan(),
        )


def test_long_candidate_rejects_invalidation_inside_entry_zone() -> None:
    invalid_plan = CandidateTradePlan(
        entry_zone=CandidateEntryZone(
            lower_price=Decimal("100"),
            upper_price=Decimal("102"),
        ),
        invalidation_price=Decimal("101"),
        targets=(
            CandidateTarget(
                label="target-1",
                price=Decimal("106"),
            ),
        ),
    )

    with pytest.raises(
        ValidationError,
        match="long invalidation",
    ):
        CandidateBuilder.from_signal(
            signal=create_signal(),
            experiment_id=EXPERIMENT_ID,
            horizon_candles=4,
            confidence=Decimal("0.70"),
            created_at=CREATED_AT,
            valid_until=VALID_UNTIL,
            trade_plan=invalid_plan,
        )


def test_directional_candidate_requires_trade_plan() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a trade plan",
    ):
        CandidateBuilder.from_signal(
            signal=create_signal(),
            experiment_id=EXPERIMENT_ID,
            horizon_candles=4,
            confidence=Decimal("0.70"),
            created_at=CREATED_AT,
            valid_until=VALID_UNTIL,
        )


def test_candidate_can_be_selected_before_expiry() -> None:
    candidate = CandidateBuilder.from_signal(
        signal=create_signal(),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.70"),
        created_at=CREATED_AT,
        valid_until=VALID_UNTIL,
        trade_plan=long_plan(),
    )

    selected_at = CREATED_AT + timedelta(minutes=5)
    selected = candidate.select(selected_at=selected_at)

    assert selected.status is CandidateStatus.SELECTED
    assert selected.status_changed_at == selected_at
    assert selected.select(selected_at=selected_at) == selected


def test_candidate_cannot_be_selected_at_or_after_expiry() -> None:
    candidate = CandidateBuilder.from_signal(
        signal=create_signal(),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.70"),
        created_at=CREATED_AT,
        valid_until=VALID_UNTIL,
        trade_plan=long_plan(),
    )

    with pytest.raises(
        ValueError,
        match="not selectable",
    ):
        candidate.select(selected_at=VALID_UNTIL)


def test_expired_candidate_can_be_marked_stale() -> None:
    candidate = CandidateBuilder.from_signal(
        signal=create_signal(),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.70"),
        created_at=CREATED_AT,
        valid_until=VALID_UNTIL,
        trade_plan=long_plan(),
    )

    stale = candidate.mark_stale(stale_at=VALID_UNTIL)

    assert stale.status is CandidateStatus.STALE
    assert stale.status_changed_at == VALID_UNTIL
    assert stale.mark_stale(stale_at=VALID_UNTIL) == stale


def test_candidate_can_be_invalidated_before_expiry() -> None:
    candidate = CandidateBuilder.from_signal(
        signal=create_signal(),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.70"),
        created_at=CREATED_AT,
        valid_until=VALID_UNTIL,
        trade_plan=long_plan(),
    )

    invalidated_at = CREATED_AT + timedelta(minutes=10)
    invalidated = candidate.invalidate(
        invalidated_at=invalidated_at,
    )

    assert invalidated.status is CandidateStatus.INVALIDATED
    assert invalidated.status_changed_at == invalidated_at
