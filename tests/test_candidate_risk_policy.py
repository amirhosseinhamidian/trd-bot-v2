from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.backtesting import PositionSide
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode
from trd_bot.paper.portfolio import SimulatedPortfolio
from trd_bot.research.candidate_ranking import CandidateRanker, CandidateRankingEntry
from trd_bot.research.candidates import (
    CandidateBuilder,
    CandidateEntryZone,
    CandidateTarget,
    CandidateTradePlan,
)
from trd_bot.research.risk_policy import (
    CandidateRiskAssessment,
    CandidateRiskCheck,
    CandidateRiskCheckName,
    CandidateRiskDecision,
    CandidateRiskEvaluator,
    CandidateRiskPolicy,
)
from trd_bot.strategies import (
    SignalDirection,
    StrategyFeature,
    StrategySignal,
    build_signal_id,
)

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)

OPEN_TIME = datetime(2026, 8, 26, 10, tzinfo=UTC)
CLOSE_TIME = datetime(2026, 8, 26, 11, tzinfo=UTC)
PORTFOLIO_CREATED_AT = datetime(2026, 8, 26, 11, tzinfo=UTC)
CANDIDATE_CREATED_AT = datetime(2026, 8, 26, 11, 1, tzinfo=UTC)
RANKED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)
VALID_UNTIL = datetime(2026, 8, 26, 15, tzinfo=UTC)
EXPERIMENT_ID = "experiment-0123456789abcdef"


def create_signal() -> StrategySignal:
    signal_id = build_signal_id(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id="dataset-test",
        candle_close_time=CLOSE_TIME,
        direction=SignalDirection.LONG,
    )

    return StrategySignal(
        signal_id=signal_id,
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id="dataset-test",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        candle_open_time=OPEN_TIME,
        candle_close_time=CLOSE_TIME,
        generated_at=CLOSE_TIME,
        direction=SignalDirection.LONG,
        score=Decimal("0.80"),
        reason="EMA crossover produced directional evidence.",
        features=(
            StrategyFeature(
                name="fast_ema",
                value=Decimal("101.25"),
            ),
        ),
    )


def trade_plan(
    *,
    first_target: Decimal = Decimal("112"),
) -> CandidateTradePlan:
    return CandidateTradePlan(
        entry_zone=CandidateEntryZone(
            lower_price=Decimal("100"),
            upper_price=Decimal("102"),
        ),
        invalidation_price=Decimal("97"),
        targets=(
            CandidateTarget(
                label="target-1",
                price=first_target,
            ),
        ),
    )


def ranked_entry(
    *,
    confidence: Decimal = Decimal("0.80"),
    valid_until: datetime = VALID_UNTIL,
    first_target: Decimal = Decimal("112"),
) -> CandidateRankingEntry:
    candidate = CandidateBuilder.from_signal(
        signal=create_signal(),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=confidence,
        created_at=CANDIDATE_CREATED_AT,
        valid_until=valid_until,
        trade_plan=trade_plan(
            first_target=first_target,
        ),
    )

    return (
        CandidateRanker()
        .rank(
            candidates=(candidate,),
            at=RANKED_AT,
        )
        .entries[0]
    )


def portfolio(
    *,
    dataset_id: str = "dataset-test",
) -> SimulatedPortfolio:
    return SimulatedPortfolioLedger().create(
        mode=SimulationMode.PAPER,
        dataset_id=dataset_id,
        starting_cash=Decimal("10000"),
        created_at=PORTFOLIO_CREATED_AT,
    )


def check_by_name(
    assessment: CandidateRiskAssessment,
    name: CandidateRiskCheckName,
) -> CandidateRiskCheck:
    return next(check for check in assessment.checks if check.name is name)


def test_healthy_ranked_candidate_is_approved_for_simulation() -> None:
    assessment = CandidateRiskEvaluator().evaluate(
        entry=ranked_entry(),
        portfolio=portfolio(),
        at=RANKED_AT,
    )

    assert assessment.decision is CandidateRiskDecision.APPROVED
    assert assessment.risk_budget == Decimal("100.00000000")
    assert assessment.notional_budget == Decimal("2500.00000000")
    assert assessment.worst_case_entry_price == Decimal("102")
    assert assessment.unit_price_risk == Decimal("5")
    assert assessment.reward_risk_ratio == Decimal("2.000000")
    assert assessment.max_simulated_quantity == Decimal("20.00000000")
    assert all(check.passed for check in assessment.checks)


def test_risk_policy_rejects_candidate_that_expired_after_ranking() -> None:
    assessment = CandidateRiskEvaluator().evaluate(
        entry=ranked_entry(
            valid_until=RANKED_AT + timedelta(minutes=30),
        ),
        portfolio=portfolio(),
        at=RANKED_AT + timedelta(minutes=30),
    )

    assert assessment.decision is CandidateRiskDecision.REJECTED
    assert (
        check_by_name(
            assessment,
            CandidateRiskCheckName.CANDIDATE_SELECTABLE,
        ).passed
        is False
    )


def test_risk_policy_rejects_dataset_lineage_mismatch() -> None:
    assessment = CandidateRiskEvaluator().evaluate(
        entry=ranked_entry(),
        portfolio=portfolio(
            dataset_id="dataset-other",
        ),
        at=RANKED_AT,
    )

    assert assessment.decision is CandidateRiskDecision.REJECTED
    assert (
        check_by_name(
            assessment,
            CandidateRiskCheckName.DATASET_MATCH,
        ).passed
        is False
    )


def test_risk_policy_rejects_portfolio_with_open_position() -> None:
    ledger = SimulatedPortfolioLedger()
    active_portfolio = portfolio()
    with_position = ledger.open_position(
        active_portfolio,
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("101"),
        quantity=Decimal("1"),
        occurred_at=RANKED_AT - timedelta(minutes=15),
    )

    assessment = CandidateRiskEvaluator().evaluate(
        entry=ranked_entry(),
        portfolio=with_position,
        at=RANKED_AT,
    )

    assert assessment.decision is CandidateRiskDecision.REJECTED
    assert (
        check_by_name(
            assessment,
            CandidateRiskCheckName.PORTFOLIO_CAPACITY,
        ).passed
        is False
    )


def test_risk_policy_rejects_low_ranking_score() -> None:
    assessment = CandidateRiskEvaluator(
        policy=CandidateRiskPolicy(
            min_ranking_score=Decimal("0.90"),
        )
    ).evaluate(
        entry=ranked_entry(),
        portfolio=portfolio(),
        at=RANKED_AT,
    )

    assert assessment.decision is CandidateRiskDecision.REJECTED
    assert (
        check_by_name(
            assessment,
            CandidateRiskCheckName.RANKING_SCORE,
        ).passed
        is False
    )


def test_risk_policy_rejects_insufficient_reward_to_risk() -> None:
    assessment = CandidateRiskEvaluator().evaluate(
        entry=ranked_entry(
            first_target=Decimal("106"),
        ),
        portfolio=portfolio(),
        at=RANKED_AT,
    )

    assert assessment.reward_risk_ratio == Decimal("0.800000")
    assert assessment.decision is CandidateRiskDecision.REJECTED
    assert (
        check_by_name(
            assessment,
            CandidateRiskCheckName.REWARD_RISK,
        ).passed
        is False
    )


def test_notional_cap_can_limit_simulated_quantity() -> None:
    assessment = CandidateRiskEvaluator(
        policy=CandidateRiskPolicy(
            max_risk_fraction=Decimal("0.10"),
            max_notional_fraction=Decimal("0.05"),
        )
    ).evaluate(
        entry=ranked_entry(),
        portfolio=portfolio(),
        at=RANKED_AT,
    )

    assert assessment.risk_budget == Decimal("1000.00000000")
    assert assessment.notional_budget == Decimal("500.00000000")
    assert assessment.max_simulated_quantity == Decimal("4.90196078")


def test_policy_rejects_invalid_fraction() -> None:
    with pytest.raises(ValidationError):
        CandidateRiskPolicy(
            max_risk_fraction=Decimal("0"),
        )


def test_assessment_check_order_is_stable_and_complete() -> None:
    assessment = CandidateRiskEvaluator().evaluate(
        entry=ranked_entry(),
        portfolio=portfolio(),
        at=RANKED_AT,
    )

    assert tuple(check.name for check in assessment.checks) == tuple(CandidateRiskCheckName)
