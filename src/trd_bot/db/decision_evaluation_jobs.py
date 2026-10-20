from collections.abc import Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.decision_candidate_ranking import SqlAlchemyDecisionCandidateRanker
from trd_bot.db.decision_intelligence_repositories import (
    SqlAlchemyDecisionIntelligenceStore,
)
from trd_bot.db.decision_strategy_evaluation import (
    SqlAlchemyContextAwareStrategyEvaluator,
)
from trd_bot.decision_intelligence import (
    DecisionCandidateIntegrityError,
    DecisionDisposition,
    DecisionEvaluationEnqueueResult,
    DecisionEvaluationIntentNotFoundError,
    DecisionEvaluationJobCancelled,
    DecisionEvaluationJobError,
    DecisionEvaluationJobPayload,
    StrategyEvaluationIntegrityError,
    StrategyEvaluationRecord,
    build_decision_evaluation_job,
    validate_decision_evaluation_enqueue,
    validate_decision_evaluation_payload_intent,
    validate_decision_evaluation_result,
)


class SqlAlchemyDecisionEvaluationEnqueuer:
    """Create one idempotent durable job for a persisted decision intent."""

    def __init__(self, session: Session) -> None:
        self._store = SqlAlchemyDecisionIntelligenceStore(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def enqueue(
        self,
        *,
        evaluation_id: str,
        requested_at: datetime,
    ) -> DecisionEvaluationEnqueueResult:
        intent = self._store.get_evaluation_intent(evaluation_id)
        if intent is None:
            raise DecisionEvaluationIntentNotFoundError
        job = build_decision_evaluation_job(
            intent=intent,
            requested_at=requested_at,
        )
        validate_decision_evaluation_enqueue(job, intent=intent)
        stored, created = self._jobs.enqueue(job)
        return DecisionEvaluationEnqueueResult(job=stored, created=created)


class SqlAlchemyDecisionEvaluationRunner:
    """Atomically evaluate one durable decision job and persist its evidence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def run(
        self,
        payload: DecisionEvaluationJobPayload,
        *,
        cancellation_requested: Callable[[], bool] = lambda: False,
    ) -> StrategyEvaluationRecord:
        if cancellation_requested():
            raise DecisionEvaluationJobCancelled

        try:
            with self._session_factory.begin() as session:
                store = SqlAlchemyDecisionIntelligenceStore(session)
                intent = store.get_evaluation_intent(payload.evaluation_id)
                if intent is None:
                    raise DecisionEvaluationIntentNotFoundError
                validate_decision_evaluation_payload_intent(
                    payload=payload,
                    intent=intent,
                )
                if cancellation_requested():
                    raise DecisionEvaluationJobCancelled

                record, _ = SqlAlchemyContextAwareStrategyEvaluator(session).evaluate(
                    payload.evaluation_id
                )
                validate_decision_evaluation_result(
                    payload=payload,
                    intent=intent,
                    record=record,
                )
                if cancellation_requested():
                    raise DecisionEvaluationJobCancelled
                if record.outcome.disposition is DecisionDisposition.ACCEPTED:
                    SqlAlchemyDecisionCandidateRanker(session).rank(payload.evaluation_id)
                    if cancellation_requested():
                        raise DecisionEvaluationJobCancelled
                return record
        except (
            DecisionEvaluationJobCancelled,
            DecisionEvaluationJobError,
            SQLAlchemyError,
        ):
            raise
        except (DecisionCandidateIntegrityError, StrategyEvaluationIntegrityError) as error:
            raise DecisionEvaluationJobError(
                code="decision_evaluation_integrity_error",
                message="Decision evaluation failed persisted-lineage validation.",
                retryable=False,
            ) from error
        except ValueError as error:
            raise DecisionEvaluationJobError(
                code="decision_evaluation_rejected",
                message="Decision evaluation failed deterministic validation.",
                retryable=False,
            ) from error
