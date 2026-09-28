from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from trd_bot.paper import PortfolioTimelineEvent, SimulatedPortfolio, SimulatedPosition
from trd_bot.research.candidate_decision_evidence import CandidateDecisionEvidence
from trd_bot.research.candidate_decision_lineage import (
    CandidateDecisionLineageKind,
    CandidateDecisionLineageNode,
    CandidateDecisionLineageStatus,
)
from trd_bot.research.candidate_journal import CandidateJournalEntry
from trd_bot.research.candidate_projection import CandidateJournalProjectionReader
from trd_bot.research.candidates import ResearchCandidate, normalize_candidate_timestamp


class PositionLineageStatus(StrEnum):
    """Completeness of the persisted decision evidence for one position."""

    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    CONFLICT = "conflict"


class PositionDetailReport(BaseModel):
    """Read-only accounting and origin lineage for one simulated position."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_detail_version: Literal["position-detail-v1"] = "position-detail-v1"
    as_of: datetime
    dataset_id: str
    position: SimulatedPosition
    lineage_status: PositionLineageStatus
    journal_id: str | None = None
    candidate: ResearchCandidate | None = None
    decision_evidence: CandidateDecisionEvidence | None = None
    nodes: tuple[CandidateDecisionLineageNode, ...]
    events: tuple[PortfolioTimelineEvent, ...]
    interpretation: Literal["historical_research_only"] = "historical_research_only"

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if tuple(node.kind for node in self.nodes) != tuple(CandidateDecisionLineageKind):
            raise ValueError("position lineage stages must be complete and ordered")
        if any(event.position_id != self.position.position_id for event in self.events):
            raise ValueError("position detail events must belong to the requested position")
        if any(event.portfolio_id != self.position.portfolio_id for event in self.events):
            raise ValueError("position detail events must belong to the requested portfolio")
        if tuple(event.sequence_number for event in self.events) != tuple(
            sorted(event.sequence_number for event in self.events)
        ):
            raise ValueError("position detail events must be ordered")

        has_complete_evidence = self.lineage_status is PositionLineageStatus.COMPLETE
        if has_complete_evidence != (self.journal_id is not None and self.candidate is not None):
            raise ValueError("complete position lineage requires journal and candidate evidence")
        if self.decision_evidence is not None and self.candidate is None:
            raise ValueError("decision evidence requires a candidate")
        return self


class PositionDetailBuilder:
    """Join immutable portfolio events with exact candidate-journal evidence."""

    @classmethod
    def build(
        cls,
        *,
        portfolio: SimulatedPortfolio,
        position: SimulatedPosition,
        journals: tuple[CandidateJournalEntry, ...],
    ) -> PositionDetailReport:
        if position.portfolio_id != portfolio.portfolio_id:
            raise ValueError("position does not belong to the requested portfolio")

        events = tuple(
            event for event in portfolio.timeline if event.position_id == position.position_id
        )
        matching = tuple(
            journal
            for journal in journals
            if journal.portfolio_id == portfolio.portfolio_id
            and journal.position_id == position.position_id
        )
        unique, conflict = cls._deduplicate(matching)

        if conflict or len(unique) > 1:
            return cls._without_evidence(
                portfolio=portfolio,
                position=position,
                events=events,
                status=PositionLineageStatus.CONFLICT,
                reason="conflicting_lineage_evidence",
            )
        if not unique:
            return cls._without_evidence(
                portfolio=portfolio,
                position=position,
                events=events,
                status=PositionLineageStatus.UNAVAILABLE,
                reason="lineage_evidence_unavailable",
            )

        journal = unique[0]
        projections = CandidateJournalProjectionReader.build((journal,))
        projection = next(
            (
                item
                for item in projections
                if item.candidate.candidate_id == journal.selected_candidate_id
            ),
            None,
        )
        if projection is None or projection.latest.position_id != position.position_id:
            return cls._without_evidence(
                portfolio=portfolio,
                position=position,
                events=events,
                status=PositionLineageStatus.CONFLICT,
                reason="conflicting_lineage_evidence",
            )

        occurrence = projection.latest
        candidate = projection.candidate
        nodes = (
            cls._available(CandidateDecisionLineageKind.DATASET, portfolio.dataset_id),
            cls._available(CandidateDecisionLineageKind.EXPERIMENT, candidate.experiment_id),
            cls._available(CandidateDecisionLineageKind.SIGNAL, candidate.signal_id),
            cls._available(CandidateDecisionLineageKind.CANDIDATE, candidate.candidate_id),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.RISK,
                status=CandidateDecisionLineageStatus.AVAILABLE,
                outcome=(
                    occurrence.risk_decision.value if occurrence.risk_decision is not None else None
                ),
            ),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.POSITION,
                status=CandidateDecisionLineageStatus.AVAILABLE,
                resource_id=position.position_id,
                portfolio_id=portfolio.portfolio_id,
                outcome=position.status.value,
            ),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.EXIT,
                status=CandidateDecisionLineageStatus.AVAILABLE,
                resource_id=position.position_id,
                portfolio_id=portfolio.portfolio_id,
                outcome=(
                    occurrence.exit_reason.value if occurrence.exit_reason is not None else None
                ),
            ),
        )
        return PositionDetailReport(
            as_of=portfolio.updated_at,
            dataset_id=portfolio.dataset_id,
            position=position,
            lineage_status=PositionLineageStatus.COMPLETE,
            journal_id=journal.journal_id,
            candidate=candidate,
            decision_evidence=occurrence.decision_evidence,
            nodes=nodes,
            events=events,
        )

    @staticmethod
    def _deduplicate(
        journals: tuple[CandidateJournalEntry, ...],
    ) -> tuple[tuple[CandidateJournalEntry, ...], bool]:
        by_id: dict[str, CandidateJournalEntry] = {}
        conflict = False
        for journal in journals:
            existing = by_id.get(journal.journal_id)
            if existing is not None and existing != journal:
                conflict = True
            else:
                by_id[journal.journal_id] = journal
        return tuple(by_id.values()), conflict

    @classmethod
    def _without_evidence(
        cls,
        *,
        portfolio: SimulatedPortfolio,
        position: SimulatedPosition,
        events: tuple[PortfolioTimelineEvent, ...],
        status: PositionLineageStatus,
        reason: str,
    ) -> PositionDetailReport:
        unavailable = CandidateDecisionLineageStatus.UNAVAILABLE
        nodes = (
            cls._available(CandidateDecisionLineageKind.DATASET, portfolio.dataset_id),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.EXPERIMENT,
                status=unavailable,
                reason=reason,
            ),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.SIGNAL,
                status=unavailable,
                reason=reason,
            ),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.CANDIDATE,
                status=unavailable,
                reason=reason,
            ),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.RISK,
                status=unavailable,
                reason=reason,
            ),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.POSITION,
                status=CandidateDecisionLineageStatus.AVAILABLE,
                resource_id=position.position_id,
                portfolio_id=portfolio.portfolio_id,
                outcome=position.status.value,
            ),
            CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.EXIT,
                status=(
                    CandidateDecisionLineageStatus.NOT_CREATED
                    if position.closed_at is None
                    else unavailable
                ),
                resource_id=position.position_id,
                portfolio_id=portfolio.portfolio_id,
                reason="exit_not_created" if position.closed_at is None else reason,
            ),
        )
        return PositionDetailReport(
            as_of=portfolio.updated_at,
            dataset_id=portfolio.dataset_id,
            position=position,
            lineage_status=status,
            nodes=nodes,
            events=events,
        )

    @staticmethod
    def _available(
        kind: CandidateDecisionLineageKind,
        resource_id: str,
    ) -> CandidateDecisionLineageNode:
        return CandidateDecisionLineageNode(
            kind=kind,
            status=CandidateDecisionLineageStatus.AVAILABLE,
            resource_id=resource_id,
        )
