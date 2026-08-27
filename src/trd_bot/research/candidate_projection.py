from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.research.candidate_journal import CandidateJournalEntry
from trd_bot.research.candidates import (
    CandidateStatus,
    ResearchCandidate,
    normalize_candidate_timestamp,
)
from trd_bot.research.dataset_replay import CandidateReplayStatus
from trd_bot.research.dataset_replay_orchestration import CandidateReplaySkipReason
from trd_bot.research.position_monitoring import CandidateExitReason
from trd_bot.research.risk_policy import CandidateRiskDecision


class CandidateOccurrenceType(StrEnum):
    """How one candidate entered a persisted journal lineage."""

    ATTEMPTED = "attempted"
    SKIPPED = "skipped"


class CandidateJournalOccurrence(BaseModel):
    """One persisted attempted or skipped candidate occurrence in a lifecycle journal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    journal_id: str = Field(pattern=r"^journal-[a-f0-9]{16}$")
    recorded_at: datetime
    evaluated_at: datetime
    portfolio_id: str = Field(pattern=r"^portfolio-[a-f0-9]{16}$")

    rank: int = Field(ge=1)
    ranking_score: Decimal = Field(ge=0, le=1)
    occurrence_type: CandidateOccurrenceType = CandidateOccurrenceType.ATTEMPTED
    replay_status: CandidateReplayStatus | None
    risk_decision: CandidateRiskDecision | None
    skip_reason: CandidateReplaySkipReason | None = None

    selected: bool
    position_id: str | None = Field(
        default=None,
        pattern=r"^position-[a-f0-9]{16}$",
    )
    exit_reason: CandidateExitReason | None = None
    candidate: ResearchCandidate

    @field_validator("recorded_at", "evaluated_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_occurrence(self) -> Self:
        if self.occurrence_type is CandidateOccurrenceType.SKIPPED:
            if self.replay_status is not None or self.risk_decision is not None:
                raise ValueError("skipped occurrence cannot contain replay or risk outcomes")
            if self.skip_reason is None:
                raise ValueError("skipped occurrence requires a skip reason")
            if self.selected:
                raise ValueError("skipped occurrence cannot be selected")
            if self.candidate.status is CandidateStatus.SELECTED:
                raise ValueError("skipped occurrence cannot contain selected candidate state")
            if self.position_id is not None or self.exit_reason is not None:
                raise ValueError("skipped occurrence cannot contain position lineage")
            return self

        if self.skip_reason is not None:
            raise ValueError("attempted occurrence cannot contain a skip reason")
        if self.replay_status is None or self.risk_decision is None:
            raise ValueError("attempted occurrence requires replay and risk outcomes")

        if self.selected:
            if self.replay_status is not CandidateReplayStatus.OPENED:
                raise ValueError("selected occurrence requires an opened replay")
            if self.candidate.status is not CandidateStatus.SELECTED:
                raise ValueError("selected occurrence requires selected candidate state")
            if self.position_id is None or self.exit_reason is None:
                raise ValueError("selected occurrence requires closed position lineage")
            return self

        if self.replay_status is CandidateReplayStatus.OPENED:
            raise ValueError("opened replay must be marked selected")
        if self.position_id is not None or self.exit_reason is not None:
            raise ValueError("unselected occurrence cannot contain position lineage")

        return self


class CandidateProjection(BaseModel):
    """Latest candidate snapshot plus every persisted journal occurrence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: ResearchCandidate
    latest: CandidateJournalOccurrence
    history: tuple[CandidateJournalOccurrence, ...]

    @model_validator(mode="after")
    def validate_projection(self) -> Self:
        if not self.history:
            raise ValueError("candidate projection requires journal history")
        if self.latest != self.history[0]:
            raise ValueError("candidate projection latest occurrence must be first")
        if self.candidate != self.latest.candidate:
            raise ValueError("candidate projection must use latest candidate snapshot")

        candidate_id = self.candidate.candidate_id
        if any(item.candidate.candidate_id != candidate_id for item in self.history):
            raise ValueError("candidate projection cannot mix candidate identities")

        journal_ids = tuple(item.journal_id for item in self.history)
        if len(journal_ids) != len(set(journal_ids)):
            raise ValueError("candidate projection journal history must be unique")

        expected = tuple(
            sorted(
                self.history,
                key=lambda item: (item.recorded_at, item.journal_id),
                reverse=True,
            )
        )
        if self.history != expected:
            raise ValueError("candidate projection history must be newest first")

        return self


class CandidateJournalProjectionReader:
    """Build read-only candidate projections from immutable journal payloads."""

    @staticmethod
    def build(
        journals: tuple[CandidateJournalEntry, ...],
    ) -> tuple[CandidateProjection, ...]:
        occurrences: dict[str, list[CandidateJournalOccurrence]] = {}

        for journal in journals:
            for attempt in journal.lifecycle.replay.attempted:
                simulation = attempt.simulation
                selected = attempt.status is CandidateReplayStatus.OPENED

                if selected:
                    if simulation is None:
                        raise ValueError("opened replay requires simulation details")
                    candidate = simulation.selected_candidate
                    position_id = journal.position_id
                    exit_reason = journal.exit_reason
                else:
                    candidate = attempt.ranking_entry.candidate
                    position_id = None
                    exit_reason = None

                occurrence = CandidateJournalOccurrence(
                    journal_id=journal.journal_id,
                    recorded_at=journal.recorded_at,
                    evaluated_at=journal.evaluated_at,
                    portfolio_id=journal.portfolio_id,
                    rank=attempt.ranking_entry.rank,
                    ranking_score=attempt.ranking_entry.total_score,
                    replay_status=attempt.status,
                    risk_decision=attempt.risk_assessment.decision,
                    selected=selected,
                    position_id=position_id,
                    exit_reason=exit_reason,
                    candidate=candidate,
                )
                occurrences.setdefault(candidate.candidate_id, []).append(occurrence)

            for skipped in journal.lifecycle.replay.skipped:
                candidate = skipped.ranking_entry.candidate
                occurrence = CandidateJournalOccurrence(
                    journal_id=journal.journal_id,
                    recorded_at=journal.recorded_at,
                    evaluated_at=journal.evaluated_at,
                    portfolio_id=journal.portfolio_id,
                    rank=skipped.ranking_entry.rank,
                    ranking_score=skipped.ranking_entry.total_score,
                    occurrence_type=CandidateOccurrenceType.SKIPPED,
                    replay_status=None,
                    risk_decision=None,
                    skip_reason=skipped.reason,
                    selected=False,
                    candidate=candidate,
                )
                occurrences.setdefault(candidate.candidate_id, []).append(occurrence)

        projections = tuple(
            CandidateJournalProjectionReader._build_projection(items)
            for items in occurrences.values()
        )

        return tuple(
            sorted(
                projections,
                key=lambda item: (
                    item.latest.recorded_at,
                    item.latest.journal_id,
                    item.candidate.candidate_id,
                ),
                reverse=True,
            )
        )

    @staticmethod
    def get(
        projections: tuple[CandidateProjection, ...],
        candidate_id: str,
    ) -> CandidateProjection | None:
        return next(
            (
                projection
                for projection in projections
                if projection.candidate.candidate_id == candidate_id
            ),
            None,
        )

    @staticmethod
    def _build_projection(
        occurrences: list[CandidateJournalOccurrence],
    ) -> CandidateProjection:
        history = tuple(
            sorted(
                occurrences,
                key=lambda item: (item.recorded_at, item.journal_id),
                reverse=True,
            )
        )
        latest = history[0]

        return CandidateProjection(
            candidate=latest.candidate,
            latest=latest,
            history=history,
        )
