from sqlalchemy.orm import Session

from trd_bot.db.decision_intelligence_repositories import (
    SqlAlchemyDecisionIntelligenceStore,
)
from trd_bot.db.repositories import SqlAlchemyDatasetRepository
from trd_bot.decision_intelligence import (
    DecisionCandidateIntegrityError,
    DecisionCandidatePolicyV1,
    DecisionCandidateRankingRecord,
    DecisionDisposition,
    build_decision_candidate_ranking,
    decision_candidate_policy_v1,
)


class SqlAlchemyDecisionCandidateRanker:
    """Build, rank, and stage candidate evidence in a caller-owned transaction."""

    def __init__(
        self,
        session: Session,
        *,
        policy: DecisionCandidatePolicyV1 | None = None,
    ) -> None:
        self._store = SqlAlchemyDecisionIntelligenceStore(session)
        self._datasets = SqlAlchemyDatasetRepository(session)
        self._policy = policy or decision_candidate_policy_v1()

    def rank(self, evaluation_id: str) -> tuple[DecisionCandidateRankingRecord, bool]:
        existing = self._store.get_candidate_ranking(evaluation_id)
        if existing is not None:
            if existing.policy_checksum != self._policy.definition_checksum:
                raise DecisionCandidateIntegrityError(
                    "candidate ranking already uses another policy"
                )
            return existing, False

        intent = self._store.get_evaluation_intent(evaluation_id)
        if intent is None:
            raise DecisionCandidateIntegrityError("candidate ranking intent does not exist")
        strategy_evaluation = self._store.get_strategy_evaluation(evaluation_id)
        if strategy_evaluation is None:
            raise DecisionCandidateIntegrityError(
                "candidate ranking strategy evidence does not exist"
            )
        if strategy_evaluation.outcome.disposition is not DecisionDisposition.ACCEPTED:
            raise DecisionCandidateIntegrityError(
                "candidate ranking requires accepted strategy evidence"
            )
        dataset = self._datasets.get(intent.dataset.dataset_id)
        if dataset is None:
            raise DecisionCandidateIntegrityError("candidate ranking dataset does not exist")

        record = build_decision_candidate_ranking(
            intent=intent,
            strategy_evaluation=strategy_evaluation,
            dataset=dataset,
            policy=self._policy,
        )
        self._store.stage_outcome(record.outcome)
        return self._store.stage_candidate_ranking(record)
