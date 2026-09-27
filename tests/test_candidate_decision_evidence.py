from decimal import Decimal

from tests.test_candidate_ranking import RANKED_AT, create_candidate
from tests.test_candidate_risk_policy import portfolio
from trd_bot.research.candidate_decision_evidence import (
    CandidateDecisionEvidenceBuilder,
    CandidateRankingEvidenceComponentName,
    CandidateRiskCompatibilityStatus,
)
from trd_bot.research.candidate_ranking import CandidateRanker, CandidateRankingEntry
from trd_bot.research.dataset_replay_orchestration import CandidateReplaySkipReason
from trd_bot.research.risk_policy import (
    CandidateRiskCheckName,
    CandidateRiskDecision,
    CandidateRiskEvaluator,
)


def tied_entries() -> tuple[CandidateRankingEntry, ...]:
    first = create_candidate(
        experiment_id="experiment-eeeeeeeeeeeeeeee",
        confidence=Decimal("0.80"),
        signal_score=Decimal("0.70"),
    )
    second = create_candidate(
        experiment_id="experiment-ffffffffffffffff",
        confidence=Decimal("0.80"),
        signal_score=Decimal("0.70"),
    )
    return CandidateRanker().rank(candidates=(second, first), at=RANKED_AT).entries


def test_decision_evidence_reconciles_score_tie_break_and_risk_rejection() -> None:
    entries = tied_entries()
    entry = entries[0]
    assessment = CandidateRiskEvaluator().evaluate(
        entry=entry,
        portfolio=portfolio(),
        at=RANKED_AT,
    )

    evidence = CandidateDecisionEvidenceBuilder.build(
        entry=entry,
        peer_entries=entries,
        risk_assessment=assessment,
    )

    assert evidence.evidence_version == "candidate-decision-evidence-v1"
    assert evidence.ranking.score_version == "candidate-ranking-score-v1"
    assert tuple(component.name for component in evidence.ranking.components) == (
        CandidateRankingEvidenceComponentName.CONFIDENCE,
        CandidateRankingEvidenceComponentName.SIGNAL_QUALITY,
        CandidateRankingEvidenceComponentName.FRESHNESS,
    )
    assert (
        sum(
            (component.weighted_value for component in evidence.ranking.components),
            start=Decimal("0"),
        )
        == evidence.ranking.total_score
    )
    assert evidence.ranking.tie_break.applied is True
    assert evidence.ranking.tie_break.tied_candidate_ids == tuple(
        sorted(item.candidate.candidate_id for item in entries)
    )
    assert evidence.ranking.tie_break.position_within_tie == 1

    risk = evidence.risk_compatibility
    assert risk.status is CandidateRiskCompatibilityStatus.EVALUATED
    assert risk.affects_ranking_score is False
    assert risk.decision is CandidateRiskDecision.REJECTED
    assert risk.compatibility_fraction == Decimal("0.875000")
    assert risk.failed_check_names == (CandidateRiskCheckName.REWARD_RISK,)


def test_skipped_candidate_has_explicit_unevaluated_risk_compatibility() -> None:
    entries = tied_entries()
    entry = entries[1]

    evidence = CandidateDecisionEvidenceBuilder.build(
        entry=entry,
        peer_entries=entries,
        not_evaluated_reason=CandidateReplaySkipReason.POSITION_OPENED,
    )

    risk = evidence.risk_compatibility
    assert risk.status is CandidateRiskCompatibilityStatus.NOT_EVALUATED
    assert risk.decision is None
    assert risk.compatibility_fraction is None
    assert risk.checks == ()
    assert risk.not_evaluated_reason is CandidateReplaySkipReason.POSITION_OPENED
