from collections.abc import Sequence
from datetime import UTC, datetime

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
from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research.candidate_simulation_runner import CandidateSimulationResult
from trd_bot.research.dataset_replay_lifecycle import CandidateReplayLifecycleRunner
from trd_bot.research.portfolio_risk_exit import (
    CandidatePortfolioRiskExitDirectiveProducer,
)
from trd_bot.research.position_monitoring import (
    CandidateExitDirective,
    CandidateExitReason,
)
from trd_bot.strategies.signals import SignalDirection


class FixedPortfolioRiskExitDirectiveProducer(CandidatePortfolioRiskExitDirectiveProducer):
    def __init__(self, *, occurred_at: datetime) -> None:
        self._occurred_at = occurred_at

    def produce(
        self,
        *,
        simulation: CandidateSimulationResult,
        monitoring_candles: Sequence[OHLCVCandle],
    ) -> tuple[CandidateExitDirective, ...]:
        del simulation, monitoring_candles
        return (
            CandidateExitDirective(
                reason=CandidateExitReason.PORTFOLIO_RISK,
                occurred_at=self._occurred_at,
            ),
        )


def test_generated_portfolio_risk_reaches_position_monitor() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    occurred_at = datetime(2026, 8, 26, 15, tzinfo=UTC)

    result = CandidateReplayLifecycleRunner(
        portfolio_risk_exit_producer=FixedPortfolioRiskExitDirectiveProducer(
            occurred_at=occurred_at,
        )
    ).run(
        entries=ranked_entries_without_price_exit(dataset_id=dataset.dataset_id),
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.PORTFOLIO_RISK
    assert result.monitoring.trigger.occurred_at == occurred_at


def test_matching_manual_and_generated_portfolio_risk_are_deduplicated() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    occurred_at = datetime(2026, 8, 26, 15, tzinfo=UTC)

    result = CandidateReplayLifecycleRunner(
        portfolio_risk_exit_producer=FixedPortfolioRiskExitDirectiveProducer(
            occurred_at=occurred_at,
        )
    ).run(
        entries=ranked_entries_without_price_exit(dataset_id=dataset.dataset_id),
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        exit_directives=(
            CandidateExitDirective(
                reason=CandidateExitReason.PORTFOLIO_RISK,
                occurred_at=occurred_at,
            ),
        ),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.PORTFOLIO_RISK
    assert result.monitoring.trigger.occurred_at == occurred_at


def test_data_unreliable_wins_generated_portfolio_risk_same_time() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    occurred_at = datetime(2026, 8, 26, 16, tzinfo=UTC)

    result = CandidateReplayLifecycleRunner(
        portfolio_risk_exit_producer=FixedPortfolioRiskExitDirectiveProducer(
            occurred_at=occurred_at,
        )
    ).run(
        entries=ranked_entries_without_price_exit(dataset_id=dataset.dataset_id),
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        monitoring_observations=observation_candles(dataset, 14, 16),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.DATA_UNRELIABLE
    assert result.monitoring.trigger.occurred_at == occurred_at


def test_generated_trend_reversal_and_portfolio_risk_same_time_conflict() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    entries = ranked_entries_without_price_exit(dataset_id=dataset.dataset_id)
    selected_candidate = entries[1].candidate
    occurred_at = datetime(2026, 8, 26, 15, tzinfo=UTC)

    with pytest.raises(
        ValueError,
        match="exit directives with equal priority conflict",
    ):
        CandidateReplayLifecycleRunner(
            portfolio_risk_exit_producer=FixedPortfolioRiskExitDirectiveProducer(
                occurred_at=occurred_at,
            )
        ).run(
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
