from datetime import datetime
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.api.dependencies import get_decision_intelligence_store
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.db import SqlAlchemyDecisionIntelligenceStore
from trd_bot.decision_intelligence import (
    DecisionCandidateRankingRecord,
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionMode,
    DecisionPortfolioIntelligenceRecord,
    DecisionReasonCode,
    DecisionRiskGateRecord,
    DecisionStage,
    DecisionStageOutcome,
    PortfolioRecommendation,
    StrategyEvaluationRecord,
)
from trd_bot.domain.market_data import Timeframe, TradingPair

router = APIRouter(
    prefix="/decision-intelligence/evaluations",
    tags=["Decision Intelligence evidence"],
)

DecisionStoreDependency = Annotated[
    SqlAlchemyDecisionIntelligenceStore,
    Depends(get_decision_intelligence_store),
]


class DecisionEvaluationFilters(BaseModel):
    """Optional lineage scope for one read-only Decision Intelligence projection."""

    model_config = ConfigDict(extra="forbid")

    strategy_name: str | None = Field(default=None, min_length=1, max_length=100)
    strategy_version: str | None = Field(default=None, min_length=1, max_length=50)
    signal_id: str | None = Field(default=None, pattern=r"^signal-[a-f0-9]{16}$")
    candidate_id: str | None = Field(
        default=None,
        pattern=r"^decision-candidate-[a-f0-9]{16}$",
    )
    portfolio_id: str | None = Field(default=None, pattern=r"^portfolio-[a-f0-9]{16}$")
    stage: DecisionStage | None = None
    mode: DecisionMode | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if self.strategy_version is not None and self.strategy_name is None:
            raise ValueError("strategy_version requires strategy_name")
        identities = (
            self.signal_id is not None,
            self.candidate_id is not None,
            self.portfolio_id is not None,
        )
        if sum(identities) > 1:
            raise ValueError("only one signal, candidate, or portfolio identity may be filtered")
        return self


DecisionEvaluationFiltersQuery = Annotated[DecisionEvaluationFilters, Query()]


class DecisionEvaluationListParams(DecisionEvaluationFilters):
    """Lineage filters plus bounded collection pagination."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


DecisionEvaluationListParamsQuery = Annotated[DecisionEvaluationListParams, Query()]
DecisionEvaluationIdPath = Annotated[
    str,
    Path(pattern=r"^decision-evaluation-[a-f0-9]{16}$"),
]


class DecisionEvaluationSummary(BaseModel):
    """Small product-facing summary of one immutable offline evaluation."""

    model_config = ConfigDict(frozen=True)

    evaluation_id: str
    mode: DecisionMode
    requested_at: datetime
    dataset_id: str
    pair: TradingPair
    timeframe: Timeframe
    strategy_name: str
    strategy_version: str
    market_context_assessment_id: str
    latest_stage: DecisionStage | None
    disposition: DecisionDisposition | None
    reason_codes: tuple[DecisionReasonCode, ...]
    completed_stage_count: int = Field(ge=0, le=4)
    signal_count: int = Field(ge=0)
    top_candidate_id: str | None
    risk_decision: Literal["approved", "rejected"] | None
    portfolio_recommendation: PortfolioRecommendation | None
    portfolio_id: str | None
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False


class DecisionEvaluationDetail(BaseModel):
    """Complete persisted evidence envelope; missing stages remain explicit nulls."""

    model_config = ConfigDict(frozen=True)

    summary: DecisionEvaluationSummary
    intent: DecisionEvaluationIntent
    outcomes: tuple[DecisionStageOutcome, ...]
    strategy_evaluation: StrategyEvaluationRecord | None
    candidate_ranking: DecisionCandidateRankingRecord | None
    risk_gate: DecisionRiskGateRecord | None
    portfolio_intelligence: DecisionPortfolioIntelligenceRecord | None


def _build_detail(
    intent: DecisionEvaluationIntent,
    store: SqlAlchemyDecisionIntelligenceStore,
) -> DecisionEvaluationDetail:
    strategy = store.get_strategy_evaluation(intent.evaluation_id)
    candidates = store.get_candidate_ranking(intent.evaluation_id)
    risk = store.get_risk_gate(intent.evaluation_id)
    portfolio = store.get_portfolio_intelligence(intent.evaluation_id)
    outcomes = store.list_stage_outcomes(intent.evaluation_id)
    latest = outcomes[-1] if outcomes else None
    portfolio_id = (
        None
        if portfolio is None or portfolio.analysis is None
        else portfolio.analysis.snapshot.portfolio_id
    )
    summary = DecisionEvaluationSummary(
        evaluation_id=intent.evaluation_id,
        mode=intent.mode,
        requested_at=intent.requested_at,
        dataset_id=intent.dataset.dataset_id,
        pair=intent.dataset.pair,
        timeframe=intent.dataset.timeframe,
        strategy_name=intent.strategy.strategy_name,
        strategy_version=intent.strategy.strategy_version,
        market_context_assessment_id=intent.market_context.assessment_id,
        latest_stage=None if latest is None else latest.stage,
        disposition=None if latest is None else latest.disposition,
        reason_codes=() if latest is None else latest.reason_codes,
        completed_stage_count=len(outcomes),
        signal_count=0 if strategy is None else strategy.signal_count,
        top_candidate_id=None if candidates is None else candidates.top_candidate_id,
        risk_decision=None if risk is None else risk.assessment.decision.value,
        portfolio_recommendation=(None if portfolio is None else portfolio.recommendation),
        portfolio_id=portfolio_id,
    )
    return DecisionEvaluationDetail(
        summary=summary,
        intent=intent,
        outcomes=outcomes,
        strategy_evaluation=strategy,
        candidate_ranking=candidates,
        risk_gate=risk,
        portfolio_intelligence=portfolio,
    )


def _matches(
    detail: DecisionEvaluationDetail,
    filters: DecisionEvaluationFilters,
) -> bool:
    summary = detail.summary
    if filters.mode is not None and summary.mode is not filters.mode:
        return False
    if filters.stage is not None and all(
        outcome.stage is not filters.stage for outcome in detail.outcomes
    ):
        return False
    if filters.signal_id is not None:
        strategy = detail.strategy_evaluation
        if strategy is None or all(
            signal.signal_id != filters.signal_id for signal in strategy.signals
        ):
            return False
    if filters.candidate_id is not None:
        candidates = detail.candidate_ranking
        if candidates is None or all(
            entry.candidate.candidate_id != filters.candidate_id for entry in candidates.entries
        ):
            return False
    return filters.portfolio_id is None or summary.portfolio_id == filters.portfolio_id


def _matching_details(
    store: SqlAlchemyDecisionIntelligenceStore,
    filters: DecisionEvaluationFilters,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[DecisionEvaluationDetail, ...]:
    intents = store.list_evaluation_intents(
        strategy_name=filters.strategy_name,
        strategy_version=filters.strategy_version,
        mode=filters.mode,
        stage=filters.stage,
        limit=limit,
        offset=offset,
    )
    return tuple(
        detail for intent in intents if _matches((detail := _build_detail(intent, store)), filters)
    )


@router.get("", response_model=Page[DecisionEvaluationSummary])
def list_decision_evaluations(
    store: DecisionStoreDependency,
    params: DecisionEvaluationListParamsQuery,
) -> Page[DecisionEvaluationSummary]:
    """List persisted Decision Intelligence evidence without creating or running work."""

    pagination = PaginationParams(limit=params.limit, offset=params.offset)
    requires_lineage_scan = any(
        value is not None for value in (params.signal_id, params.candidate_id, params.portfolio_id)
    )
    if requires_lineage_scan:
        matching = _matching_details(store, params)
        total = len(matching)
        selected = matching[pagination.offset : pagination.offset + pagination.limit]
    else:
        total = store.count_evaluation_intents(
            strategy_name=params.strategy_name,
            strategy_version=params.strategy_version,
            mode=params.mode,
            stage=params.stage,
        )
        selected = _matching_details(
            store,
            params,
            limit=pagination.limit,
            offset=pagination.offset,
        )
    return build_page(
        tuple(item.summary for item in selected),
        total=total,
        pagination=pagination,
    )


@router.get("/latest", response_model=DecisionEvaluationDetail)
def get_latest_decision_evaluation(
    store: DecisionStoreDependency,
    filters: DecisionEvaluationFiltersQuery,
) -> DecisionEvaluationDetail:
    """Return the newest persisted evaluation matching one product-page lineage scope."""

    requires_lineage_scan = any(
        value is not None
        for value in (filters.signal_id, filters.candidate_id, filters.portfolio_id)
    )
    matching = _matching_details(store, filters, limit=None if requires_lineage_scan else 1)
    if not matching:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="decision evaluation evidence not found",
        )
    return matching[0]


@router.get("/{evaluation_id}", response_model=DecisionEvaluationDetail)
def get_decision_evaluation(
    evaluation_id: DecisionEvaluationIdPath,
    store: DecisionStoreDependency,
) -> DecisionEvaluationDetail:
    """Return complete immutable evidence for one exact evaluation."""

    intent = store.get_evaluation_intent(evaluation_id)
    if intent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="decision evaluation evidence not found",
        )
    return _build_detail(intent, store)
