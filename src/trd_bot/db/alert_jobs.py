from collections.abc import Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.alerts import (
    AlertEvaluationEnqueueResult,
    AlertEvaluationJobCancelled,
    AlertEvaluationJobError,
    AlertEvaluationJobPayload,
    AlertEvaluationRecord,
    AlertRuleDefinition,
    AlertRuleReference,
    AlertRuleState,
    AlertRuleVersionNotFoundError,
    AlertSourceAssessmentNotFoundError,
    MarketContextAlertSourceReference,
    build_alert_evaluation_id,
    build_alert_evaluation_job,
    evaluate_alert,
    validate_alert_evaluation_enqueue,
    validate_alert_evaluation_result,
)
from trd_bot.db.alert_publication import SqlAlchemyAlertPublicationRepository
from trd_bot.db.alert_repositories import SqlAlchemyAlertStore
from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.market_context_repositories import SqlAlchemyMarketContextStore
from trd_bot.market_context import MarketContextProductView, MarketRegimeAssessment


class SqlAlchemyAlertEvaluationEnqueuer:
    """Create one idempotent durable request for a persisted rule/source pair."""

    def __init__(self, session: Session) -> None:
        self._alerts = SqlAlchemyAlertStore(session)
        self._context = SqlAlchemyMarketContextStore(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def enqueue(
        self,
        *,
        rule_id: str,
        rule_version: int,
        source_event_id: str,
        requested_at: datetime,
    ) -> AlertEvaluationEnqueueResult:
        rule = self._alerts.get_rule_definition(rule_id, rule_version)
        if rule is None:
            raise AlertRuleVersionNotFoundError
        assessment = self._context.get_assessment(source_event_id)
        if assessment is None:
            raise AlertSourceAssessmentNotFoundError

        return self._enqueue_loaded(
            rule=rule,
            assessment=assessment,
            requested_at=requested_at,
        )

    def enqueue_enabled_for_source(
        self,
        *,
        source_event_id: str,
        requested_at: datetime,
    ) -> tuple[AlertEvaluationEnqueueResult, ...]:
        assessment = self._context.get_assessment(source_event_id)
        if assessment is None:
            raise AlertSourceAssessmentNotFoundError
        rules = self._alerts.list_latest_rule_definitions(state=AlertRuleState.ENABLED)
        return tuple(
            self._enqueue_loaded(
                rule=rule,
                assessment=assessment,
                requested_at=requested_at,
            )
            for rule in rules
        )

    def _enqueue_loaded(
        self,
        *,
        rule: AlertRuleDefinition,
        assessment: MarketRegimeAssessment,
        requested_at: datetime,
    ) -> AlertEvaluationEnqueueResult:
        job = build_alert_evaluation_job(
            rule=rule,
            assessment=assessment,
            requested_at=requested_at,
        )
        validate_alert_evaluation_enqueue(job)
        stored, created = self._jobs.enqueue(job)
        return AlertEvaluationEnqueueResult(job=stored, created=created)


class SqlAlchemyAlertEvaluationRunner:
    """Evaluate and persist one alert outcome in a caller-independent transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def run(
        self,
        payload: AlertEvaluationJobPayload,
        *,
        cancellation_requested: Callable[[], bool] = lambda: False,
        executed_at: datetime | None = None,
    ) -> AlertEvaluationRecord:
        if cancellation_requested():
            raise AlertEvaluationJobCancelled

        try:
            with self._session_factory.begin() as session:
                alerts = SqlAlchemyAlertStore(session)
                rule = alerts.get_rule_definition(
                    payload.rule.rule_id,
                    payload.rule.rule_version,
                )
                if rule is None:
                    raise AlertRuleVersionNotFoundError
                if AlertRuleReference.from_definition(rule) != payload.rule:
                    raise ValueError("alert job rule does not match persisted definition")

                assessment = SqlAlchemyMarketContextStore(session).get_assessment(
                    payload.source.source_event_id
                )
                if assessment is None:
                    raise AlertSourceAssessmentNotFoundError
                source = MarketContextAlertSourceReference.from_market_context_view(
                    MarketContextProductView.from_assessment(
                        assessment,
                        evaluated_at=payload.requested_at,
                    )
                )
                if source != payload.source:
                    raise ValueError("alert job source does not match persisted assessment")
                if cancellation_requested():
                    raise AlertEvaluationJobCancelled

                evaluation_id = build_alert_evaluation_id(
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                    source_kind=source.source_kind,
                    source_event_id=source.source_event_id,
                )
                existing = alerts.get_evaluation(evaluation_id)
                if existing is not None:
                    return existing

                outcome = evaluate_alert(rule=rule, source=source)
                publication_decision = None
                if outcome.draft is not None:
                    publication = SqlAlchemyAlertPublicationRepository(session)
                    publication_decision = publication.evaluate(
                        evaluation_id=evaluation_id,
                        rule=rule,
                        source=source,
                        evaluated_at=executed_at or payload.requested_at,
                    )
                    if not publication_decision.allowed:
                        outcome = evaluate_alert(
                            rule=rule,
                            source=source,
                            publication_suppression_reasons=(
                                publication_decision.suppression_reasons
                            ),
                        )
                validate_alert_evaluation_result(payload=payload, outcome=outcome)
                if cancellation_requested():
                    raise AlertEvaluationJobCancelled

                evaluation, _ = alerts.stage_evaluation(
                    outcome.evaluation,
                    draft=outcome.draft,
                )
                if publication_decision is not None:
                    publication.stage_decision(
                        publication_decision,
                        evaluation=evaluation,
                    )
                return evaluation
        except (
            AlertEvaluationJobCancelled,
            AlertEvaluationJobError,
            SQLAlchemyError,
        ):
            raise
        except ValueError as error:
            raise AlertEvaluationJobError(
                code="alert_evaluation_rejected",
                message="Alert evaluation failed deterministic validation.",
                retryable=False,
            ) from error
