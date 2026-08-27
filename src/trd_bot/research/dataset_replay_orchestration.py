from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.paper.portfolio import SimulatedPortfolio
from trd_bot.research.candidate_ranking import CandidateRankingEntry
from trd_bot.research.candidates import normalize_candidate_timestamp
from trd_bot.research.dataset_replay import (
    CandidateDatasetReplayRunner,
    CandidateReplayResult,
    CandidateReplayStatus,
)
from trd_bot.research.datasets import DatasetSnapshot


class CandidateReplaySkipReason(StrEnum):
    """Reason a ranked candidate was not replay-attempted."""

    POSITION_OPENED = "position_opened"


class CandidateReplaySkip(BaseModel):
    """Auditable snapshot for one ranked candidate skipped after an earlier open."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    ranking_entry: CandidateRankingEntry
    reason: CandidateReplaySkipReason


class CandidateReplayBatchResult(BaseModel):
    """Deterministic multi-candidate replay result for one portfolio snapshot."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    dataset_id: str = Field(min_length=1, max_length=100)
    evaluated_at: datetime
    portfolio_id: str = Field(pattern=r"^portfolio-[a-f0-9]{16}$")
    initial_portfolio_updated_at: datetime

    total_candidates: int = Field(ge=0)
    attempted_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)

    attempted: tuple[CandidateReplayResult, ...]
    skipped: tuple[CandidateReplaySkip, ...] = ()
    skipped_candidate_ids: tuple[str, ...]
    selected_candidate_id: str | None = Field(
        default=None,
        pattern=r"^candidate-[a-f0-9]{16}$",
    )
    portfolio: SimulatedPortfolio

    @field_validator(
        "evaluated_at",
        "initial_portfolio_updated_at",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        if self.attempted_count != len(self.attempted):
            raise ValueError("replay attempted count does not match results")

        if self.skipped_count != len(self.skipped_candidate_ids):
            raise ValueError("replay skipped count does not match candidate IDs")

        if self.skipped and self.skipped_count != len(self.skipped):
            raise ValueError("replay skipped count does not match snapshots")

        if self.skipped:
            skipped_ids = tuple(item.ranking_entry.candidate.candidate_id for item in self.skipped)
            if skipped_ids != self.skipped_candidate_ids:
                raise ValueError("replay skipped snapshots do not match candidate IDs")

            if any(
                item.ranking_entry.candidate.dataset_id != self.dataset_id for item in self.skipped
            ):
                raise ValueError("replay batch skipped candidate belongs to another dataset")

        if self.total_candidates != self.attempted_count + self.skipped_count:
            raise ValueError("replay batch counts do not reconcile")

        if self.portfolio.portfolio_id != self.portfolio_id:
            raise ValueError("replay batch portfolio ID does not match final portfolio")

        attempted_ids = tuple(
            result.ranking_entry.candidate.candidate_id for result in self.attempted
        )
        all_ids = (*attempted_ids, *self.skipped_candidate_ids)
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("replay batch candidate IDs must be unique")

        for result in self.attempted:
            if result.dataset_id != self.dataset_id:
                raise ValueError("replay batch contains another dataset")
            if result.evaluated_at != self.evaluated_at:
                raise ValueError("replay batch evaluation times must match")

        opened = tuple(
            result for result in self.attempted if result.status is CandidateReplayStatus.OPENED
        )
        if len(opened) > 1:
            raise ValueError("replay batch cannot open more than one candidate")

        if opened:
            opened_result = opened[0]
            if self.attempted[-1] != opened_result:
                raise ValueError("opened candidate must be the final replay attempt")

            if opened_result.simulation is None:
                raise ValueError("opened replay must contain simulation details")

            expected_selected_id = opened_result.simulation.selected_candidate.candidate_id
            if self.selected_candidate_id != expected_selected_id:
                raise ValueError("replay batch selected candidate does not match open")

            if self.portfolio != opened_result.simulation.portfolio:
                raise ValueError("replay batch final portfolio does not match open")

            return self

        if self.selected_candidate_id is not None:
            raise ValueError("replay batch without an open cannot select a candidate")

        if self.skipped_candidate_ids or self.skipped:
            raise ValueError("replay batch can skip candidates only after an open")

        if self.portfolio.updated_at != self.initial_portfolio_updated_at:
            raise ValueError("replay batch without an open cannot change portfolio")

        return self


class CandidateDatasetReplayOrchestrator:
    """Try ranked candidates in rank order until one simulated position opens."""

    def __init__(
        self,
        *,
        replay_runner: CandidateDatasetReplayRunner | None = None,
    ) -> None:
        self._replay_runner = replay_runner or CandidateDatasetReplayRunner()

    def run(
        self,
        *,
        entries: Sequence[CandidateRankingEntry],
        portfolio: SimulatedPortfolio,
        dataset: DatasetSnapshot,
        evaluated_at: datetime,
    ) -> CandidateReplayBatchResult:
        normalized_evaluated_at = normalize_candidate_timestamp(evaluated_at)
        ordered = tuple(
            sorted(
                entries,
                key=lambda entry: (
                    entry.rank,
                    entry.candidate.candidate_id,
                ),
            )
        )

        candidate_ids = tuple(entry.candidate.candidate_id for entry in ordered)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("replay batch candidate IDs must be unique")

        ranks = tuple(entry.rank for entry in ordered)
        if len(ranks) != len(set(ranks)):
            raise ValueError("replay batch ranks must be unique")

        attempted: list[CandidateReplayResult] = []
        skipped: tuple[CandidateReplaySkip, ...] = ()
        skipped_candidate_ids: tuple[str, ...] = ()
        selected_candidate_id: str | None = None
        final_portfolio = portfolio

        for index, entry in enumerate(ordered):
            result = self._replay_runner.run(
                entry=entry,
                portfolio=portfolio,
                dataset=dataset,
                evaluated_at=normalized_evaluated_at,
            )
            attempted.append(result)

            if result.status is not CandidateReplayStatus.OPENED:
                continue

            if result.simulation is None:
                raise ValueError("opened replay must contain simulation details")

            final_portfolio = result.simulation.portfolio
            selected_candidate_id = result.simulation.selected_candidate.candidate_id
            skipped = tuple(
                CandidateReplaySkip(
                    ranking_entry=later_entry,
                    reason=CandidateReplaySkipReason.POSITION_OPENED,
                )
                for later_entry in ordered[index + 1 :]
            )
            skipped_candidate_ids = tuple(
                item.ranking_entry.candidate.candidate_id for item in skipped
            )
            break

        return CandidateReplayBatchResult(
            dataset_id=dataset.dataset_id,
            evaluated_at=normalized_evaluated_at,
            portfolio_id=portfolio.portfolio_id,
            initial_portfolio_updated_at=portfolio.updated_at,
            total_candidates=len(ordered),
            attempted_count=len(attempted),
            skipped_count=len(skipped_candidate_ids),
            attempted=tuple(attempted),
            skipped=skipped,
            skipped_candidate_ids=skipped_candidate_ids,
            selected_candidate_id=selected_candidate_id,
            portfolio=final_portfolio,
        )
