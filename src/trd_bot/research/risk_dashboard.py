from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.backtesting.performance import quantize_money
from trd_bot.domain.market_data import TradingPair
from trd_bot.paper.portfolio import (
    PortfolioEventType,
    PortfolioTimelineEvent,
    SimulatedPortfolio,
)
from trd_bot.research.candidate_journal import CandidateJournalEntry
from trd_bot.research.candidates import normalize_candidate_timestamp
from trd_bot.research.dataset_replay import CandidateReplayStatus
from trd_bot.research.risk_policy import (
    CandidateRiskCheckName,
    CandidateRiskDecision,
    CandidateRiskPolicy,
)

RATIO_QUANTUM = Decimal("0.000001")


def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


class RiskDecisionSummary(BaseModel):
    """Decision denominator and outcomes for attempted candidate evaluations."""

    model_config = ConfigDict(frozen=True)

    evaluated_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    approval_rate: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.approved_count + self.rejected_count != self.evaluated_count:
            raise ValueError("risk decision counts must reconcile")
        if self.evaluated_count == 0 and self.approval_rate is not None:
            raise ValueError("empty risk decisions cannot have an approval rate")
        if self.evaluated_count > 0 and self.approval_rate is None:
            raise ValueError("non-empty risk decisions require an approval rate")
        return self


class RiskRejectionReasonSummary(BaseModel):
    """Count of rejected decisions assigned to one deterministic primary reason."""

    model_config = ConfigDict(frozen=True)

    name: CandidateRiskCheckName
    rejected_decisions: int = Field(ge=0)


class RiskDecisionEvent(BaseModel):
    """Auditable risk decision projected from one persisted replay attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(min_length=1, max_length=100)
    journal_id: str = Field(pattern=r"^journal-[a-f0-9]{16}$")
    candidate_id: str = Field(pattern=r"^candidate-[a-f0-9]{16}$")
    portfolio_id: str = Field(pattern=r"^portfolio-[a-f0-9]{16}$")
    evaluated_at: datetime
    decision: CandidateRiskDecision
    replay_status: CandidateReplayStatus
    primary_rejection_reason: CandidateRiskCheckName | None = None
    failed_check_names: tuple[CandidateRiskCheckName, ...]
    risk_budget: Decimal = Field(ge=0)
    risk_consumed: Decimal = Field(ge=0)
    selected: bool
    position_id: str | None = Field(
        default=None,
        pattern=r"^position-[a-f0-9]{16}$",
    )

    @field_validator("evaluated_at")
    @classmethod
    def evaluated_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.decision is CandidateRiskDecision.REJECTED:
            if self.primary_rejection_reason is None or not self.failed_check_names:
                raise ValueError("rejected risk event requires rejection reasons")
            if self.primary_rejection_reason is not self.failed_check_names[0]:
                raise ValueError("primary rejection reason must be the first failed check")
            if self.selected or self.position_id is not None or self.risk_consumed != 0:
                raise ValueError("rejected risk event cannot consume simulated risk")
            return self

        if self.primary_rejection_reason is not None or self.failed_check_names:
            raise ValueError("approved risk event cannot contain rejection reasons")
        if self.selected != (self.replay_status is CandidateReplayStatus.OPENED):
            raise ValueError("risk event selection must match replay status")
        if self.selected != (self.position_id is not None):
            raise ValueError("selected risk event must identify its simulated position")
        if self.risk_consumed > self.risk_budget:
            raise ValueError("risk event consumption cannot exceed its approved budget")
        return self


class RiskBudgetUtilization(BaseModel):
    """Actual risk used by opened simulations against their approved budgets."""

    model_config = ConfigDict(frozen=True)

    opened_decisions: int = Field(ge=0)
    allocated_risk_budget: Decimal = Field(ge=0)
    consumed_risk: Decimal = Field(ge=0)
    consumption_fraction: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_utilization(self) -> Self:
        if self.opened_decisions == 0:
            if self.allocated_risk_budget != 0 or self.consumed_risk != 0:
                raise ValueError("empty opened decisions cannot allocate or consume risk")
            if self.consumption_fraction is not None:
                raise ValueError("empty opened decisions cannot have risk utilization")
            return self

        if self.allocated_risk_budget <= 0 or self.consumption_fraction is None:
            raise ValueError("opened decisions require a positive budget and utilization")
        if self.consumed_risk > self.allocated_risk_budget:
            raise ValueError("consumed risk cannot exceed allocated risk budget")
        return self


class PortfolioRiskSnapshot(BaseModel):
    """As-of portfolio exposure and interval drawdown from persisted timeline events."""

    model_config = ConfigDict(frozen=True)

    latest_event_at: datetime | None = None
    portfolio_count: int = Field(ge=0)
    open_position_count: int = Field(ge=0)
    total_equity: Decimal
    simulated_exposure: Decimal = Field(ge=0)
    exposure_fraction: Decimal | None = Field(default=None, ge=0)
    exposure_limit_fraction: Decimal = Field(gt=0, le=1)
    exposure_within_limit: bool | None = None
    largest_pair: TradingPair | None = None
    concentration_exposure: Decimal = Field(ge=0)
    concentration_fraction: Decimal | None = Field(default=None, ge=0)
    concentration_limit_fraction: Decimal = Field(gt=0, le=1)
    concentration_within_limit: bool | None = None
    max_drawdown_fraction: Decimal | None = Field(default=None, ge=0)
    drawdown_limit_fraction: Decimal = Field(gt=0, le=1)
    drawdown_within_limit: bool | None = None

    @field_validator("latest_event_at")
    @classmethod
    def latest_event_at_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if self.portfolio_count == 0:
            optional_values = (
                self.latest_event_at,
                self.exposure_fraction,
                self.exposure_within_limit,
                self.concentration_fraction,
                self.concentration_within_limit,
                self.max_drawdown_fraction,
                self.drawdown_within_limit,
            )
            if any(value is not None for value in optional_values):
                raise ValueError("empty portfolio snapshot cannot contain derived metrics")
            if (
                self.open_position_count != 0
                or self.total_equity != 0
                or self.simulated_exposure != 0
                or self.concentration_exposure != 0
                or self.largest_pair is not None
            ):
                raise ValueError("empty portfolio snapshot must contain zero totals")
            return self

        if self.latest_event_at is None or self.max_drawdown_fraction is None:
            raise ValueError("portfolio snapshot requires event and drawdown metrics")
        if self.open_position_count > self.portfolio_count:
            raise ValueError("open position count cannot exceed portfolio count")
        if self.concentration_exposure > self.simulated_exposure:
            raise ValueError("concentration exposure cannot exceed total exposure")
        if self.total_equity > 0 and any(
            value is None
            for value in (
                self.exposure_fraction,
                self.exposure_within_limit,
                self.concentration_fraction,
                self.concentration_within_limit,
            )
        ):
            raise ValueError("positive portfolio equity requires exposure ratios")
        return self


class RiskDashboardReport(BaseModel):
    """Versioned read-only risk dashboard projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dashboard_version: Literal["risk-dashboard-v1"] = "risk-dashboard-v1"
    generated_at: datetime
    from_time: datetime | None = None
    to_time: datetime | None = None
    portfolio_id: str | None = Field(
        default=None,
        pattern=r"^portfolio-[a-f0-9]{16}$",
    )
    decision_window: Literal["inclusive_risk_assessment_evaluated_at"] = (
        "inclusive_risk_assessment_evaluated_at"
    )
    portfolio_snapshot_rule: Literal["latest_event_at_or_before_to_time"] = (
        "latest_event_at_or_before_to_time"
    )
    drawdown_window_rule: Literal["baseline_at_from_time_then_events_in_range"] = (
        "baseline_at_from_time_then_events_in_range"
    )
    decisions: RiskDecisionSummary
    rejection_reasons: tuple[RiskRejectionReasonSummary, ...]
    budget: RiskBudgetUtilization
    portfolio_risk: PortfolioRiskSnapshot
    decision_events: tuple[RiskDecisionEvent, ...]
    interpretation: Literal["historical_research_only"] = "historical_research_only"

    @field_validator("generated_at", "from_time", "to_time")
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if (
            self.from_time is not None
            and self.to_time is not None
            and self.to_time < self.from_time
        ):
            raise ValueError("to_time must be on or after from_time")
        if len(self.decision_events) != self.decisions.evaluated_count:
            raise ValueError("risk decision events must match evaluated count")
        event_ids = tuple(event.event_id for event in self.decision_events)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("risk decision event IDs must be unique")
        approved_events = sum(
            event.decision is CandidateRiskDecision.APPROVED for event in self.decision_events
        )
        if approved_events != self.decisions.approved_count:
            raise ValueError("approved risk events must match decision summary")

        expected_names = tuple(CandidateRiskCheckName)
        actual_names = tuple(reason.name for reason in self.rejection_reasons)
        if actual_names != expected_names:
            raise ValueError("risk rejection reasons must be complete and ordered")

        reason_total = sum(reason.rejected_decisions for reason in self.rejection_reasons)
        if reason_total != self.decisions.rejected_count:
            raise ValueError("risk rejection reasons must reconcile with rejected decisions")
        event_reason_counts = {
            name: sum(event.primary_rejection_reason is name for event in self.decision_events)
            for name in CandidateRiskCheckName
        }
        if any(
            reason.rejected_decisions != event_reason_counts[reason.name]
            for reason in self.rejection_reasons
        ):
            raise ValueError("risk rejection categories must match decision events")

        opened_events = tuple(event for event in self.decision_events if event.selected)
        if self.budget.opened_decisions != len(opened_events):
            raise ValueError("risk budget opened count must match decision events")
        if self.budget.allocated_risk_budget != quantize_money(
            sum((event.risk_budget for event in opened_events), start=Decimal("0"))
        ):
            raise ValueError("allocated risk budget must match opened decision events")
        if self.budget.consumed_risk != quantize_money(
            sum((event.risk_consumed for event in opened_events), start=Decimal("0"))
        ):
            raise ValueError("consumed risk must match opened decision events")
        return self


@dataclass(frozen=True)
class _PortfolioState:
    latest_event: PortfolioTimelineEvent
    exposure: Decimal
    open_pair: TradingPair | None
    max_drawdown_fraction: Decimal


class RiskDashboardBuilder:
    """Aggregate immutable candidate and portfolio events into risk read models."""

    def __init__(self, *, policy: CandidateRiskPolicy | None = None) -> None:
        self._policy = policy or CandidateRiskPolicy()

    def build(
        self,
        *,
        journals: Sequence[CandidateJournalEntry],
        portfolios: Sequence[SimulatedPortfolio],
        generated_at: datetime | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        portfolio_id: str | None = None,
    ) -> RiskDashboardReport:
        normalized_generated_at = normalize_candidate_timestamp(generated_at or datetime.now(UTC))
        normalized_from = self._normalize_optional_time(from_time)
        normalized_to = self._normalize_optional_time(to_time)
        if (
            normalized_from is not None
            and normalized_to is not None
            and normalized_to < normalized_from
        ):
            raise ValueError("to_time must be on or after from_time")

        selected_journals = tuple(
            journal
            for journal in journals
            if (portfolio_id is None or journal.portfolio_id == portfolio_id)
            and (normalized_from is None or journal.evaluated_at >= normalized_from)
            and (normalized_to is None or journal.evaluated_at <= normalized_to)
        )
        selected_portfolios = tuple(
            portfolio
            for portfolio in portfolios
            if portfolio_id is None or portfolio.portfolio_id == portfolio_id
        )

        events = self._decision_events(selected_journals)
        approved_count = sum(event.decision is CandidateRiskDecision.APPROVED for event in events)
        rejected_count = len(events) - approved_count
        approval_rate = (
            _quantize_ratio(Decimal(approved_count) / Decimal(len(events))) if events else None
        )

        reason_counts = {name: 0 for name in CandidateRiskCheckName}
        for event in events:
            if event.primary_rejection_reason is not None:
                reason_counts[event.primary_rejection_reason] += 1

        opened_events = tuple(event for event in events if event.selected)
        allocated_budget = quantize_money(
            sum((event.risk_budget for event in opened_events), start=Decimal("0"))
        )
        consumed_risk = quantize_money(
            sum((event.risk_consumed for event in opened_events), start=Decimal("0"))
        )
        consumption_fraction = (
            _quantize_ratio(consumed_risk / allocated_budget) if allocated_budget > 0 else None
        )

        return RiskDashboardReport(
            generated_at=normalized_generated_at,
            from_time=normalized_from,
            to_time=normalized_to,
            portfolio_id=portfolio_id,
            decisions=RiskDecisionSummary(
                evaluated_count=len(events),
                approved_count=approved_count,
                rejected_count=rejected_count,
                approval_rate=approval_rate,
            ),
            rejection_reasons=tuple(
                RiskRejectionReasonSummary(
                    name=name,
                    rejected_decisions=reason_counts[name],
                )
                for name in CandidateRiskCheckName
            ),
            budget=RiskBudgetUtilization(
                opened_decisions=len(opened_events),
                allocated_risk_budget=allocated_budget,
                consumed_risk=consumed_risk,
                consumption_fraction=consumption_fraction,
            ),
            portfolio_risk=self._portfolio_risk(
                selected_portfolios,
                from_time=normalized_from,
                to_time=normalized_to,
            ),
            decision_events=events,
        )

    @staticmethod
    def _normalize_optional_time(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_candidate_timestamp(value)

    @staticmethod
    def _decision_events(
        journals: Sequence[CandidateJournalEntry],
    ) -> tuple[RiskDecisionEvent, ...]:
        events: list[RiskDecisionEvent] = []

        for journal in journals:
            for attempt in journal.lifecycle.replay.attempted:
                assessment = attempt.risk_assessment
                failed_names = tuple(check.name for check in assessment.checks if not check.passed)
                simulation = attempt.simulation
                selected = attempt.status is CandidateReplayStatus.OPENED
                risk_consumed = (
                    quantize_money(simulation.quantity * assessment.unit_price_risk)
                    if simulation is not None
                    else Decimal("0")
                )

                events.append(
                    RiskDecisionEvent(
                        event_id=RiskDashboardBuilder._event_id(
                            journal,
                            attempt.ranking_entry.candidate.candidate_id,
                        ),
                        journal_id=journal.journal_id,
                        candidate_id=attempt.ranking_entry.candidate.candidate_id,
                        portfolio_id=journal.portfolio_id,
                        evaluated_at=assessment.evaluated_at,
                        decision=assessment.decision,
                        replay_status=attempt.status,
                        primary_rejection_reason=(
                            failed_names[0]
                            if assessment.decision is CandidateRiskDecision.REJECTED
                            else None
                        ),
                        failed_check_names=failed_names,
                        risk_budget=assessment.risk_budget,
                        risk_consumed=risk_consumed,
                        selected=selected,
                        position_id=journal.position_id if selected else None,
                    )
                )

        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.evaluated_at,
                    event.journal_id,
                    event.candidate_id,
                ),
                reverse=True,
            )
        )

    @staticmethod
    def _event_id(journal: CandidateJournalEntry, candidate_id: str) -> str:
        journal_suffix = journal.journal_id.removeprefix("journal-")
        candidate_suffix = candidate_id.removeprefix("candidate-")
        return f"risk-event-{journal_suffix}-{candidate_suffix}"

    def _portfolio_risk(
        self,
        portfolios: Sequence[SimulatedPortfolio],
        *,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> PortfolioRiskSnapshot:
        collected_states: list[_PortfolioState] = []
        for portfolio in portfolios:
            state = self._portfolio_state(
                portfolio,
                from_time=from_time,
                to_time=to_time,
            )
            if state is not None:
                collected_states.append(state)
        states = tuple(collected_states)

        if not states:
            return PortfolioRiskSnapshot(
                portfolio_count=0,
                open_position_count=0,
                total_equity=Decimal("0"),
                simulated_exposure=Decimal("0"),
                exposure_limit_fraction=self._policy.max_notional_fraction,
                concentration_exposure=Decimal("0"),
                concentration_limit_fraction=self._policy.max_notional_fraction,
                drawdown_limit_fraction=self._policy.max_risk_fraction,
            )

        total_equity = quantize_money(
            sum((state.latest_event.equity for state in states), start=Decimal("0"))
        )
        total_exposure = quantize_money(
            sum((state.exposure for state in states), start=Decimal("0"))
        )
        pair_exposures: dict[tuple[str, str, str], tuple[TradingPair, Decimal]] = {}
        for state in states:
            if state.open_pair is None:
                continue
            pair = state.open_pair
            key = (pair.base_asset, pair.quote_asset, pair.market_type.value)
            current_pair, current_exposure = pair_exposures.get(
                key,
                (pair, Decimal("0")),
            )
            pair_exposures[key] = (
                current_pair,
                quantize_money(current_exposure + state.exposure),
            )

        largest_pair: TradingPair | None = None
        concentration_exposure = Decimal("0")
        if pair_exposures:
            _, (largest_pair, concentration_exposure) = min(
                pair_exposures.items(),
                key=lambda item: (-item[1][1], item[0]),
            )

        exposure_fraction = (
            _quantize_ratio(total_exposure / total_equity) if total_equity > 0 else None
        )
        concentration_fraction = (
            _quantize_ratio(concentration_exposure / total_equity) if total_equity > 0 else None
        )
        max_drawdown = max(state.max_drawdown_fraction for state in states)

        return PortfolioRiskSnapshot(
            latest_event_at=max(state.latest_event.occurred_at for state in states),
            portfolio_count=len(states),
            open_position_count=sum(state.open_pair is not None for state in states),
            total_equity=total_equity,
            simulated_exposure=total_exposure,
            exposure_fraction=exposure_fraction,
            exposure_limit_fraction=self._policy.max_notional_fraction,
            exposure_within_limit=(
                exposure_fraction <= self._policy.max_notional_fraction
                if exposure_fraction is not None
                else None
            ),
            largest_pair=largest_pair,
            concentration_exposure=concentration_exposure,
            concentration_fraction=concentration_fraction,
            concentration_limit_fraction=self._policy.max_notional_fraction,
            concentration_within_limit=(
                concentration_fraction <= self._policy.max_notional_fraction
                if concentration_fraction is not None
                else None
            ),
            max_drawdown_fraction=max_drawdown,
            drawdown_limit_fraction=self._policy.max_risk_fraction,
            drawdown_within_limit=max_drawdown <= self._policy.max_risk_fraction,
        )

    @staticmethod
    def _portfolio_state(
        portfolio: SimulatedPortfolio,
        *,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> _PortfolioState | None:
        events_to_snapshot = tuple(
            event for event in portfolio.timeline if to_time is None or event.occurred_at <= to_time
        )
        if not events_to_snapshot:
            return None

        positions_by_id = {position.position_id: position for position in portfolio.positions}
        active_position_id: str | None = None
        active_exposure = Decimal("0")

        for event in events_to_snapshot:
            if event.event_type in {
                PortfolioEventType.POSITION_OPENED,
                PortfolioEventType.POSITION_MARKED,
            }:
                if event.position_id is None or event.price is None or event.quantity is None:
                    raise ValueError("position event is missing exposure details")
                active_position_id = event.position_id
                active_exposure = quantize_money(event.price * event.quantity)
            elif event.event_type is PortfolioEventType.POSITION_CLOSED:
                active_position_id = None
                active_exposure = Decimal("0")

        open_pair: TradingPair | None = None
        if active_position_id is not None:
            position = positions_by_id.get(active_position_id)
            if position is None:
                raise ValueError("portfolio timeline position is missing from aggregate")
            open_pair = position.pair

        return _PortfolioState(
            latest_event=events_to_snapshot[-1],
            exposure=active_exposure,
            open_pair=open_pair,
            max_drawdown_fraction=RiskDashboardBuilder._max_drawdown_fraction(
                events_to_snapshot,
                from_time=from_time,
            ),
        )

    @staticmethod
    def _max_drawdown_fraction(
        events: Sequence[PortfolioTimelineEvent],
        *,
        from_time: datetime | None,
    ) -> Decimal:
        if not events:
            return Decimal("0")

        if from_time is None:
            equities = [event.equity for event in events]
        else:
            before_range = tuple(event for event in events if event.occurred_at < from_time)
            in_range = tuple(event for event in events if event.occurred_at >= from_time)
            baseline = before_range[-1] if before_range else None
            equities = ([baseline.equity] if baseline is not None else []) + [
                event.equity for event in in_range
            ]
            if not equities:
                equities = [events[-1].equity]

        peak = equities[0]
        maximum = Decimal("0")
        for equity in equities:
            peak = max(peak, equity)
            if peak <= 0:
                continue
            drawdown = max((peak - equity) / peak, Decimal("0"))
            maximum = max(maximum, drawdown)

        return _quantize_ratio(maximum)
