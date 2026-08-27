from collections.abc import Sequence
from decimal import Decimal

from trd_bot.backtesting.performance import quantize_money
from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.paper.portfolio import SimulatedPortfolioLedger
from trd_bot.research.candidate_simulation_runner import CandidateSimulationResult
from trd_bot.research.position_monitoring import (
    CandidateExitDirective,
    CandidateExitReason,
)


class CandidatePortfolioRiskExitDirectiveProducer:
    """Convert an approved simulated risk-budget breach into an offline exit directive."""

    def __init__(
        self,
        *,
        ledger: SimulatedPortfolioLedger | None = None,
    ) -> None:
        self._ledger = ledger or SimulatedPortfolioLedger()

    def produce(
        self,
        *,
        simulation: CandidateSimulationResult,
        monitoring_candles: Sequence[OHLCVCandle],
    ) -> tuple[CandidateExitDirective, ...]:
        self._validate_monitoring_candles(
            simulation=simulation,
            monitoring_candles=monitoring_candles,
        )

        risk_budget = simulation.assessment.risk_budget
        if risk_budget <= 0:
            return ()

        baseline_equity = simulation.portfolio.equity
        current_portfolio = simulation.portfolio

        ordered_candles = tuple(
            sorted(
                (
                    candle
                    for candle in monitoring_candles
                    if candle.is_closed and candle.close_time > simulation.opened_at
                ),
                key=lambda candle: (
                    candle.close_time,
                    candle.open_time,
                ),
            )
        )

        for candle in ordered_candles:
            current_portfolio = self._ledger.mark_to_market(
                current_portfolio,
                position_id=simulation.opened_position.position_id,
                price=candle.close_price,
                occurred_at=candle.close_time,
            )
            equity_drawdown = quantize_money(
                max(
                    baseline_equity - current_portfolio.equity,
                    Decimal("0"),
                )
            )
            if equity_drawdown >= risk_budget:
                return (
                    CandidateExitDirective(
                        reason=CandidateExitReason.PORTFOLIO_RISK,
                        occurred_at=candle.close_time,
                    ),
                )

        return ()

    @staticmethod
    def _validate_monitoring_candles(
        *,
        simulation: CandidateSimulationResult,
        monitoring_candles: Sequence[OHLCVCandle],
    ) -> None:
        candidate = simulation.selected_candidate

        mismatched = any(
            candle.pair != candidate.pair or candle.timeframe is not candidate.timeframe
            for candle in monitoring_candles
        )
        if mismatched:
            raise ValueError("portfolio risk monitoring candles must match selected candidate")
