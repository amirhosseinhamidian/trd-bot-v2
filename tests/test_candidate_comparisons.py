import pytest

from tests.test_candidate_decision_evidence import tied_entries
from tests.test_candidate_ranking import RANKED_AT
from tests.test_candidate_risk_policy import portfolio
from trd_bot.research.candidate_comparisons import CandidateComparator
from trd_bot.research.candidate_decision_evidence import CandidateDecisionEvidenceBuilder
from trd_bot.research.candidate_decision_lineage import (
    CandidateDecisionLineageBuilder,
    CandidateDecisionLineageKind,
    CandidateDecisionLineageStatus,
)
from trd_bot.research.candidate_projection import (
    CandidateJournalOccurrence,
    CandidateProjection,
)
from trd_bot.research.dataset_replay import CandidateReplayStatus
from trd_bot.research.risk_policy import CandidateRiskDecision, CandidateRiskEvaluator


def build_projections(
    journal_id: str = "journal-1111111111111111",
) -> tuple[CandidateProjection, ...]:
    entries = tied_entries()
    projections: list[CandidateProjection] = []

    for entry in entries:
        assessment = CandidateRiskEvaluator().evaluate(
            entry=entry,
            portfolio=portfolio(),
            at=RANKED_AT,
        )
        replay_status = (
            CandidateReplayStatus.RISK_REJECTED
            if assessment.decision is CandidateRiskDecision.REJECTED
            else CandidateReplayStatus.NO_FILL
        )
        occurrence = CandidateJournalOccurrence(
            journal_id=journal_id,
            recorded_at=RANKED_AT,
            evaluated_at=RANKED_AT,
            portfolio_id=assessment.portfolio_id,
            rank=entry.rank,
            ranking_score=entry.total_score,
            replay_status=replay_status,
            risk_decision=assessment.decision,
            selected=False,
            candidate=entry.candidate,
            decision_evidence=CandidateDecisionEvidenceBuilder.build(
                entry=entry,
                peer_entries=entries,
                risk_assessment=assessment,
            ),
        )
        projections.append(
            CandidateProjection(
                candidate=occurrence.candidate,
                latest=occurrence,
                history=(occurrence,),
            )
        )

    return tuple(projections)


def test_candidate_comparison_preserves_shared_cohort_rank_order_and_evidence() -> None:
    projections = tuple(reversed(build_projections()))

    result = CandidateComparator().compare(projections)

    assert result.journal_id == "journal-1111111111111111"
    assert result.compared_candidates == 2
    assert tuple(item.occurrence.rank for item in result.entries) == (1, 2)
    assert all(item.occurrence.decision_evidence is not None for item in result.entries)


def test_rejected_candidate_lineage_marks_position_and_exit_not_created() -> None:
    rejected = next(
        projection
        for projection in build_projections()
        if projection.latest.risk_decision is CandidateRiskDecision.REJECTED
    )

    lineage = CandidateDecisionLineageBuilder.build(rejected)
    nodes = {node.kind: node for node in lineage.nodes}

    assert nodes[CandidateDecisionLineageKind.RISK].outcome == "rejected"
    assert (
        nodes[CandidateDecisionLineageKind.POSITION].status
        is CandidateDecisionLineageStatus.NOT_CREATED
    )
    assert nodes[CandidateDecisionLineageKind.POSITION].reason == "risk_rejected"
    assert (
        nodes[CandidateDecisionLineageKind.EXIT].status
        is CandidateDecisionLineageStatus.NOT_CREATED
    )


def test_candidate_comparison_rejects_mixed_latest_journals() -> None:
    first = build_projections()[0]
    second = build_projections("journal-2222222222222222")[1]

    with pytest.raises(
        ValueError,
        match="candidates must use the same latest journal",
    ):
        CandidateComparator().compare((first, second))
