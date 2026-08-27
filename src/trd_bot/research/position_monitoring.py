from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.paper.portfolio import (
    PositionStatus,
    SimulatedPortfolio,
    SimulatedPortfolioLedger,
    SimulatedPosition,
)
from trd_bot.research.candidate_simulation_runner import CandidateSimulationResult
from trd_bot.research.candidates import (
    CandidateAction,
    normalize_candidate_timestamp,
)
from trd_bot.research.datasets import DatasetSnapshot


class CandidateExitReason(StrEnum):
    """Deterministic reasons for closing one simulated candidate position."""

    INVALIDATION = "invalidation"
    TARGET = "target"
    TREND_REVERSAL = "trend_reversal"
    PORTFOLIO_RISK = "portfolio_risk"
    DATA_UNRELIABLE = "data_unreliable"
    TIME_EXPIRY = "time_expiry"
    END_OF_DATA = "end_of_data"


class CandidateExitDirective(BaseModel):
    """One deterministic non-price exit instruction for offline monitoring."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    reason: CandidateExitReason
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_directive(self) -> Self:
        if self.reason not in (
            CandidateExitReason.TREND_REVERSAL,
            CandidateExitReason.PORTFOLIO_RISK,
            CandidateExitReason.DATA_UNRELIABLE,
        ):
            raise ValueError(
                "exit directive reason must be trend reversal, portfolio risk, or data unreliable"
            )

        return self


class CandidateExitTrigger(BaseModel):
    """One auditable exit decision produced from a closed historical candle."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    reason: CandidateExitReason
    price: Decimal = Field(gt=0)
    occurred_at: datetime
    candle_open_time: datetime
    candle_close_time: datetime
    target_label: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator(
        "occurred_at",
        "candle_open_time",
        "candle_close_time",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_trigger(self) -> Self:
        if self.candle_close_time <= self.candle_open_time:
            raise ValueError("exit trigger candle close must be after open")

        if self.occurred_at != self.candle_close_time:
            raise ValueError("exit trigger time must equal closed candle time")

        if self.reason is CandidateExitReason.TARGET:
            if self.target_label is None:
                raise ValueError("target exit requires a target label")
        elif self.target_label is not None:
            raise ValueError("only target exit can contain a target label")

        return self


class CandidatePositionMonitoringResult(BaseModel):
    """Final offline monitoring result for one opened simulated candidate."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    dataset_id: str = Field(min_length=1, max_length=100)
    candidate_id: str = Field(pattern=r"^candidate-[a-f0-9]{16}$")
    position_id: str = Field(pattern=r"^position-[a-f0-9]{16}$")

    opened_at: datetime
    closed_at: datetime
    monitored_candles: int = Field(ge=1)
    marked_candles: int = Field(ge=0)

    trigger: CandidateExitTrigger
    closed_position: SimulatedPosition
    portfolio: SimulatedPortfolio

    @field_validator(
        "opened_at",
        "closed_at",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.closed_at <= self.opened_at:
            raise ValueError("monitored position must close after opening")

        if self.trigger.occurred_at != self.closed_at:
            raise ValueError("monitoring close time must match exit trigger")

        if self.closed_position.position_id != self.position_id:
            raise ValueError("monitoring position ID does not match closed position")

        if self.closed_position.status is not PositionStatus.CLOSED:
            raise ValueError("monitoring result requires a closed position")

        if self.closed_position.closed_at != self.closed_at:
            raise ValueError("closed position time does not match monitoring result")

        if self.closed_position.exit_price != self.trigger.price:
            raise ValueError("closed position price does not match exit trigger")

        if self.portfolio.updated_at != self.closed_at:
            raise ValueError("final portfolio time must match position close")

        matching_positions = tuple(
            position
            for position in self.portfolio.positions
            if position.position_id == self.position_id
        )
        if matching_positions != (self.closed_position,):
            raise ValueError("closed position must appear exactly once in final portfolio")

        if self.marked_candles >= self.monitored_candles:
            raise ValueError("final monitored candle must close rather than mark")

        return self


class CandidatePositionMonitor:
    """Monitor one offline position over future candles and deterministically exit."""

    def __init__(
        self,
        *,
        ledger: SimulatedPortfolioLedger | None = None,
    ) -> None:
        self._ledger = ledger or SimulatedPortfolioLedger()

    def run(
        self,
        *,
        simulation: CandidateSimulationResult,
        dataset: DatasetSnapshot,
        exit_directives: Sequence[CandidateExitDirective] = (),
    ) -> CandidatePositionMonitoringResult:
        candidate = simulation.selected_candidate
        position = simulation.opened_position
        portfolio = simulation.portfolio

        self._validate_lineage(
            simulation=simulation,
            dataset=dataset,
        )

        future_candles = tuple(
            candle for candle in dataset.candles if candle.open_time >= simulation.opened_at
        )
        if not future_candles:
            raise ValueError("dataset has no closed candle after simulated entry")

        directives_by_time = self._prepare_directives(
            exit_directives=exit_directives,
            future_candles=future_candles,
        )
        current_portfolio = portfolio

        for index, candle in enumerate(future_candles):
            trigger: CandidateExitTrigger | None
            directive = directives_by_time.get(candle.close_time)

            if directive is not None and directive.reason is CandidateExitReason.DATA_UNRELIABLE:
                trigger = self._directive_trigger(
                    directive=directive,
                    candle=candle,
                    portfolio=current_portfolio,
                    position_id=position.position_id,
                )
            else:
                trigger = self._price_trigger(
                    simulation=simulation,
                    candle=candle,
                )

            if trigger is None and directive is not None:
                trigger = self._directive_trigger(
                    directive=directive,
                    candle=candle,
                    portfolio=current_portfolio,
                    position_id=position.position_id,
                )

            if trigger is None and candle.close_time >= candidate.valid_until:
                trigger = CandidateExitTrigger(
                    reason=CandidateExitReason.TIME_EXPIRY,
                    price=candle.close_price,
                    occurred_at=candle.close_time,
                    candle_open_time=candle.open_time,
                    candle_close_time=candle.close_time,
                )

            is_final_candle = index == len(future_candles) - 1
            if trigger is None and is_final_candle:
                trigger = CandidateExitTrigger(
                    reason=CandidateExitReason.END_OF_DATA,
                    price=candle.close_price,
                    occurred_at=candle.close_time,
                    candle_open_time=candle.open_time,
                    candle_close_time=candle.close_time,
                )

            if trigger is not None:
                current_portfolio = self._ledger.close_position(
                    current_portfolio,
                    position_id=position.position_id,
                    price=trigger.price,
                    occurred_at=trigger.occurred_at,
                )
                closed_position = self._closed_position(
                    current_portfolio,
                    position.position_id,
                )

                return CandidatePositionMonitoringResult(
                    dataset_id=dataset.dataset_id,
                    candidate_id=candidate.candidate_id,
                    position_id=position.position_id,
                    opened_at=simulation.opened_at,
                    closed_at=trigger.occurred_at,
                    monitored_candles=index + 1,
                    marked_candles=index,
                    trigger=trigger,
                    closed_position=closed_position,
                    portfolio=current_portfolio,
                )

            current_portfolio = self._ledger.mark_to_market(
                current_portfolio,
                position_id=position.position_id,
                price=candle.close_price,
                occurred_at=candle.close_time,
            )

        raise RuntimeError("position monitoring exhausted candles without closing")

    @staticmethod
    def _validate_lineage(
        *,
        simulation: CandidateSimulationResult,
        dataset: DatasetSnapshot,
    ) -> None:
        candidate = simulation.selected_candidate
        position = simulation.opened_position

        if candidate.dataset_id != dataset.dataset_id:
            raise ValueError("candidate and monitoring dataset lineage must match")

        if simulation.portfolio.dataset_id != dataset.dataset_id:
            raise ValueError("portfolio and monitoring dataset lineage must match")

        if candidate.pair != dataset.pair or position.pair != dataset.pair:
            raise ValueError("position pair does not match monitoring dataset")

        if candidate.timeframe is not dataset.timeframe:
            raise ValueError("candidate timeframe does not match monitoring dataset")

        if position.status is not PositionStatus.OPEN:
            raise ValueError("position monitor requires an open simulated position")

        if simulation.portfolio.updated_at != simulation.opened_at:
            raise ValueError("simulation portfolio must be the entry snapshot")

    @staticmethod
    def _prepare_directives(
        *,
        exit_directives: Sequence[CandidateExitDirective],
        future_candles: tuple[OHLCVCandle, ...],
    ) -> dict[datetime, CandidateExitDirective]:
        directive_times = tuple(directive.occurred_at for directive in exit_directives)
        if len(directive_times) != len(set(directive_times)):
            raise ValueError("exit directive times must be unique")

        candle_close_times = {candle.close_time for candle in future_candles}
        unmatched = tuple(
            occurred_at for occurred_at in directive_times if occurred_at not in candle_close_times
        )
        if unmatched:
            raise ValueError("exit directives must match future closed candle times")

        return {directive.occurred_at: directive for directive in exit_directives}

    @staticmethod
    def _directive_trigger(
        *,
        directive: CandidateExitDirective,
        candle: OHLCVCandle,
        portfolio: SimulatedPortfolio,
        position_id: str,
    ) -> CandidateExitTrigger:
        if directive.reason is CandidateExitReason.DATA_UNRELIABLE:
            price = CandidatePositionMonitor._open_position(
                portfolio,
                position_id,
            ).current_price
        else:
            price = candle.close_price

        return CandidateExitTrigger(
            reason=directive.reason,
            price=price,
            occurred_at=candle.close_time,
            candle_open_time=candle.open_time,
            candle_close_time=candle.close_time,
        )

    @staticmethod
    def _price_trigger(
        *,
        simulation: CandidateSimulationResult,
        candle: OHLCVCandle,
    ) -> CandidateExitTrigger | None:
        candidate = simulation.selected_candidate
        trade_plan = candidate.trade_plan

        if trade_plan is None:
            raise ValueError("monitored directional candidate requires a trade plan")

        invalidation = trade_plan.invalidation_price
        first_target = trade_plan.targets[0]

        if candidate.action is CandidateAction.LONG:
            invalidation_hit = candle.low_price <= invalidation
            target_hit = candle.high_price >= first_target.price
        elif candidate.action is CandidateAction.SHORT:
            invalidation_hit = candle.high_price >= invalidation
            target_hit = candle.low_price <= first_target.price
        else:
            raise ValueError("position monitor only accepts directional candidates")

        # Closed OHLCV candles do not expose intra-candle event order. If both
        # thresholds are touched, choose invalidation first to avoid optimistic bias.
        if invalidation_hit:
            return CandidateExitTrigger(
                reason=CandidateExitReason.INVALIDATION,
                price=invalidation,
                occurred_at=candle.close_time,
                candle_open_time=candle.open_time,
                candle_close_time=candle.close_time,
            )

        if target_hit:
            return CandidateExitTrigger(
                reason=CandidateExitReason.TARGET,
                price=first_target.price,
                occurred_at=candle.close_time,
                candle_open_time=candle.open_time,
                candle_close_time=candle.close_time,
                target_label=first_target.label,
            )

        return None

    @staticmethod
    def _open_position(
        portfolio: SimulatedPortfolio,
        position_id: str,
    ) -> SimulatedPosition:
        for position in portfolio.positions:
            if position.position_id == position_id and position.status is PositionStatus.OPEN:
                return position

        raise ValueError("open simulated position was not found")

    @staticmethod
    def _closed_position(
        portfolio: SimulatedPortfolio,
        position_id: str,
    ) -> SimulatedPosition:
        for position in portfolio.positions:
            if position.position_id == position_id and position.status is PositionStatus.CLOSED:
                return position

        raise ValueError("closed simulated position was not found")
