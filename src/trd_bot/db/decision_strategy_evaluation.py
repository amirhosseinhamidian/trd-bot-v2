from sqlalchemy.orm import Session

from trd_bot.db.decision_intelligence_repositories import (
    SqlAlchemyDecisionIntelligenceStore,
)
from trd_bot.db.repositories import SqlAlchemyDatasetRepository
from trd_bot.decision_intelligence import (
    StrategyContextCompatibilityPolicyV1,
    StrategyEvaluationIntegrityError,
    StrategyEvaluationRecord,
    evaluate_strategy_intent,
    strategy_context_compatibility_policy_v1,
)
from trd_bot.strategies import StrategyRegistry, build_default_strategy_registry


class SqlAlchemyContextAwareStrategyEvaluator:
    """Evaluate persisted intent lineage and stage immutable strategy evidence."""

    def __init__(
        self,
        session: Session,
        *,
        registry: StrategyRegistry | None = None,
        compatibility_policy: StrategyContextCompatibilityPolicyV1 | None = None,
    ) -> None:
        self._store = SqlAlchemyDecisionIntelligenceStore(session)
        self._datasets = SqlAlchemyDatasetRepository(session)
        self._registry = registry or build_default_strategy_registry()
        self._compatibility_policy = (
            compatibility_policy or strategy_context_compatibility_policy_v1()
        )

    def evaluate(self, evaluation_id: str) -> tuple[StrategyEvaluationRecord, bool]:
        existing = self._store.get_strategy_evaluation(evaluation_id)
        if existing is not None:
            if (
                existing.compatibility_policy_checksum
                != self._compatibility_policy.definition_checksum
            ):
                raise StrategyEvaluationIntegrityError(
                    "strategy evaluation already uses another compatibility policy"
                )
            return existing, False

        intent = self._store.get_evaluation_intent(evaluation_id)
        if intent is None:
            raise StrategyEvaluationIntegrityError("strategy evaluation intent does not exist")
        dataset = self._datasets.get(intent.dataset.dataset_id)
        if dataset is None:
            raise StrategyEvaluationIntegrityError("strategy evaluation dataset does not exist")

        record = evaluate_strategy_intent(
            intent=intent,
            dataset=dataset,
            registry=self._registry,
            compatibility_policy=self._compatibility_policy,
        )
        self._store.stage_outcome(record.outcome)
        return self._store.stage_strategy_evaluation(record)
