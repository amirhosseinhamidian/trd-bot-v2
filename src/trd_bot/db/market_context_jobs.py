from collections.abc import Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.market_context_alignment import SqlAlchemyMarketContextAssembler
from trd_bot.db.market_context_features import SqlAlchemyMarketContextFeatureCalculator
from trd_bot.db.market_context_regimes import SqlAlchemyMarketRegimeEvaluator
from trd_bot.domain.market_data import TradingPair
from trd_bot.market_context import (
    MarketContextAlignmentStatus,
    MarketContextEvaluationCancelled,
    MarketContextEvaluationEnqueueResult,
    MarketContextEvaluationError,
    MarketContextEvaluationJobPayload,
    MarketContextInputsNotReadyError,
    MarketRegimeAssessment,
    build_market_context_evaluation_job,
    market_context_feature_set_v1,
    validate_market_context_evaluation_enqueue,
    validate_market_context_evaluation_result,
)


class SqlAlchemyMarketContextEvaluationEnqueuer:
    """Create one idempotent durable evaluation request."""

    def __init__(self, session: Session) -> None:
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def enqueue(
        self,
        *,
        source: str,
        pair: TradingPair,
        as_of: datetime,
        requested_at: datetime,
    ) -> MarketContextEvaluationEnqueueResult:
        job = build_market_context_evaluation_job(
            source=source,
            pair=pair,
            as_of=as_of,
            requested_at=requested_at,
        )
        validate_market_context_evaluation_enqueue(job)
        stored, created = self._jobs.enqueue(job)
        return MarketContextEvaluationEnqueueResult(job=stored, created=created)


class SqlAlchemyMarketContextEvaluationRunner:
    """Atomically align, calculate and classify one market-context boundary."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def run(
        self,
        payload: MarketContextEvaluationJobPayload,
        *,
        cancellation_requested: Callable[[], bool] = lambda: False,
    ) -> MarketRegimeAssessment:
        if cancellation_requested():
            raise MarketContextEvaluationCancelled

        try:
            with self._session_factory.begin() as session:
                alignment = SqlAlchemyMarketContextAssembler(session).assemble_and_stage(
                    source=payload.source,
                    pair=payload.pair,
                    as_of=payload.as_of,
                    feature_set=market_context_feature_set_v1(),
                    aligned_at=payload.requested_at,
                )
                if alignment.status is not MarketContextAlignmentStatus.READY:
                    raise MarketContextInputsNotReadyError
                if alignment.manifest is None:  # pragma: no cover - contract protected
                    raise RuntimeError("ready market-context alignment has no manifest")
                if cancellation_requested():
                    raise MarketContextEvaluationCancelled

                SqlAlchemyMarketContextFeatureCalculator(session).calculate_and_stage(
                    manifest_id=alignment.manifest.manifest_id,
                )
                if cancellation_requested():
                    raise MarketContextEvaluationCancelled

                assessment, _ = SqlAlchemyMarketRegimeEvaluator(session).evaluate_and_stage(
                    manifest_id=alignment.manifest.manifest_id,
                )
                validate_market_context_evaluation_result(
                    payload=payload,
                    assessment=assessment,
                )
                return assessment
        except (
            MarketContextEvaluationCancelled,
            MarketContextEvaluationError,
            SQLAlchemyError,
        ):
            raise
        except ValueError as error:
            raise MarketContextEvaluationError(
                code="market_context_evaluation_rejected",
                message="Market-context evaluation failed deterministic validation.",
                retryable=False,
            ) from error
