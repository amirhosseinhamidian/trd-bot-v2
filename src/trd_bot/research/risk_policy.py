from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.backtesting.performance import quantize_money
from trd_bot.paper.portfolio import (
    PortfolioStatus,
    PositionStatus,
    SimulatedPortfolio,
)
from trd_bot.research.candidate_ranking import CandidateRankingEntry
from trd_bot.research.candidates import (
    CandidateAction,
    normalize_candidate_timestamp,
)

SIMULATED_QUANTITY_QUANTUM = Decimal("0.00000001")


class CandidateRiskDecision(StrEnum):
    """Paper/shadow risk-policy outcome for one ranked candidate."""

    APPROVED = "approved"
    REJECTED = "rejected"


class CandidateRiskCheckName(StrEnum):
    """Deterministic checks applied before paper/shadow simulation."""

    CANDIDATE_SELECTABLE = "candidate_selectable"
    PORTFOLIO_ACTIVE = "portfolio_active"
    DATASET_MATCH = "dataset_match"
    PORTFOLIO_CAPACITY = "portfolio_capacity"
    RANK_LIMIT = "rank_limit"
    RANKING_SCORE = "ranking_score"
    REWARD_RISK = "reward_risk"
    SIMULATED_BUDGET = "simulated_budget"


class CandidateRiskCheck(BaseModel):
    """Explainable outcome of one risk-policy rule."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    name: CandidateRiskCheckName
    passed: bool
    actual_value: str = Field(min_length=1, max_length=100)
    limit_value: str | None = Field(default=None, min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)


class CandidateRiskPolicy(BaseModel):
    """Conservative limits for offline paper/shadow candidate evaluation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    max_candidate_rank: int = Field(default=5, ge=1)
    min_ranking_score: Decimal = Field(
        default=Decimal("0.50"),
        ge=0,
        le=1,
    )
    max_risk_fraction: Decimal = Field(
        default=Decimal("0.01"),
        gt=0,
        le=1,
    )
    max_notional_fraction: Decimal = Field(
        default=Decimal("0.25"),
        gt=0,
        le=1,
    )
    cash_buffer_fraction: Decimal = Field(
        default=Decimal("0.05"),
        ge=0,
        lt=1,
    )
    min_reward_risk_ratio: Decimal = Field(
        default=Decimal("1.50"),
        gt=0,
    )


class CandidateRiskAssessment(BaseModel):
    """Auditable result of applying risk policy to one ranked candidate."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    evaluated_at: datetime
    decision: CandidateRiskDecision
    portfolio_id: str = Field(pattern=r"^portfolio-[a-f0-9]{16}$")
    portfolio_updated_at: datetime
    ranking_entry: CandidateRankingEntry
    checks: tuple[CandidateRiskCheck, ...]

    risk_budget: Decimal = Field(ge=0)
    notional_budget: Decimal = Field(ge=0)
    worst_case_entry_price: Decimal = Field(gt=0)
    unit_price_risk: Decimal = Field(gt=0)
    reward_risk_ratio: Decimal = Field(ge=0)
    max_simulated_quantity: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_assessment(self) -> Self:
        normalized_time = normalize_candidate_timestamp(self.evaluated_at)
        if normalized_time != self.evaluated_at:
            raise ValueError("risk assessment time must be normalized to UTC")

        normalized_portfolio_time = normalize_candidate_timestamp(self.portfolio_updated_at)
        if normalized_portfolio_time != self.portfolio_updated_at:
            raise ValueError("portfolio snapshot time must be normalized to UTC")

        names = tuple(check.name for check in self.checks)
        if len(names) != len(set(names)):
            raise ValueError("risk assessment check names must be unique")

        expected_names = tuple(CandidateRiskCheckName)
        if names != expected_names:
            raise ValueError("risk assessment checks must be complete and ordered")

        all_passed = all(check.passed for check in self.checks)
        expected_decision = (
            CandidateRiskDecision.APPROVED if all_passed else CandidateRiskDecision.REJECTED
        )
        if self.decision is not expected_decision:
            raise ValueError("risk assessment decision does not match checks")

        return self


class CandidateRiskEvaluator:
    """Evaluate ranked candidates for offline paper/shadow simulation only."""

    def __init__(
        self,
        *,
        policy: CandidateRiskPolicy | None = None,
    ) -> None:
        self._policy = policy or CandidateRiskPolicy()

    @property
    def policy(self) -> CandidateRiskPolicy:
        return self._policy

    def evaluate(
        self,
        *,
        entry: CandidateRankingEntry,
        portfolio: SimulatedPortfolio,
        at: datetime,
    ) -> CandidateRiskAssessment:
        evaluated_at = normalize_candidate_timestamp(at)
        candidate = entry.candidate
        trade_plan = candidate.trade_plan

        if trade_plan is None:
            raise ValueError("ranked directional candidate requires a trade plan")

        worst_case_entry_price = self._worst_case_entry_price(entry)
        unit_price_risk = abs(worst_case_entry_price - trade_plan.invalidation_price)
        first_target = trade_plan.targets[0].price
        unit_reward = abs(first_target - worst_case_entry_price)

        if unit_price_risk <= 0:
            raise ValueError("candidate unit price risk must be greater than zero")

        reward_risk_ratio = _quantize_ratio(unit_reward / unit_price_risk)

        positive_equity = max(
            portfolio.equity,
            Decimal("0"),
        )
        risk_budget = quantize_money(positive_equity * self._policy.max_risk_fraction)

        equity_notional_cap = quantize_money(positive_equity * self._policy.max_notional_fraction)
        cash_after_buffer = quantize_money(
            portfolio.cash * (Decimal("1") - self._policy.cash_buffer_fraction)
        )
        notional_budget = min(
            equity_notional_cap,
            cash_after_buffer,
        )

        max_simulated_quantity = _max_simulated_quantity(
            risk_budget=risk_budget,
            notional_budget=notional_budget,
            entry_price=worst_case_entry_price,
            unit_price_risk=unit_price_risk,
        )

        checks = self._checks(
            entry=entry,
            portfolio=portfolio,
            evaluated_at=evaluated_at,
            reward_risk_ratio=reward_risk_ratio,
            max_simulated_quantity=max_simulated_quantity,
        )

        decision = (
            CandidateRiskDecision.APPROVED
            if all(check.passed for check in checks)
            else CandidateRiskDecision.REJECTED
        )

        return CandidateRiskAssessment(
            evaluated_at=evaluated_at,
            decision=decision,
            portfolio_id=portfolio.portfolio_id,
            portfolio_updated_at=portfolio.updated_at,
            ranking_entry=entry,
            checks=checks,
            risk_budget=risk_budget,
            notional_budget=notional_budget,
            worst_case_entry_price=worst_case_entry_price,
            unit_price_risk=unit_price_risk,
            reward_risk_ratio=reward_risk_ratio,
            max_simulated_quantity=max_simulated_quantity,
        )

    def _checks(
        self,
        *,
        entry: CandidateRankingEntry,
        portfolio: SimulatedPortfolio,
        evaluated_at: datetime,
        reward_risk_ratio: Decimal,
        max_simulated_quantity: Decimal,
    ) -> tuple[CandidateRiskCheck, ...]:
        candidate = entry.candidate

        selectable = candidate.is_selectable(at=evaluated_at)
        portfolio_active = portfolio.status is PortfolioStatus.ACTIVE
        dataset_matches = candidate.dataset_id == portfolio.dataset_id
        has_capacity = not any(
            position.status is PositionStatus.OPEN for position in portfolio.positions
        )
        rank_allowed = entry.rank <= self._policy.max_candidate_rank
        score_allowed = entry.total_score >= self._policy.min_ranking_score
        reward_risk_allowed = reward_risk_ratio >= self._policy.min_reward_risk_ratio
        budget_available = max_simulated_quantity > 0

        return (
            CandidateRiskCheck(
                name=CandidateRiskCheckName.CANDIDATE_SELECTABLE,
                passed=selectable,
                actual_value=str(selectable).lower(),
                limit_value="true",
                reason=(
                    "Candidate must remain fresh, directional, and unselected at evaluation time."
                ),
            ),
            CandidateRiskCheck(
                name=CandidateRiskCheckName.PORTFOLIO_ACTIVE,
                passed=portfolio_active,
                actual_value=portfolio.status.value,
                limit_value=PortfolioStatus.ACTIVE.value,
                reason="Only an active simulated portfolio can accept a candidate.",
            ),
            CandidateRiskCheck(
                name=CandidateRiskCheckName.DATASET_MATCH,
                passed=dataset_matches,
                actual_value=candidate.dataset_id,
                limit_value=portfolio.dataset_id,
                reason="Candidate and simulated portfolio must share dataset lineage.",
            ),
            CandidateRiskCheck(
                name=CandidateRiskCheckName.PORTFOLIO_CAPACITY,
                passed=has_capacity,
                actual_value=str(
                    sum(position.status is PositionStatus.OPEN for position in portfolio.positions)
                ),
                limit_value="0",
                reason=(
                    "Current simulated portfolio contract allows only one open position at a time."
                ),
            ),
            CandidateRiskCheck(
                name=CandidateRiskCheckName.RANK_LIMIT,
                passed=rank_allowed,
                actual_value=str(entry.rank),
                limit_value=str(self._policy.max_candidate_rank),
                reason="Candidate rank must be inside the configured selection band.",
            ),
            CandidateRiskCheck(
                name=CandidateRiskCheckName.RANKING_SCORE,
                passed=score_allowed,
                actual_value=str(entry.total_score),
                limit_value=str(self._policy.min_ranking_score),
                reason="Candidate ranking score must meet the configured floor.",
            ),
            CandidateRiskCheck(
                name=CandidateRiskCheckName.REWARD_RISK,
                passed=reward_risk_allowed,
                actual_value=str(reward_risk_ratio),
                limit_value=str(self._policy.min_reward_risk_ratio),
                reason=(
                    "First target reward-to-risk must meet the configured paper/shadow threshold."
                ),
            ),
            CandidateRiskCheck(
                name=CandidateRiskCheckName.SIMULATED_BUDGET,
                passed=budget_available,
                actual_value=str(max_simulated_quantity),
                limit_value="> 0",
                reason=("Risk and notional caps must leave positive simulated quantity capacity."),
            ),
        )

    @staticmethod
    def _worst_case_entry_price(
        entry: CandidateRankingEntry,
    ) -> Decimal:
        candidate = entry.candidate
        trade_plan = candidate.trade_plan

        if trade_plan is None:
            raise ValueError("ranked directional candidate requires a trade plan")

        if candidate.action is CandidateAction.LONG:
            return trade_plan.entry_zone.upper_price

        if candidate.action is CandidateAction.SHORT:
            return trade_plan.entry_zone.lower_price

        raise ValueError("risk policy only accepts directional ranked candidates")


def _max_simulated_quantity(
    *,
    risk_budget: Decimal,
    notional_budget: Decimal,
    entry_price: Decimal,
    unit_price_risk: Decimal,
) -> Decimal:
    if risk_budget <= 0 or notional_budget <= 0 or entry_price <= 0 or unit_price_risk <= 0:
        return Decimal("0")

    risk_limited = risk_budget / unit_price_risk
    notional_limited = notional_budget / entry_price

    return min(
        risk_limited,
        notional_limited,
    ).quantize(
        SIMULATED_QUANTITY_QUANTUM,
        rounding=ROUND_DOWN,
    )


def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(
        Decimal("0.000001"),
        rounding=ROUND_DOWN,
    )
