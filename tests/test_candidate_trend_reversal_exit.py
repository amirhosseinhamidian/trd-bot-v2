from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tests.test_candidate_replay_lifecycle import (
    candidate,
    lifecycle_dataset,
)
from trd_bot.research.candidates import ResearchCandidate
from trd_bot.research.position_monitoring import CandidateExitReason
from trd_bot.research.trend_reversal_exit import (
    CandidateTrendReversalExitDirectiveProducer,
)
from trd_bot.strategies.signals import (
    SignalDirection,
    StrategySignal,
    build_signal_id,
)


def build_candidate() -> ResearchCandidate:
    dataset = lifecycle_dataset()
    return candidate(
        dataset_id=dataset.dataset_id,
        experiment_id="experiment-6666666666666666",
        confidence="0.80",
        entry_low="100",
        entry_high="102",
        invalidation="98",
        target="108",
    )


def signal(
    *,
    candidate: ResearchCandidate,
    hour: int,
    direction: SignalDirection,
    strategy_name: str | None = None,
) -> StrategySignal:
    candle_open_time = datetime(2026, 8, 26, hour, tzinfo=UTC)
    candle_close_time = datetime(2026, 8, 26, hour + 1, tzinfo=UTC)
    name = strategy_name or candidate.strategy_name
    score = Decimal("0.5") if direction is SignalDirection.LONG else Decimal("-0.5")

    return StrategySignal(
        signal_id=build_signal_id(
            strategy_name=name,
            strategy_version=candidate.strategy_version,
            dataset_id=candidate.dataset_id,
            candle_close_time=candle_close_time,
            direction=direction,
        ),
        strategy_name=name,
        strategy_version=candidate.strategy_version,
        dataset_id=candidate.dataset_id,
        pair=candidate.pair,
        timeframe=candidate.timeframe,
        candle_open_time=candle_open_time,
        candle_close_time=candle_close_time,
        generated_at=candle_close_time,
        direction=direction,
        score=score,
        reason="Historical strategy signal for trend reversal testing.",
    )


def test_opposite_signal_produces_trend_reversal_directive() -> None:
    dataset = lifecycle_dataset()
    selected_candidate = build_candidate()

    directives = CandidateTrendReversalExitDirectiveProducer().produce(
        candidate=selected_candidate,
        opened_at=datetime(2026, 8, 26, 13, tzinfo=UTC),
        signals=(
            signal(
                candidate=selected_candidate,
                hour=13,
                direction=SignalDirection.SHORT,
            ),
        ),
        monitoring_candles=dataset.candles,
    )

    assert len(directives) == 1
    assert directives[0].reason is CandidateExitReason.TREND_REVERSAL
    assert directives[0].occurred_at == datetime(2026, 8, 26, 14, tzinfo=UTC)


def test_same_direction_signal_does_not_produce_reversal() -> None:
    dataset = lifecycle_dataset()
    selected_candidate = build_candidate()

    directives = CandidateTrendReversalExitDirectiveProducer().produce(
        candidate=selected_candidate,
        opened_at=datetime(2026, 8, 26, 13, tzinfo=UTC),
        signals=(
            signal(
                candidate=selected_candidate,
                hour=13,
                direction=SignalDirection.LONG,
            ),
        ),
        monitoring_candles=dataset.candles,
    )

    assert directives == ()


def test_producer_uses_earliest_matching_opposite_signal() -> None:
    dataset = lifecycle_dataset()
    selected_candidate = build_candidate()

    directives = CandidateTrendReversalExitDirectiveProducer().produce(
        candidate=selected_candidate,
        opened_at=datetime(2026, 8, 26, 12, tzinfo=UTC),
        signals=(
            signal(
                candidate=selected_candidate,
                hour=14,
                direction=SignalDirection.SHORT,
            ),
            signal(
                candidate=selected_candidate,
                hour=13,
                direction=SignalDirection.SHORT,
            ),
        ),
        monitoring_candles=dataset.candles,
    )

    assert len(directives) == 1
    assert directives[0].occurred_at == datetime(2026, 8, 26, 14, tzinfo=UTC)


def test_unrelated_strategy_signal_is_ignored() -> None:
    dataset = lifecycle_dataset()
    selected_candidate = build_candidate()

    directives = CandidateTrendReversalExitDirectiveProducer().produce(
        candidate=selected_candidate,
        opened_at=datetime(2026, 8, 26, 13, tzinfo=UTC),
        signals=(
            signal(
                candidate=selected_candidate,
                hour=13,
                direction=SignalDirection.SHORT,
                strategy_name="other-strategy",
            ),
        ),
        monitoring_candles=dataset.candles,
    )

    assert directives == ()


def test_signal_outside_monitoring_horizon_is_ignored() -> None:
    dataset = lifecycle_dataset()
    selected_candidate = build_candidate()

    directives = CandidateTrendReversalExitDirectiveProducer().produce(
        candidate=selected_candidate,
        opened_at=datetime(2026, 8, 26, 13, tzinfo=UTC),
        signals=(
            signal(
                candidate=selected_candidate,
                hour=16,
                direction=SignalDirection.SHORT,
            ),
        ),
        monitoring_candles=dataset.candles,
    )

    assert directives == ()


def test_non_directional_candidate_is_rejected() -> None:
    dataset = lifecycle_dataset()
    selected_candidate = build_candidate().model_copy(
        update={"action": "neutral"},
    )

    with pytest.raises(
        ValueError,
        match="trend reversal producer requires a directional candidate",
    ):
        CandidateTrendReversalExitDirectiveProducer().produce(
            candidate=selected_candidate,
            opened_at=datetime(2026, 8, 26, 13, tzinfo=UTC),
            signals=(),
            monitoring_candles=dataset.candles,
        )
