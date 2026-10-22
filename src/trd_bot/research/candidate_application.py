from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.paper import (
    SimulatedPortfolioLedger,
    SimulationMode,
)
from trd_bot.research.candidate_generation import CandidateGenerator
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
)
from trd_bot.research.candidate_ranking import (
    CandidateRanker,
    CandidateRankingResult,
)
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleResult,
    CandidateReplayLifecycleRunner,
    CandidateReplayLifecycleStatus,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.experiment_executions import HistoricalExecutionParameters
from trd_bot.research.experiments import ResearchExperiment


class CandidateApplicationStatus(StrEnum):
    """Outcome of one offline candidate application handoff."""

    NO_CANDIDATES = "no_candidates"
    NO_POSITION = "no_position"
    CLOSED = "closed"


class CandidateLifecycleRecorder(Protocol):
    """Persistence boundary for one complete candidate lifecycle."""

    def record(
        self,
        lifecycle: CandidateReplayLifecycleResult,
    ) -> CandidateJournalEntry: ...


class CandidateApplicationResult(BaseModel):
    """Auditable result of applying one experiment to candidate decision logic."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    status: CandidateApplicationStatus

    experiment_id: str = Field(
        pattern=r"^experiment-[a-f0-9]{16}$",
    )
    dataset_id: str = Field(
        min_length=1,
        max_length=100,
    )

    generated_candidate_count: int = Field(ge=0)
    evaluated_at: datetime | None = None

    ranking: CandidateRankingResult | None = None
    lifecycle: CandidateReplayLifecycleResult | None = None
    journal: CandidateJournalEntry | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        decision_artifacts = (
            self.evaluated_at,
            self.ranking,
            self.lifecycle,
            self.journal,
        )

        if self.status is CandidateApplicationStatus.NO_CANDIDATES:
            if any(value is not None for value in decision_artifacts):
                raise ValueError(
                    "no-candidates application result cannot contain decision artifacts"
                )

            if self.generated_candidate_count != 0:
                raise ValueError(
                    "no-candidates application result must have zero generated candidates"
                )

            return self

        if self.generated_candidate_count == 0 or any(
            value is None for value in decision_artifacts
        ):
            raise ValueError("evaluated candidate application result requires decision artifacts")

        assert self.lifecycle is not None

        expected_lifecycle_status = {
            CandidateApplicationStatus.NO_POSITION: CandidateReplayLifecycleStatus.NO_POSITION,
            CandidateApplicationStatus.CLOSED: CandidateReplayLifecycleStatus.CLOSED,
        }[self.status]

        if self.lifecycle.status is not expected_lifecycle_status:
            raise ValueError("candidate application status must match lifecycle status")

        assert self.evaluated_at is not None
        assert self.ranking is not None

        if (
            self.ranking.ranked_at != self.evaluated_at
            or self.lifecycle.evaluated_at != self.evaluated_at
        ):
            raise ValueError(
                "candidate application evaluation time must match ranking and lifecycle"
            )

        ranked_candidate_ids = tuple(entry.candidate.candidate_id for entry in self.ranking.entries)
        replay_candidate_ids = (
            *(
                result.ranking_entry.candidate.candidate_id
                for result in self.lifecycle.replay.attempted
            ),
            *self.lifecycle.replay.skipped_candidate_ids,
        )

        if ranked_candidate_ids != replay_candidate_ids:
            raise ValueError(
                "candidate application ranking and lifecycle candidate batches must match"
            )

        assert self.journal is not None

        expected_journal = CandidateJournalBuilder.from_lifecycle(self.lifecycle)

        if self.journal != expected_journal:
            raise ValueError("candidate application journal must match lifecycle")

        return self


class CandidateApplicationOrchestrator:
    """Connect candidate generation, ranking, replay, and persistence."""

    def __init__(
        self,
        *,
        recorder: CandidateLifecycleRecorder,
        generator: CandidateGenerator | None = None,
        ranker: CandidateRanker | None = None,
        lifecycle_runner: CandidateReplayLifecycleRunner | None = None,
        portfolio_ledger: SimulatedPortfolioLedger | None = None,
    ) -> None:
        self._recorder = recorder
        self._generator = generator or CandidateGenerator()
        self._ranker = ranker or CandidateRanker()
        self._lifecycle_runner = lifecycle_runner or CandidateReplayLifecycleRunner()
        self._portfolio_ledger = portfolio_ledger or SimulatedPortfolioLedger()

    def run(
        self,
        *,
        experiment: ResearchExperiment,
        dataset: DatasetSnapshot,
        parameters: HistoricalExecutionParameters,
    ) -> CandidateApplicationResult:
        if experiment.dataset_id != dataset.dataset_id:
            raise ValueError("candidate application experiment and dataset lineage must match")

        if parameters.horizon_candles != experiment.horizon_candles:
            raise ValueError("candidate application execution horizon must match experiment")

        if parameters.strategy_name != experiment.strategy_name:
            raise ValueError("candidate application execution strategy must match experiment")

        if parameters.strategy_version != experiment.strategy_version:
            raise ValueError(
                "candidate application execution strategy version must match experiment"
            )

        expected_strategy_parameters = dict(parameters.strategy_parameter_pairs())
        experiment_parameters = {
            parameter.name: parameter.value for parameter in experiment.parameters
        }
        actual_strategy_parameters = {
            name: experiment_parameters.get(name) for name in expected_strategy_parameters
        }

        if actual_strategy_parameters != expected_strategy_parameters:
            raise ValueError(
                "candidate application execution strategy parameters must match experiment"
            )

        candidates = self._generator.generate(
            experiment=experiment,
            dataset=dataset,
        )

        if not candidates:
            return CandidateApplicationResult(
                status=CandidateApplicationStatus.NO_CANDIDATES,
                experiment_id=experiment.experiment_id,
                dataset_id=dataset.dataset_id,
                generated_candidate_count=0,
                evaluated_at=None,
                ranking=None,
                lifecycle=None,
                journal=None,
            )

        evaluated_at = max(candidate.created_at for candidate in candidates)

        ranking = self._ranker.rank(
            candidates=candidates,
            at=evaluated_at,
        )

        portfolio = self._portfolio_ledger.create(
            mode=SimulationMode.PAPER,
            dataset_id=dataset.dataset_id,
            starting_cash=parameters.starting_balance,
            fee_rate=parameters.fee_rate,
            created_at=evaluated_at,
        )

        lifecycle = self._lifecycle_runner.run(
            entries=ranking.entries,
            portfolio=portfolio,
            dataset=dataset,
            evaluated_at=evaluated_at,
            historical_signals=experiment.result.signals,
        )

        journal = self._recorder.record(lifecycle)

        status = (
            CandidateApplicationStatus.CLOSED
            if lifecycle.status is CandidateReplayLifecycleStatus.CLOSED
            else CandidateApplicationStatus.NO_POSITION
        )

        return CandidateApplicationResult(
            status=status,
            experiment_id=experiment.experiment_id,
            dataset_id=dataset.dataset_id,
            generated_candidate_count=len(candidates),
            evaluated_at=evaluated_at,
            ranking=ranking,
            lifecycle=lifecycle,
            journal=journal,
        )
