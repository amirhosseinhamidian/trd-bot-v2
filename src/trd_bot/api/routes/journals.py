from datetime import datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from trd_bot.api.dependencies import get_candidate_journal_repository
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.db import SqlAlchemyCandidateJournalRepository
from trd_bot.research.candidate_journal import CandidateJournalEntry
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleStatus,
)
from trd_bot.research.position_monitoring import CandidateExitReason

router = APIRouter(
    prefix="/research/journals",
    tags=["Candidate journals"],
)

CandidateJournalRepositoryDependency = Annotated[
    SqlAlchemyCandidateJournalRepository,
    Depends(get_candidate_journal_repository),
]
PaginationQuery = Annotated[
    PaginationParams,
    Query(),
]


class CandidateJournalSummary(BaseModel):
    """Lightweight audit entry for candidate journal catalogs."""

    model_config = ConfigDict(frozen=True)

    journal_id: str
    schema_version: int = Field(ge=1)
    recorded_at: datetime
    evaluated_at: datetime
    status: CandidateReplayLifecycleStatus
    dataset_id: str
    portfolio_id: str
    attempted_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    selected_candidate_id: str | None = None
    signal_id: str | None = None
    experiment_id: str | None = None
    position_id: str | None = None
    exit_reason: CandidateExitReason | None = None

    @classmethod
    def from_entry(cls, journal: CandidateJournalEntry) -> Self:
        return cls(
            journal_id=journal.journal_id,
            schema_version=journal.schema_version,
            recorded_at=journal.recorded_at,
            evaluated_at=journal.evaluated_at,
            status=journal.status,
            dataset_id=journal.dataset_id,
            portfolio_id=journal.portfolio_id,
            attempted_count=len(journal.attempted_candidate_ids),
            skipped_count=len(journal.skipped_candidate_ids),
            selected_candidate_id=journal.selected_candidate_id,
            signal_id=journal.signal_id,
            experiment_id=journal.experiment_id,
            position_id=journal.position_id,
            exit_reason=journal.exit_reason,
        )


@router.get(
    "",
    response_model=Page[CandidateJournalSummary],
)
def list_candidate_journals(
    journals: CandidateJournalRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[CandidateJournalSummary]:
    """List persisted candidate lifecycle journals newest first."""

    entries = journals.list_page(
        limit=pagination.limit,
        offset=pagination.offset,
    )
    summaries = tuple(CandidateJournalSummary.from_entry(entry) for entry in entries)

    return build_page(
        summaries,
        total=journals.count(),
        pagination=pagination,
    )


@router.get(
    "/{journal_id}",
    response_model=CandidateJournalEntry,
)
def get_candidate_journal(
    journal_id: str,
    journals: CandidateJournalRepositoryDependency,
) -> CandidateJournalEntry:
    """Return one complete immutable candidate lifecycle audit record."""

    journal = journals.get(journal_id)
    if journal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="candidate journal not found",
        )

    return journal
