from trd_bot.research import (
    CandidateRiskAssessment,
    CandidateRiskCheck,
    CandidateRiskCheckName,
    CandidateRiskDecision,
    CandidateRiskEvaluator,
    CandidateRiskPolicy,
    CandidateSimulationResult,
    CandidateSimulationRunner,
)


def test_risk_and_simulation_contracts_are_public_research_api() -> None:
    exported_symbols = (
        CandidateRiskAssessment,
        CandidateRiskCheck,
        CandidateRiskCheckName,
        CandidateRiskDecision,
        CandidateRiskEvaluator,
        CandidateRiskPolicy,
        CandidateSimulationResult,
        CandidateSimulationRunner,
    )

    assert all(symbol is not None for symbol in exported_symbols)
