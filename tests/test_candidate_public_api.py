from trd_bot.research import (
    CandidateAction,
    CandidateBuilder,
    CandidateEntryZone,
    CandidateEvidence,
    CandidateRanker,
    CandidateRankingComponent,
    CandidateRankingComponentName,
    CandidateRankingEntry,
    CandidateRankingPolicy,
    CandidateRankingResult,
    CandidateStatus,
    CandidateTarget,
    CandidateTradePlan,
    ResearchCandidate,
    build_candidate_id,
    normalize_candidate_timestamp,
)


def test_candidate_domain_is_available_from_research_public_api() -> None:
    exported_symbols = (
        CandidateAction,
        CandidateBuilder,
        CandidateEntryZone,
        CandidateEvidence,
        CandidateRanker,
        CandidateRankingComponent,
        CandidateRankingComponentName,
        CandidateRankingEntry,
        CandidateRankingPolicy,
        CandidateRankingResult,
        CandidateStatus,
        CandidateTarget,
        CandidateTradePlan,
        ResearchCandidate,
        build_candidate_id,
        normalize_candidate_timestamp,
    )

    assert all(symbol is not None for symbol in exported_symbols)
