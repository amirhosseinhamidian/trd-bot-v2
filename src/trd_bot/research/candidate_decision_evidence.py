from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.research.candidate_ranking import (
    SCORE_QUANTUM,
    CandidateRankingComponentName,
    CandidateRankingEntry,
)
from trd_bot.research.dataset_replay_orchestration import CandidateReplaySkipReason
from trd_bot.research.risk_policy import (
    CandidateRiskAssessment,
    CandidateRiskCheck,
    CandidateRiskCheckName,
    CandidateRiskDecision,
)


class CandidateRankingEvidenceComponentName(StrEnum):
    """Stable public names for candidate ranking score inputs."""

    CONFIDENCE = "confidence"
    SIGNAL_QUALITY = "signal_quality"
    FRESHNESS = "freshness"


class CandidateRiskCompatibilityStatus(StrEnum):
    """Whether portfolio-aware risk evidence exists for one occurrence."""

    EVALUATED = "evaluated"
    NOT_EVALUATED = "not_evaluated"


class CandidateRankingEvidenceComponent(BaseModel):
    """One normalized input and its exact weighted ranking contribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: CandidateRankingEvidenceComponentName
    source_component: CandidateRankingComponentName
    raw_value: Decimal = Field(ge=0, le=1)
    weight: Decimal = Field(ge=0, le=1)
    weighted_value: Decimal = Field(ge=0, le=1)
    formula: Literal["round_half_up(raw_value * weight, 0.000001)"] = (
        "round_half_up(raw_value * weight, 0.000001)"
    )

    @model_validator(mode="after")
    def validate_component(self) -> Self:
        expected_source = {
            CandidateRankingEvidenceComponentName.CONFIDENCE: (
                CandidateRankingComponentName.CONFIDENCE
            ),
            CandidateRankingEvidenceComponentName.SIGNAL_QUALITY: (
                CandidateRankingComponentName.SIGNAL_STRENGTH
            ),
            CandidateRankingEvidenceComponentName.FRESHNESS: (
                CandidateRankingComponentName.FRESHNESS
            ),
        }[self.name]
        if self.source_component is not expected_source:
            raise ValueError("candidate ranking evidence source is inconsistent")

        expected_weighted_value = _quantize_score(self.raw_value * self.weight)
        if self.weighted_value != expected_weighted_value:
            raise ValueError("candidate ranking evidence contribution is inconsistent")
        return self


class CandidateRankingTieBreakEvidence(BaseModel):
    """Explicit final ordering rule for candidates with equal total scores."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tie_break_version: Literal["candidate-ranking-tie-break-v1"] = "candidate-ranking-tie-break-v1"
    rule: Literal["total_score_desc_then_candidate_id_asc"] = (
        "total_score_desc_then_candidate_id_asc"
    )
    applied: bool
    tied_candidate_ids: tuple[str, ...]
    position_within_tie: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_tie_break(self) -> Self:
        if self.applied:
            if len(self.tied_candidate_ids) < 2:
                raise ValueError("applied candidate tie-break requires at least two candidates")
            if self.tied_candidate_ids != tuple(sorted(self.tied_candidate_ids)):
                raise ValueError("candidate tie-break IDs must use ascending order")
            if self.position_within_tie is None:
                raise ValueError("applied candidate tie-break requires a position")
            if self.position_within_tie > len(self.tied_candidate_ids):
                raise ValueError("candidate tie-break position exceeds tied candidates")
            return self

        if self.tied_candidate_ids or self.position_within_tie is not None:
            raise ValueError("unused candidate tie-break cannot contain tied candidates")
        return self


class CandidateRankingBreakdown(BaseModel):
    """Versioned reconstruction of one persisted candidate ranking entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score_version: Literal["candidate-ranking-score-v1"] = "candidate-ranking-score-v1"
    candidate_id: str = Field(pattern=r"^candidate-[a-f0-9]{16}$")
    rank: int = Field(ge=1)
    total_score: Decimal = Field(ge=0, le=1)
    formula: Literal["sum(weighted_components)"] = "sum(weighted_components)"
    components: tuple[CandidateRankingEvidenceComponent, ...]
    tie_break: CandidateRankingTieBreakEvidence

    @model_validator(mode="after")
    def validate_breakdown(self) -> Self:
        expected_names = tuple(CandidateRankingEvidenceComponentName)
        actual_names = tuple(component.name for component in self.components)
        if actual_names != expected_names:
            raise ValueError("candidate ranking breakdown components must be complete and ordered")

        expected_total = _quantize_score(
            sum(
                (component.weighted_value for component in self.components),
                start=Decimal("0"),
            )
        )
        if self.total_score != expected_total:
            raise ValueError("candidate ranking breakdown total is inconsistent")

        if self.tie_break.applied:
            position = self.tie_break.position_within_tie
            if position is None:
                raise ValueError("candidate ranking tie-break position is required")
            if self.tie_break.tied_candidate_ids[position - 1] != self.candidate_id:
                raise ValueError("candidate ranking tie-break position does not match candidate")
        return self


class CandidateRiskCompatibilityBreakdown(BaseModel):
    """Portfolio-aware gate evidence kept separate from the pre-risk rank score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    compatibility_version: Literal["candidate-risk-compatibility-v1"] = (
        "candidate-risk-compatibility-v1"
    )
    status: CandidateRiskCompatibilityStatus
    affects_ranking_score: Literal[False] = False
    decision: CandidateRiskDecision | None = None
    passed_checks: int = Field(ge=0)
    failed_checks: int = Field(ge=0)
    compatibility_fraction: Decimal | None = Field(default=None, ge=0, le=1)
    failed_check_names: tuple[CandidateRiskCheckName, ...]
    checks: tuple[CandidateRiskCheck, ...]
    not_evaluated_reason: CandidateReplaySkipReason | None = None

    @model_validator(mode="after")
    def validate_compatibility(self) -> Self:
        if self.status is CandidateRiskCompatibilityStatus.NOT_EVALUATED:
            if self.decision is not None or self.compatibility_fraction is not None:
                raise ValueError("unevaluated risk compatibility cannot contain an outcome")
            if self.passed_checks != 0 or self.failed_checks != 0 or self.checks:
                raise ValueError("unevaluated risk compatibility cannot contain checks")
            if self.failed_check_names:
                raise ValueError("unevaluated risk compatibility cannot contain failed checks")
            if self.not_evaluated_reason is None:
                raise ValueError("unevaluated risk compatibility requires a reason")
            return self

        if self.not_evaluated_reason is not None:
            raise ValueError("evaluated risk compatibility cannot contain a skip reason")
        if self.decision is None or not self.checks:
            raise ValueError("evaluated risk compatibility requires a decision and checks")

        check_names = tuple(check.name for check in self.checks)
        if check_names != tuple(CandidateRiskCheckName):
            raise ValueError("evaluated risk compatibility checks must be complete and ordered")

        expected_passed = sum(check.passed for check in self.checks)
        expected_failed = len(self.checks) - expected_passed
        if self.passed_checks != expected_passed or self.failed_checks != expected_failed:
            raise ValueError("risk compatibility check counts are inconsistent")

        expected_failed_names = tuple(check.name for check in self.checks if not check.passed)
        if self.failed_check_names != expected_failed_names:
            raise ValueError("risk compatibility failed checks are inconsistent")

        expected_fraction = _quantize_score(Decimal(expected_passed) / Decimal(len(self.checks)))
        if self.compatibility_fraction != expected_fraction:
            raise ValueError("risk compatibility fraction is inconsistent")

        expected_decision = (
            CandidateRiskDecision.APPROVED
            if expected_failed == 0
            else CandidateRiskDecision.REJECTED
        )
        if self.decision is not expected_decision:
            raise ValueError("risk compatibility decision is inconsistent")
        return self


class CandidateDecisionEvidence(BaseModel):
    """Complete explainable ranking and risk evidence for one journal occurrence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version: Literal["candidate-decision-evidence-v1"] = "candidate-decision-evidence-v1"
    candidate_id: str = Field(pattern=r"^candidate-[a-f0-9]{16}$")
    ranking: CandidateRankingBreakdown
    risk_compatibility: CandidateRiskCompatibilityBreakdown

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.ranking.candidate_id != self.candidate_id:
            raise ValueError("candidate decision evidence identity is inconsistent")
        return self


class CandidateDecisionEvidenceBuilder:
    """Reconstruct stable explanations from immutable lifecycle evidence."""

    @staticmethod
    def build(
        *,
        entry: CandidateRankingEntry,
        peer_entries: Sequence[CandidateRankingEntry],
        risk_assessment: CandidateRiskAssessment | None = None,
        not_evaluated_reason: CandidateReplaySkipReason | None = None,
    ) -> CandidateDecisionEvidence:
        peers = tuple(peer_entries)
        peer_ids = tuple(item.candidate.candidate_id for item in peers)
        if len(peer_ids) != len(set(peer_ids)):
            raise ValueError("candidate decision evidence peers must be unique")
        if entry.candidate.candidate_id not in peer_ids:
            raise ValueError("candidate decision evidence entry must be present in peers")
        if (risk_assessment is None) == (not_evaluated_reason is None):
            raise ValueError("candidate decision evidence requires one risk evidence source")
        if risk_assessment is not None and risk_assessment.ranking_entry != entry:
            raise ValueError("candidate decision evidence risk assessment does not match ranking")

        return CandidateDecisionEvidence(
            candidate_id=entry.candidate.candidate_id,
            ranking=CandidateDecisionEvidenceBuilder._ranking_breakdown(
                entry=entry,
                peers=peers,
            ),
            risk_compatibility=CandidateDecisionEvidenceBuilder._risk_compatibility(
                assessment=risk_assessment,
                not_evaluated_reason=not_evaluated_reason,
            ),
        )

    @staticmethod
    def _ranking_breakdown(
        *,
        entry: CandidateRankingEntry,
        peers: tuple[CandidateRankingEntry, ...],
    ) -> CandidateRankingBreakdown:
        components_by_name = {component.name: component for component in entry.components}
        public_names = (
            (
                CandidateRankingEvidenceComponentName.CONFIDENCE,
                CandidateRankingComponentName.CONFIDENCE,
            ),
            (
                CandidateRankingEvidenceComponentName.SIGNAL_QUALITY,
                CandidateRankingComponentName.SIGNAL_STRENGTH,
            ),
            (
                CandidateRankingEvidenceComponentName.FRESHNESS,
                CandidateRankingComponentName.FRESHNESS,
            ),
        )
        components = tuple(
            CandidateRankingEvidenceComponent(
                name=public_name,
                source_component=source_name,
                raw_value=components_by_name[source_name].raw_value,
                weight=components_by_name[source_name].weight,
                weighted_value=components_by_name[source_name].weighted_value,
            )
            for public_name, source_name in public_names
        )

        tied_candidate_ids = tuple(
            sorted(
                item.candidate.candidate_id
                for item in peers
                if item.total_score == entry.total_score
            )
        )
        tie_applied = len(tied_candidate_ids) > 1
        tie_break = CandidateRankingTieBreakEvidence(
            applied=tie_applied,
            tied_candidate_ids=tied_candidate_ids if tie_applied else (),
            position_within_tie=(
                tied_candidate_ids.index(entry.candidate.candidate_id) + 1 if tie_applied else None
            ),
        )

        return CandidateRankingBreakdown(
            candidate_id=entry.candidate.candidate_id,
            rank=entry.rank,
            total_score=entry.total_score,
            components=components,
            tie_break=tie_break,
        )

    @staticmethod
    def _risk_compatibility(
        *,
        assessment: CandidateRiskAssessment | None,
        not_evaluated_reason: CandidateReplaySkipReason | None,
    ) -> CandidateRiskCompatibilityBreakdown:
        if assessment is None:
            if not_evaluated_reason is None:
                raise ValueError("unevaluated risk compatibility requires a reason")
            return CandidateRiskCompatibilityBreakdown(
                status=CandidateRiskCompatibilityStatus.NOT_EVALUATED,
                passed_checks=0,
                failed_checks=0,
                failed_check_names=(),
                checks=(),
                not_evaluated_reason=not_evaluated_reason,
            )

        passed_checks = sum(check.passed for check in assessment.checks)
        failed_checks = len(assessment.checks) - passed_checks
        return CandidateRiskCompatibilityBreakdown(
            status=CandidateRiskCompatibilityStatus.EVALUATED,
            decision=assessment.decision,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            compatibility_fraction=_quantize_score(
                Decimal(passed_checks) / Decimal(len(assessment.checks))
            ),
            failed_check_names=tuple(check.name for check in assessment.checks if not check.passed),
            checks=assessment.checks,
        )


def _quantize_score(value: Decimal) -> Decimal:
    return value.quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)
