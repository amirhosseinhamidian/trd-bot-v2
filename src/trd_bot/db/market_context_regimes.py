from sqlalchemy.orm import Session

from trd_bot.db.market_context_repositories import SqlAlchemyMarketContextStore
from trd_bot.market_context import (
    MARKET_CONTEXT_FEATURE_SET_V1_VERSION,
    MARKET_REGIME_ALGORITHM_V1,
    MarketRegimeAssessment,
    evaluate_market_regime_v1,
)


class SqlAlchemyMarketRegimeEvaluator:
    """Evaluate and stage one deterministic regime without owning the transaction."""

    def __init__(self, session: Session) -> None:
        self._store = SqlAlchemyMarketContextStore(session)

    def evaluate_and_stage(
        self,
        *,
        manifest_id: str,
    ) -> tuple[MarketRegimeAssessment, bool]:
        snapshot = self._store.get_feature_snapshot_for_manifest(
            manifest_id=manifest_id,
            feature_set_version=MARKET_CONTEXT_FEATURE_SET_V1_VERSION,
        )
        if snapshot is None:
            raise ValueError("canonical market-context feature snapshot does not exist")

        existing = self._store.get_assessment_for_manifest(
            manifest_id=manifest_id,
            feature_set_version=MARKET_CONTEXT_FEATURE_SET_V1_VERSION,
            algorithm_version=MARKET_REGIME_ALGORITHM_V1,
        )
        assessment = evaluate_market_regime_v1(snapshot)
        if existing is not None:
            if existing != assessment:
                raise ValueError("persisted market-regime assessment is not reproducible")
            return existing, False
        return self._store.stage_assessment(assessment)
