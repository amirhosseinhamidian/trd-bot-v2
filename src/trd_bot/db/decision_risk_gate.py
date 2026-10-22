from sqlalchemy.orm import Session

from trd_bot.db.decision_intelligence_repositories import (
    SqlAlchemyDecisionIntelligenceStore,
)
from trd_bot.decision_intelligence import (
    DecisionDisposition,
    DecisionRiskGateRecord,
    DecisionRiskIntegrityError,
    DecisionRiskPolicyV1,
    decision_risk_policy_v1,
    evaluate_decision_risk,
)


class SqlAlchemyDecisionRiskGate:
    """Evaluate and stage risk evidence in a caller-owned transaction."""

    def __init__(
        self,
        session: Session,
        *,
        policy: DecisionRiskPolicyV1 | None = None,
    ) -> None:
        self._store = SqlAlchemyDecisionIntelligenceStore(session)
        self._policy = policy or decision_risk_policy_v1()

    def evaluate(self, evaluation_id: str) -> tuple[DecisionRiskGateRecord, bool]:
        existing = self._store.get_risk_gate(evaluation_id)
        if existing is not None:
            if existing.policy_checksum != self._policy.definition_checksum:
                raise DecisionRiskIntegrityError("risk gate already uses another policy")
            return existing, False

        ranking = self._store.get_candidate_ranking(evaluation_id)
        if ranking is None:
            raise DecisionRiskIntegrityError("risk gate candidate ranking does not exist")
        if ranking.outcome.disposition is not DecisionDisposition.ACCEPTED:
            raise DecisionRiskIntegrityError("risk gate requires accepted candidate ranking")

        record = evaluate_decision_risk(
            ranking=ranking,
            policy=self._policy,
        )
        self._store.stage_outcome(record.outcome)
        return self._store.stage_risk_gate(record)
