from collections.abc import Sequence
from datetime import datetime

from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research.candidates import CandidateAction, ResearchCandidate
from trd_bot.research.position_monitoring import (
    CandidateExitDirective,
    CandidateExitReason,
)
from trd_bot.strategies.signals import SignalDirection, StrategySignal


class CandidateTrendReversalExitDirectiveProducer:
    """Convert opposite historical strategy signals into offline exit directives."""

    def produce(
        self,
        *,
        candidate: ResearchCandidate,
        opened_at: datetime,
        signals: Sequence[StrategySignal],
        monitoring_candles: Sequence[OHLCVCandle],
    ) -> tuple[CandidateExitDirective, ...]:
        opposite_direction = self._opposite_direction(candidate.action)
        monitoring_close_times = {
            candle.close_time for candle in monitoring_candles if candle.is_closed
        }

        matching_signals = tuple(
            signal
            for signal in signals
            if self._matches_candidate(
                signal=signal,
                candidate=candidate,
            )
            and signal.direction is opposite_direction
            and signal.candle_close_time > opened_at
            and signal.candle_close_time in monitoring_close_times
        )
        if not matching_signals:
            return ()

        first_reversal = min(
            matching_signals,
            key=lambda signal: (
                signal.candle_close_time,
                signal.signal_id,
            ),
        )

        return (
            CandidateExitDirective(
                reason=CandidateExitReason.TREND_REVERSAL,
                occurred_at=first_reversal.candle_close_time,
            ),
        )

    @staticmethod
    def _matches_candidate(
        *,
        signal: StrategySignal,
        candidate: ResearchCandidate,
    ) -> bool:
        return (
            signal.dataset_id == candidate.dataset_id
            and signal.strategy_name == candidate.strategy_name
            and signal.strategy_version == candidate.strategy_version
            and signal.pair == candidate.pair
            and signal.timeframe is candidate.timeframe
        )

    @staticmethod
    def _opposite_direction(
        action: CandidateAction,
    ) -> SignalDirection:
        if action is CandidateAction.LONG:
            return SignalDirection.SHORT
        if action is CandidateAction.SHORT:
            return SignalDirection.LONG

        raise ValueError("trend reversal producer requires a directional candidate")
