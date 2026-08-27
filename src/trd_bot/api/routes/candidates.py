from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from trd_bot.api.dependencies import get_candidate_projection_repository
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.db import SqlAlchemyCandidateProjectionRepository
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.research.candidate_projection import (
    CandidateJournalOccurrence,
    CandidateOccurrenceType,
    CandidateProjection,
)
from trd_bot.research.candidates import (
    CandidateAction,
    CandidateStatus,
    ResearchCandidate,
)
from trd_bot.research.dataset_replay import CandidateReplayStatus
from trd_bot.research.dataset_replay_orchestration import CandidateReplaySkipReason
from trd_bot.research.position_monitoring import CandidateExitReason
from trd_bot.research.risk_policy import CandidateRiskDecision

router = APIRouter(
    prefix="/research/candidates",
    tags=["Candidate projections"],
)

CandidateProjectionRepositoryDependency = Annotated[
    SqlAlchemyCandidateProjectionRepository,
    Depends(get_candidate_projection_repository),
]
PaginationQuery = Annotated[PaginationParams, Query()]


class CandidateProjectionSummary(BaseModel):
    """Lightweight latest view of one persisted candidate occurrence."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str
    status: CandidateStatus
    action: CandidateAction
    pair: TradingPair
    timeframe: Timeframe
    strategy_name: str
    strategy_version: str
    confidence: Decimal
    signal_score: Decimal
    created_at: datetime
    valid_until: datetime

    occurrence_count: int = Field(ge=1)
    latest_journal_id: str
    latest_recorded_at: datetime
    latest_occurrence_type: CandidateOccurrenceType
    latest_replay_status: CandidateReplayStatus | None
    latest_risk_decision: CandidateRiskDecision | None
    latest_skip_reason: CandidateReplaySkipReason | None = None
    selected: bool
    position_id: str | None = None
    exit_reason: CandidateExitReason | None = None

    @classmethod
    def from_projection(cls, projection: CandidateProjection) -> Self:
        candidate = projection.candidate
        latest = projection.latest

        return cls(
            candidate_id=candidate.candidate_id,
            status=candidate.status,
            action=candidate.action,
            pair=candidate.pair,
            timeframe=candidate.timeframe,
            strategy_name=candidate.strategy_name,
            strategy_version=candidate.strategy_version,
            confidence=candidate.confidence,
            signal_score=candidate.signal_score,
            created_at=candidate.created_at,
            valid_until=candidate.valid_until,
            occurrence_count=len(projection.history),
            latest_journal_id=latest.journal_id,
            latest_recorded_at=latest.recorded_at,
            latest_occurrence_type=latest.occurrence_type,
            latest_replay_status=latest.replay_status,
            latest_risk_decision=latest.risk_decision,
            latest_skip_reason=latest.skip_reason,
            selected=latest.selected,
            position_id=latest.position_id,
            exit_reason=latest.exit_reason,
        )


class CandidateProjectionDetail(BaseModel):
    """Complete candidate snapshot with latest persisted attempt metadata."""

    model_config = ConfigDict(frozen=True)

    candidate: ResearchCandidate
    occurrence_count: int = Field(ge=1)
    journal_ids: tuple[str, ...]
    latest: CandidateJournalOccurrence

    @classmethod
    def from_projection(cls, projection: CandidateProjection) -> Self:
        return cls(
            candidate=projection.candidate,
            occurrence_count=len(projection.history),
            journal_ids=tuple(item.journal_id for item in projection.history),
            latest=projection.latest,
        )


def _get_projection_or_404(
    candidate_id: str,
    projections: SqlAlchemyCandidateProjectionRepository,
) -> CandidateProjection:
    projection = projections.get(candidate_id)
    if projection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="candidate projection not found",
        )
    return projection


@router.get("", response_model=Page[CandidateProjectionSummary])
def list_candidate_projections(
    projections: CandidateProjectionRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[CandidateProjectionSummary]:
    """List persisted candidate read models newest first."""

    page_items = projections.list_page(
        limit=pagination.limit,
        offset=pagination.offset,
    )
    summaries = tuple(CandidateProjectionSummary.from_projection(item) for item in page_items)

    return build_page(
        summaries,
        total=projections.count(),
        pagination=pagination,
    )


@router.get(
    "/{candidate_id}/lineage",
    response_model=Page[CandidateJournalOccurrence],
)
def list_candidate_lineage(
    candidate_id: str,
    projections: CandidateProjectionRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[CandidateJournalOccurrence]:
    """List persisted candidate lineage occurrences newest first."""

    projection = _get_projection_or_404(candidate_id, projections)
    items = projection.history[pagination.offset : pagination.offset + pagination.limit]

    return build_page(
        items,
        total=len(projection.history),
        pagination=pagination,
    )


@router.get(
    "/{candidate_id}",
    response_model=CandidateProjectionDetail,
)
def get_candidate_projection(
    candidate_id: str,
    projections: CandidateProjectionRepositoryDependency,
) -> CandidateProjectionDetail:
    """Return the persisted candidate snapshot and lineage pointers."""

    return CandidateProjectionDetail.from_projection(
        _get_projection_or_404(candidate_id, projections)
    )
