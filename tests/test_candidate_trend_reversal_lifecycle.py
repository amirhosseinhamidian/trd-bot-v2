from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tests.test_candidate_data_quality_lifecycle import (
    lifecycle_dataset_with_monitoring_horizon,
    observation_candles,
    ranked_entries_without_price_exit,
)
from tests.test_candidate_replay_lifecycle import (
    EVALUATED_AT,
    simulated_portfolio,
)
from tests.test_candidate_trend_reversal_exit import signal
from trd_bot.research.dataset_replay_lifecycle import CandidateReplayLifecycleRunner
from trd_bot.research.position_monitoring import (
    CandidateExitDirective,
    CandidateExitReason,
)
from trd_bot.strategies.signals import SignalDirection


def test_opposite_historical_signal_generates_trend_reversal_exit() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    entries = ranked_entries_without_price_exit(dataset_id=dataset.dataset_id)
    selected_candidate = entries[1].candidate

    result = CandidateReplayLifecycleRunner().run(
        entries=entries,
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        historical_signals=(
            signal(
                candidate=selected_candidate,
                hour=14,
                direction=SignalDirection.SHORT,
            ),
        ),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.TREND_REVERSAL
    assert result.monitoring.trigger.occurred_at == datetime(
        2026,
        8,
        26,
        15,
        tzinfo=UTC,
    )
    assert result.monitoring.trigger.price == Decimal("100")


def test_same_direction_historical_signal_preserves_normal_exit() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    entries = ranked_entries_without_price_exit(dataset_id=dataset.dataset_id)
    selected_candidate = entries[1].candidate

    result = CandidateReplayLifecycleRunner().run(
        entries=entries,
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        historical_signals=(
            signal(
                candidate=selected_candidate,
                hour=14,
                direction=SignalDirection.LONG,
            ),
        ),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.TIME_EXPIRY


def test_matching_manual_and_generated_trend_reversal_are_deduplicated() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    entries = ranked_entries_without_price_exit(dataset_id=dataset.dataset_id)
    selected_candidate = entries[1].candidate
    occurred_at = datetime(2026, 8, 26, 15, tzinfo=UTC)

    result = CandidateReplayLifecycleRunner().run(
        entries=entries,
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        exit_directives=(
            CandidateExitDirective(
                reason=CandidateExitReason.TREND_REVERSAL,
                occurred_at=occurred_at,
            ),
        ),
        historical_signals=(
            signal(
                candidate=selected_candidate,
                hour=14,
                direction=SignalDirection.SHORT,
            ),
        ),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.TREND_REVERSAL
    assert result.monitoring.trigger.occurred_at == occurred_at


def test_generated_data_unreliable_wins_generated_trend_reversal_same_time() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    entries = ranked_entries_without_price_exit(dataset_id=dataset.dataset_id)
    selected_candidate = entries[1].candidate

    result = CandidateReplayLifecycleRunner().run(
        entries=entries,
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        monitoring_observations=observation_candles(dataset, 14, 16),
        historical_signals=(
            signal(
                candidate=selected_candidate,
                hour=15,
                direction=SignalDirection.SHORT,
            ),
        ),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.DATA_UNRELIABLE
    assert result.monitoring.trigger.occurred_at == datetime(
        2026,
        8,
        26,
        16,
        tzinfo=UTC,
    )


def test_equal_priority_different_non_data_directives_conflict() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    entries = ranked_entries_without_price_exit(dataset_id=dataset.dataset_id)
    selected_candidate = entries[1].candidate
    occurred_at = datetime(2026, 8, 26, 15, tzinfo=UTC)

    with pytest.raises(
        ValueError,
        match="exit directives with equal priority conflict",
    ):
        CandidateReplayLifecycleRunner().run(
            entries=entries,
            portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
            dataset=dataset,
            evaluated_at=EVALUATED_AT,
            exit_directives=(
                CandidateExitDirective(
                    reason=CandidateExitReason.PORTFOLIO_RISK,
                    occurred_at=occurred_at,
                ),
            ),
            historical_signals=(
                signal(
                    candidate=selected_candidate,
                    hour=14,
                    direction=SignalDirection.SHORT,
                ),
            ),
        )
