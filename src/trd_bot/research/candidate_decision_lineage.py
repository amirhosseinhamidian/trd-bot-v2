from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.research.candidate_projection import (
    CandidateJournalOccurrence,
    CandidateOccurrenceType,
    CandidateProjection,
)
from trd_bot.research.dataset_replay import CandidateReplayStatus


class CandidateDecisionLineageKind(StrEnum):
    """Ordered stages in a candidate's historical decision lineage."""

    DATASET = "dataset"
    EXPERIMENT = "experiment"
    SIGNAL = "signal"
    CANDIDATE = "candidate"
    RISK = "risk"
    POSITION = "position"
    EXIT = "exit"


class CandidateDecisionLineageStatus(StrEnum):
    """Availability of a lineage stage in the persisted historical record."""

    AVAILABLE = "available"
    NOT_CREATED = "not_created"
    NOT_EVALUATED = "not_evaluated"
    UNAVAILABLE = "unavailable"


class CandidateDecisionLineageNode(BaseModel):
    """One navigable or explicitly absent stage in the decision chain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CandidateDecisionLineageKind
    status: CandidateDecisionLineageStatus
    resource_id: str | None = None
    portfolio_id: str | None = None
    outcome: str | None = None
    reason: str | None = None


class CandidateDecisionLineage(BaseModel):
    """Versioned lineage projection for the latest candidate occurrence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lineage_version: Literal["candidate-decision-lineage-v1"] = "candidate-decision-lineage-v1"
    journal_id: str = Field(pattern=r"^journal-[a-f0-9]{16}$")
    nodes: tuple[CandidateDecisionLineageNode, ...]

    @model_validator(mode="after")
    def stages_must_be_complete_and_ordered(self) -> Self:
        if tuple(node.kind for node in self.nodes) != tuple(CandidateDecisionLineageKind):
            raise ValueError("candidate decision lineage stages must be complete and ordered")
        return self


class CandidateRankHistoryEntry(BaseModel):
    """One immutable historical rank assigned to the same candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    journal_id: str = Field(pattern=r"^journal-[a-f0-9]{16}$")
    recorded_at: datetime
    rank: int = Field(ge=1)
    ranking_score: Decimal = Field(ge=0, le=1)
    selected: bool
    evidence_available: bool

    @classmethod
    def from_occurrence(
        cls,
        occurrence: CandidateJournalOccurrence,
    ) -> Self:
        return cls(
            journal_id=occurrence.journal_id,
            recorded_at=occurrence.recorded_at,
            rank=occurrence.rank,
            ranking_score=occurrence.ranking_score,
            selected=occurrence.selected,
            evidence_available=occurrence.decision_evidence is not None,
        )


class CandidateDecisionLineageBuilder:
    """Build a deterministic latest-stage lineage from a candidate projection."""

    @classmethod
    def build(cls, projection: CandidateProjection) -> CandidateDecisionLineage:
        occurrence = projection.latest
        candidate = occurrence.candidate

        return CandidateDecisionLineage(
            journal_id=occurrence.journal_id,
            nodes=(
                cls._available(CandidateDecisionLineageKind.DATASET, candidate.dataset_id),
                cls._available(
                    CandidateDecisionLineageKind.EXPERIMENT,
                    candidate.experiment_id,
                ),
                cls._available(CandidateDecisionLineageKind.SIGNAL, candidate.signal_id),
                cls._available(
                    CandidateDecisionLineageKind.CANDIDATE,
                    candidate.candidate_id,
                ),
                cls._risk_node(occurrence),
                cls._position_node(occurrence),
                cls._exit_node(occurrence),
            ),
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

    @staticmethod
    def _risk_node(
        occurrence: CandidateJournalOccurrence,
    ) -> CandidateDecisionLineageNode:
        if occurrence.occurrence_type is CandidateOccurrenceType.SKIPPED:
            return CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.RISK,
                status=CandidateDecisionLineageStatus.NOT_EVALUATED,
                reason=(
                    occurrence.skip_reason.value if occurrence.skip_reason is not None else None
                ),
            )

        evidence = occurrence.decision_evidence
        if evidence is None:
            return CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.RISK,
                status=CandidateDecisionLineageStatus.UNAVAILABLE,
                outcome=(
                    occurrence.risk_decision.value if occurrence.risk_decision is not None else None
                ),
                reason="legacy_evidence_unavailable",
            )

        risk = evidence.risk_compatibility
        return CandidateDecisionLineageNode(
            kind=CandidateDecisionLineageKind.RISK,
            status=CandidateDecisionLineageStatus.AVAILABLE,
            outcome=risk.decision.value if risk.decision is not None else None,
        )

    @staticmethod
    def _position_node(
        occurrence: CandidateJournalOccurrence,
    ) -> CandidateDecisionLineageNode:
        if occurrence.position_id is not None:
            return CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.POSITION,
                status=CandidateDecisionLineageStatus.AVAILABLE,
                resource_id=occurrence.position_id,
                portfolio_id=occurrence.portfolio_id,
            )

        if occurrence.occurrence_type is CandidateOccurrenceType.SKIPPED:
            reason = occurrence.skip_reason.value if occurrence.skip_reason else "skipped"
        elif occurrence.replay_status is CandidateReplayStatus.RISK_REJECTED:
            reason = "risk_rejected"
        elif occurrence.replay_status is CandidateReplayStatus.NO_FILL:
            reason = "no_fill"
        else:
            reason = "not_selected"

        return CandidateDecisionLineageNode(
            kind=CandidateDecisionLineageKind.POSITION,
            status=CandidateDecisionLineageStatus.NOT_CREATED,
            portfolio_id=occurrence.portfolio_id,
            reason=reason,
        )

    @staticmethod
    def _exit_node(
        occurrence: CandidateJournalOccurrence,
    ) -> CandidateDecisionLineageNode:
        if occurrence.exit_reason is not None:
            return CandidateDecisionLineageNode(
                kind=CandidateDecisionLineageKind.EXIT,
                status=CandidateDecisionLineageStatus.AVAILABLE,
                resource_id=occurrence.position_id,
                portfolio_id=occurrence.portfolio_id,
                outcome=occurrence.exit_reason.value,
            )

        return CandidateDecisionLineageNode(
            kind=CandidateDecisionLineageKind.EXIT,
            status=CandidateDecisionLineageStatus.NOT_CREATED,
            portfolio_id=occurrence.portfolio_id,
            reason=(
                "position_not_created" if occurrence.position_id is None else "exit_not_created"
            ),
        )
