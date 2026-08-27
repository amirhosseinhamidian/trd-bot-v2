from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.backtesting.models import PositionSide
from trd_bot.paper import (
    PortfolioStatus,
    PositionStatus,
    SimulatedPortfolio,
    SimulatedPortfolioLedger,
    SimulatedPosition,
)
from trd_bot.research.candidates import (
    CandidateAction,
    CandidateStatus,
    ResearchCandidate,
    normalize_candidate_timestamp,
)
from trd_bot.research.risk_policy import (
    CandidateRiskAssessment,
    CandidateRiskDecision,
)

SIMULATION_QUANTITY_QUANTUM = Decimal("0.00000001")


class CandidateSimulationResult(BaseModel):
    """Auditable result of opening one offline paper/shadow position."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    opened_at: datetime
    fill_price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)

    assessment: CandidateRiskAssessment
    selected_candidate: ResearchCandidate
    opened_position: SimulatedPosition
    portfolio: SimulatedPortfolio

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        normalized_time = normalize_candidate_timestamp(self.opened_at)
        if normalized_time != self.opened_at:
            raise ValueError("simulation open time must be normalized to UTC")

        if self.assessment.decision is not CandidateRiskDecision.APPROVED:
            raise ValueError("simulation result requires an approved risk assessment")

        source_candidate = self.assessment.ranking_entry.candidate
        if self.selected_candidate.candidate_id != source_candidate.candidate_id:
            raise ValueError("selected candidate does not match risk assessment")

        if self.selected_candidate.status is not CandidateStatus.SELECTED:
            raise ValueError("simulation result requires a selected candidate")

        if self.selected_candidate.status_changed_at != self.opened_at:
            raise ValueError("candidate selection time must match simulated open time")

        if self.portfolio.portfolio_id != self.assessment.portfolio_id:
            raise ValueError("simulated portfolio does not match risk assessment")

        if self.opened_position.portfolio_id != self.portfolio.portfolio_id:
            raise ValueError("opened position belongs to another simulated portfolio")

        if self.opened_position.status is not PositionStatus.OPEN:
            raise ValueError("simulation result requires an open simulated position")

        if self.opened_position.pair != self.selected_candidate.pair:
            raise ValueError("opened position pair does not match selected candidate")

        if self.opened_position.entry_price != self.fill_price:
            raise ValueError("opened position price does not match simulation fill")

        if self.opened_position.quantity != self.quantity:
            raise ValueError("opened position quantity does not match simulation result")

        if self.opened_position.opened_at != self.opened_at:
            raise ValueError("opened position time does not match simulation result")

        matching_positions = tuple(
            position
            for position in self.portfolio.positions
            if position.position_id == self.opened_position.position_id
        )
        if matching_positions != (self.opened_position,):
            raise ValueError("opened position is not present exactly once in portfolio")

        return self


class CandidateSimulationRunner:
    """Convert one approved candidate into an offline paper/shadow position."""

    def __init__(
        self,
        *,
        ledger: SimulatedPortfolioLedger | None = None,
    ) -> None:
        self._ledger = ledger or SimulatedPortfolioLedger()

    def run(
        self,
        *,
        assessment: CandidateRiskAssessment,
        portfolio: SimulatedPortfolio,
        fill_price: Decimal,
        occurred_at: datetime,
    ) -> CandidateSimulationResult:
        opened_at = normalize_candidate_timestamp(occurred_at)

        if assessment.decision is not CandidateRiskDecision.APPROVED:
            raise ValueError("risk assessment must be approved before simulation")

        if assessment.portfolio_id != portfolio.portfolio_id:
            raise ValueError("risk assessment belongs to another simulated portfolio")

        if assessment.portfolio_updated_at != portfolio.updated_at:
            raise ValueError("simulated portfolio changed after risk assessment")

        if opened_at < assessment.evaluated_at:
            raise ValueError("simulation cannot precede risk assessment")

        if portfolio.status is not PortfolioStatus.ACTIVE:
            raise ValueError("simulated portfolio must be active")

        if any(position.status is PositionStatus.OPEN for position in portfolio.positions):
            raise ValueError("simulated portfolio already has an open position")

        candidate = assessment.ranking_entry.candidate
        if candidate.dataset_id != portfolio.dataset_id:
            raise ValueError("candidate and simulated portfolio dataset must match")

        if not candidate.is_selectable(at=opened_at):
            raise ValueError("candidate is no longer selectable for simulation")

        trade_plan = candidate.trade_plan
        if trade_plan is None:
            raise ValueError("directional candidate requires a trade plan")

        if not (
            trade_plan.entry_zone.lower_price <= fill_price <= trade_plan.entry_zone.upper_price
        ):
            raise ValueError("simulation fill price must be inside candidate entry zone")

        quantity = self._simulation_quantity(
            assessment=assessment,
            portfolio=portfolio,
            fill_price=fill_price,
        )
        if quantity <= 0:
            raise ValueError("approved assessment leaves no executable simulated quantity")

        selected_candidate = candidate.select(
            selected_at=opened_at,
        )
        side = self._position_side(selected_candidate.action)

        updated_portfolio = self._ledger.open_position(
            portfolio,
            pair=selected_candidate.pair,
            side=side,
            price=fill_price,
            quantity=quantity,
            occurred_at=opened_at,
        )
        opened_position = updated_portfolio.positions[-1]

        return CandidateSimulationResult(
            opened_at=opened_at,
            fill_price=fill_price,
            quantity=quantity,
            assessment=assessment,
            selected_candidate=selected_candidate,
            opened_position=opened_position,
            portfolio=updated_portfolio,
        )

    @staticmethod
    def _position_side(action: CandidateAction) -> PositionSide:
        if action is CandidateAction.LONG:
            return PositionSide.LONG

        if action is CandidateAction.SHORT:
            return PositionSide.SHORT

        raise ValueError("simulation runner only accepts directional candidates")

    @staticmethod
    def _simulation_quantity(
        *,
        assessment: CandidateRiskAssessment,
        portfolio: SimulatedPortfolio,
        fill_price: Decimal,
    ) -> Decimal:
        candidate = assessment.ranking_entry.candidate
        trade_plan = candidate.trade_plan

        if trade_plan is None:
            raise ValueError("directional candidate requires a trade plan")

        unit_price_risk = abs(fill_price - trade_plan.invalidation_price)
        if unit_price_risk <= 0:
            raise ValueError("simulation unit price risk must be greater than zero")

        risk_limited = assessment.risk_budget / unit_price_risk
        notional_limited = assessment.notional_budget / fill_price

        per_unit_commitment = fill_price * (Decimal("1") + portfolio.fee_rate)
        cash_limited = portfolio.cash / per_unit_commitment

        return min(
            assessment.max_simulated_quantity,
            risk_limited,
            notional_limited,
            cash_limited,
        ).quantize(
            SIMULATION_QUANTITY_QUANTUM,
            rounding=ROUND_DOWN,
        )
