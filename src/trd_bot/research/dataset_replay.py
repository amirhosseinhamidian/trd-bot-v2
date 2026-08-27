from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.paper import SimulatedPortfolio
from trd_bot.research.candidate_ranking import CandidateRankingEntry
from trd_bot.research.candidate_simulation_runner import (
    CandidateSimulationResult,
    CandidateSimulationRunner,
)
from trd_bot.research.candidates import (
    CandidateAction,
    ResearchCandidate,
    normalize_candidate_timestamp,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.risk_policy import (
    CandidateRiskAssessment,
    CandidateRiskDecision,
    CandidateRiskEvaluator,
)


class CandidateReplayStatus(StrEnum):
    """Outcome of replaying one ranked candidate against historical candles."""

    OPENED = "opened"
    RISK_REJECTED = "risk_rejected"
    NO_FILL = "no_fill"


class CandidateReplayFill(BaseModel):
    """Deterministic historical fill chosen from one closed candle."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    candle_open_time: datetime
    candle_close_time: datetime
    fill_price: Decimal = Field(gt=0)

    @field_validator(
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
    def validate_candle_window(self) -> Self:
        if self.candle_close_time <= self.candle_open_time:
            raise ValueError("replay fill candle close must be after open")

        return self


class CandidateReplayResult(BaseModel):
    """Auditable result of risk evaluation plus deterministic dataset replay."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    dataset_id: str = Field(min_length=1, max_length=100)
    evaluated_at: datetime
    status: CandidateReplayStatus

    ranking_entry: CandidateRankingEntry
    risk_assessment: CandidateRiskAssessment
    fill: CandidateReplayFill | None = None
    simulation: CandidateSimulationResult | None = None

    @field_validator("evaluated_at")
    @classmethod
    def evaluated_at_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.risk_assessment.ranking_entry != self.ranking_entry:
            raise ValueError("replay ranking entry does not match risk assessment")

        if self.risk_assessment.evaluated_at != self.evaluated_at:
            raise ValueError("replay evaluation time does not match risk assessment")

        candidate = self.ranking_entry.candidate
        if candidate.dataset_id != self.dataset_id:
            raise ValueError("replay dataset does not match ranked candidate")

        if self.status is CandidateReplayStatus.RISK_REJECTED:
            if self.risk_assessment.decision is not CandidateRiskDecision.REJECTED:
                raise ValueError("risk-rejected replay requires a rejected assessment")
            if self.fill is not None or self.simulation is not None:
                raise ValueError("risk-rejected replay cannot contain a fill")
            return self

        if self.risk_assessment.decision is not CandidateRiskDecision.APPROVED:
            raise ValueError("non-rejected replay requires an approved assessment")

        if self.status is CandidateReplayStatus.NO_FILL:
            if self.fill is not None or self.simulation is not None:
                raise ValueError("no-fill replay cannot contain a simulation")
            return self

        if self.fill is None or self.simulation is None:
            raise ValueError("opened replay requires fill and simulation details")

        if self.fill.fill_price != self.simulation.fill_price:
            raise ValueError("replay fill price does not match simulation")

        if self.fill.candle_close_time != self.simulation.opened_at:
            raise ValueError("replay fill time does not match simulation open time")

        if self.simulation.assessment != self.risk_assessment:
            raise ValueError("replay simulation does not match risk assessment")

        return self


class CandidateDatasetReplayRunner:
    """Replay one ranked candidate over immutable historical market data."""

    def __init__(
        self,
        *,
        risk_evaluator: CandidateRiskEvaluator | None = None,
        simulation_runner: CandidateSimulationRunner | None = None,
    ) -> None:
        self._risk_evaluator = risk_evaluator or CandidateRiskEvaluator()
        self._simulation_runner = simulation_runner or CandidateSimulationRunner()

    def run(
        self,
        *,
        entry: CandidateRankingEntry,
        portfolio: SimulatedPortfolio,
        dataset: DatasetSnapshot,
        evaluated_at: datetime,
    ) -> CandidateReplayResult:
        normalized_evaluated_at = normalize_candidate_timestamp(evaluated_at)
        candidate = entry.candidate

        self._validate_lineage(
            candidate=candidate,
            portfolio=portfolio,
            dataset=dataset,
        )

        assessment = self._risk_evaluator.evaluate(
            entry=entry,
            portfolio=portfolio,
            at=normalized_evaluated_at,
        )

        if assessment.decision is CandidateRiskDecision.REJECTED:
            return CandidateReplayResult(
                dataset_id=dataset.dataset_id,
                evaluated_at=normalized_evaluated_at,
                status=CandidateReplayStatus.RISK_REJECTED,
                ranking_entry=entry,
                risk_assessment=assessment,
            )

        fill = self._find_fill(
            candidate=candidate,
            dataset=dataset,
            evaluated_at=normalized_evaluated_at,
        )

        if fill is None:
            return CandidateReplayResult(
                dataset_id=dataset.dataset_id,
                evaluated_at=normalized_evaluated_at,
                status=CandidateReplayStatus.NO_FILL,
                ranking_entry=entry,
                risk_assessment=assessment,
            )

        simulation = self._simulation_runner.run(
            assessment=assessment,
            portfolio=portfolio,
            fill_price=fill.fill_price,
            occurred_at=fill.candle_close_time,
        )

        return CandidateReplayResult(
            dataset_id=dataset.dataset_id,
            evaluated_at=normalized_evaluated_at,
            status=CandidateReplayStatus.OPENED,
            ranking_entry=entry,
            risk_assessment=assessment,
            fill=fill,
            simulation=simulation,
        )

    @staticmethod
    def _validate_lineage(
        *,
        candidate: ResearchCandidate,
        portfolio: SimulatedPortfolio,
        dataset: DatasetSnapshot,
    ) -> None:
        if candidate.dataset_id != dataset.dataset_id:
            raise ValueError("candidate and replay dataset lineage must match")

        if portfolio.dataset_id != dataset.dataset_id:
            raise ValueError("portfolio and replay dataset lineage must match")

        if candidate.pair != dataset.pair:
            raise ValueError("candidate pair does not match replay dataset")

        if candidate.timeframe is not dataset.timeframe:
            raise ValueError("candidate timeframe does not match replay dataset")

    def _find_fill(
        self,
        *,
        candidate: ResearchCandidate,
        dataset: DatasetSnapshot,
        evaluated_at: datetime,
    ) -> CandidateReplayFill | None:
        for candle in dataset.candles:
            if candle.open_time < evaluated_at:
                continue

            if not candidate.is_selectable(at=candle.close_time):
                continue

            fill_price = self._fill_price(
                candidate=candidate,
                candle=candle,
            )
            if fill_price is None:
                continue

            return CandidateReplayFill(
                candle_open_time=candle.open_time,
                candle_close_time=candle.close_time,
                fill_price=fill_price,
            )

        return None

    @staticmethod
    def _fill_price(
        *,
        candidate: ResearchCandidate,
        candle: OHLCVCandle,
    ) -> Decimal | None:
        trade_plan = candidate.trade_plan
        if trade_plan is None:
            raise ValueError("replay requires a directional candidate trade plan")

        zone = trade_plan.entry_zone
        overlap_low = max(
            zone.lower_price,
            candle.low_price,
        )
        overlap_high = min(
            zone.upper_price,
            candle.high_price,
        )

        if overlap_low > overlap_high:
            return None

        if candidate.action is CandidateAction.LONG:
            return overlap_high

        if candidate.action is CandidateAction.SHORT:
            return overlap_low

        raise ValueError("replay only accepts directional candidates")
