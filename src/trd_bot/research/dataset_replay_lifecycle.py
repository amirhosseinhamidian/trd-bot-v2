from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.paper.portfolio import SimulatedPortfolio
from trd_bot.research.candidate_ranking import CandidateRankingEntry
from trd_bot.research.candidates import normalize_candidate_timestamp
from trd_bot.research.data_quality_exit import (
    CandidateDataQualityExitDirectiveProducer,
)
from trd_bot.research.dataset_replay import CandidateReplayStatus
from trd_bot.research.dataset_replay_orchestration import (
    CandidateDatasetReplayOrchestrator,
    CandidateReplayBatchResult,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.portfolio_risk_exit import (
    CandidatePortfolioRiskExitDirectiveProducer,
)
from trd_bot.research.position_monitoring import (
    CandidateExitDirective,
    CandidateExitReason,
    CandidatePositionMonitor,
    CandidatePositionMonitoringResult,
)
from trd_bot.research.trend_reversal_exit import (
    CandidateTrendReversalExitDirectiveProducer,
)
from trd_bot.strategies.signals import StrategySignal


class CandidateReplayLifecycleStatus(StrEnum):
    """Final state of one offline replay-to-exit lifecycle."""

    NO_POSITION = "no_position"
    CLOSED = "closed"


class CandidateReplayLifecycleResult(BaseModel):
    """Auditable aggregate from ranked replay through simulated position exit."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    dataset_id: str = Field(min_length=1, max_length=100)
    evaluated_at: datetime
    status: CandidateReplayLifecycleStatus

    replay: CandidateReplayBatchResult
    monitoring: CandidatePositionMonitoringResult | None = None
    portfolio: SimulatedPortfolio

    @field_validator("evaluated_at")
    @classmethod
    def evaluated_at_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.replay.dataset_id != self.dataset_id:
            raise ValueError("lifecycle dataset does not match replay batch")

        if self.replay.evaluated_at != self.evaluated_at:
            raise ValueError("lifecycle evaluation time does not match replay batch")

        if self.portfolio.portfolio_id != self.replay.portfolio_id:
            raise ValueError("lifecycle final portfolio ID does not match replay batch")

        if self.status is CandidateReplayLifecycleStatus.NO_POSITION:
            if self.replay.selected_candidate_id is not None:
                raise ValueError("no-position lifecycle cannot contain a selection")
            if self.monitoring is not None:
                raise ValueError("no-position lifecycle cannot contain monitoring")
            if self.portfolio != self.replay.portfolio:
                raise ValueError("no-position lifecycle cannot change replay portfolio")
            return self

        if self.replay.selected_candidate_id is None:
            raise ValueError("closed lifecycle requires a selected replay candidate")

        if self.monitoring is None:
            raise ValueError("closed lifecycle requires monitoring details")

        if self.monitoring.dataset_id != self.dataset_id:
            raise ValueError("monitoring dataset does not match lifecycle")

        if self.monitoring.candidate_id != self.replay.selected_candidate_id:
            raise ValueError("monitoring candidate does not match replay selection")

        if self.monitoring.portfolio != self.portfolio:
            raise ValueError("lifecycle final portfolio does not match monitoring")

        return self


class CandidateReplayLifecycleRunner:
    """Run ranked replay and close any opened paper/shadow position offline."""

    def __init__(
        self,
        *,
        replay_orchestrator: CandidateDatasetReplayOrchestrator | None = None,
        position_monitor: CandidatePositionMonitor | None = None,
        data_quality_exit_producer: CandidateDataQualityExitDirectiveProducer | None = None,
        trend_reversal_exit_producer: CandidateTrendReversalExitDirectiveProducer | None = None,
        portfolio_risk_exit_producer: CandidatePortfolioRiskExitDirectiveProducer | None = None,
    ) -> None:
        self._replay_orchestrator = replay_orchestrator or CandidateDatasetReplayOrchestrator()
        self._position_monitor = position_monitor or CandidatePositionMonitor()
        self._data_quality_exit_producer = (
            data_quality_exit_producer or CandidateDataQualityExitDirectiveProducer()
        )
        self._trend_reversal_exit_producer = (
            trend_reversal_exit_producer or CandidateTrendReversalExitDirectiveProducer()
        )
        self._portfolio_risk_exit_producer = (
            portfolio_risk_exit_producer or CandidatePortfolioRiskExitDirectiveProducer()
        )

    def run(
        self,
        *,
        entries: Sequence[CandidateRankingEntry],
        portfolio: SimulatedPortfolio,
        dataset: DatasetSnapshot,
        evaluated_at: datetime,
        exit_directives: Sequence[CandidateExitDirective] = (),
        monitoring_observations: Sequence[OHLCVCandle] | None = None,
        historical_signals: Sequence[StrategySignal] = (),
    ) -> CandidateReplayLifecycleResult:
        normalized_evaluated_at = normalize_candidate_timestamp(evaluated_at)

        replay = self._replay_orchestrator.run(
            entries=entries,
            portfolio=portfolio,
            dataset=dataset,
            evaluated_at=normalized_evaluated_at,
        )

        if replay.selected_candidate_id is None:
            return CandidateReplayLifecycleResult(
                dataset_id=dataset.dataset_id,
                evaluated_at=normalized_evaluated_at,
                status=CandidateReplayLifecycleStatus.NO_POSITION,
                replay=replay,
                portfolio=replay.portfolio,
            )

        opened = tuple(
            attempt
            for attempt in replay.attempted
            if attempt.status is CandidateReplayStatus.OPENED
        )
        if len(opened) != 1:
            raise ValueError("selected replay batch must contain exactly one open")

        simulation = opened[0].simulation
        if simulation is None:
            raise ValueError("opened replay must contain simulation details")

        monitoring_candles = tuple(
            candle for candle in dataset.candles if candle.open_time >= simulation.opened_at
        )
        generated_exit_directives: tuple[CandidateExitDirective, ...] = ()

        if monitoring_observations is not None:
            self._validate_monitoring_observations(
                observations=monitoring_observations,
                dataset=dataset,
            )
            generated_exit_directives += self._data_quality_exit_producer.produce(
                observed_candles=monitoring_observations,
                monitoring_candles=monitoring_candles,
            )

        generated_exit_directives += self._trend_reversal_exit_producer.produce(
            candidate=simulation.selected_candidate,
            opened_at=simulation.opened_at,
            signals=historical_signals,
            monitoring_candles=monitoring_candles,
        )
        generated_exit_directives += self._portfolio_risk_exit_producer.produce(
            simulation=simulation,
            monitoring_candles=monitoring_candles,
        )

        monitoring = self._position_monitor.run(
            simulation=simulation,
            dataset=dataset,
            exit_directives=self._merge_exit_directives(
                explicit=exit_directives,
                generated=generated_exit_directives,
            ),
        )

        return CandidateReplayLifecycleResult(
            dataset_id=dataset.dataset_id,
            evaluated_at=normalized_evaluated_at,
            status=CandidateReplayLifecycleStatus.CLOSED,
            replay=replay,
            monitoring=monitoring,
            portfolio=monitoring.portfolio,
        )

    @staticmethod
    def _validate_monitoring_observations(
        *,
        observations: Sequence[OHLCVCandle],
        dataset: DatasetSnapshot,
    ) -> None:
        mismatched = any(
            candle.source != dataset.source
            or candle.pair != dataset.pair
            or candle.timeframe is not dataset.timeframe
            for candle in observations
        )
        if mismatched:
            raise ValueError("monitoring observations must match lifecycle dataset series")

    @staticmethod
    def _merge_exit_directives(
        *,
        explicit: Sequence[CandidateExitDirective],
        generated: Sequence[CandidateExitDirective],
    ) -> tuple[CandidateExitDirective, ...]:
        merged: dict[datetime, CandidateExitDirective] = {}

        for directive in explicit:
            if directive.occurred_at in merged:
                raise ValueError("exit directive times must be unique")
            merged[directive.occurred_at] = directive

        for directive in generated:
            existing = merged.get(directive.occurred_at)
            if existing is None:
                merged[directive.occurred_at] = directive
                continue

            if existing.reason is directive.reason:
                continue

            existing_priority = CandidateReplayLifecycleRunner._directive_priority(existing.reason)
            generated_priority = CandidateReplayLifecycleRunner._directive_priority(
                directive.reason
            )

            if generated_priority > existing_priority:
                merged[directive.occurred_at] = directive
                continue

            if generated_priority < existing_priority:
                continue

            raise ValueError("exit directives with equal priority conflict")

        return tuple(
            sorted(
                merged.values(),
                key=lambda directive: (
                    directive.occurred_at,
                    directive.reason.value,
                ),
            )
        )

    @staticmethod
    def _directive_priority(
        reason: CandidateExitReason,
    ) -> int:
        if reason is CandidateExitReason.DATA_UNRELIABLE:
            return 2

        if reason in (
            CandidateExitReason.TREND_REVERSAL,
            CandidateExitReason.PORTFOLIO_RISK,
        ):
            return 1

        raise ValueError("unsupported generated exit directive reason")
