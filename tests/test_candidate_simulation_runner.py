from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.backtesting import PositionSide
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode
from trd_bot.research.candidate_ranking import CandidateRanker
from trd_bot.research.candidate_simulation_runner import CandidateSimulationRunner
from trd_bot.research.candidates import (
    CandidateBuilder,
    CandidateEntryZone,
    CandidateStatus,
    CandidateTarget,
    CandidateTradePlan,
)
from trd_bot.research.risk_policy import (
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
OPENED_AT = datetime(2026, 8, 26, 12, 5, tzinfo=UTC)
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


def candidate(
    *,
    valid_until: datetime = VALID_UNTIL,
):
    return CandidateBuilder.from_signal(
        signal=create_signal(),
        experiment_id=EXPERIMENT_ID,
        horizon_candles=4,
        confidence=Decimal("0.80"),
        created_at=CANDIDATE_CREATED_AT,
        valid_until=valid_until,
        trade_plan=CandidateTradePlan(
            entry_zone=CandidateEntryZone(
                lower_price=Decimal("100"),
                upper_price=Decimal("102"),
            ),
            invalidation_price=Decimal("97"),
            targets=(
                CandidateTarget(
                    label="target-1",
                    price=Decimal("112"),
                ),
            ),
        ),
    )


def portfolio():
    return SimulatedPortfolioLedger().create(
        mode=SimulationMode.PAPER,
        dataset_id="dataset-test",
        starting_cash=Decimal("10000"),
        created_at=PORTFOLIO_CREATED_AT,
    )


def assessment(
    simulated_portfolio,
    *,
    risk_policy: CandidateRiskPolicy | None = None,
    valid_until: datetime = VALID_UNTIL,
):
    ranking_entry = (
        CandidateRanker()
        .rank(
            candidates=(
                candidate(
                    valid_until=valid_until,
                ),
            ),
            at=RANKED_AT,
        )
        .entries[0]
    )

    return CandidateRiskEvaluator(
        policy=risk_policy,
    ).evaluate(
        entry=ranking_entry,
        portfolio=simulated_portfolio,
        at=RANKED_AT,
    )


def test_approved_candidate_opens_offline_simulated_position() -> None:
    simulated_portfolio = portfolio()
    approved = assessment(simulated_portfolio)

    result = CandidateSimulationRunner().run(
        assessment=approved,
        portfolio=simulated_portfolio,
        fill_price=Decimal("101"),
        occurred_at=OPENED_AT,
    )

    assert approved.decision is CandidateRiskDecision.APPROVED
    assert result.selected_candidate.status is CandidateStatus.SELECTED
    assert result.selected_candidate.status_changed_at == OPENED_AT
    assert result.opened_position.status.value == "open"
    assert result.opened_position.side is PositionSide.LONG
    assert result.opened_position.entry_price == Decimal("101")
    assert result.quantity == Decimal("20.00000000")
    assert result.portfolio.positions == (result.opened_position,)


def test_runner_rejects_non_approved_assessment() -> None:
    simulated_portfolio = portfolio()
    rejected = assessment(
        simulated_portfolio,
        risk_policy=CandidateRiskPolicy(
            min_ranking_score=Decimal("0.95"),
        ),
    )

    assert rejected.decision is CandidateRiskDecision.REJECTED

    with pytest.raises(
        ValueError,
        match="must be approved",
    ):
        CandidateSimulationRunner().run(
            assessment=rejected,
            portfolio=simulated_portfolio,
            fill_price=Decimal("101"),
            occurred_at=OPENED_AT,
        )


def test_runner_rejects_fill_outside_candidate_entry_zone() -> None:
    simulated_portfolio = portfolio()
    approved = assessment(simulated_portfolio)

    with pytest.raises(
        ValueError,
        match="inside candidate entry zone",
    ):
        CandidateSimulationRunner().run(
            assessment=approved,
            portfolio=simulated_portfolio,
            fill_price=Decimal("103"),
            occurred_at=OPENED_AT,
        )


def test_runner_rejects_candidate_that_expired_after_risk_assessment() -> None:
    simulated_portfolio = portfolio()
    expires_at = RANKED_AT + timedelta(minutes=10)
    approved = assessment(
        simulated_portfolio,
        valid_until=expires_at,
    )

    with pytest.raises(
        ValueError,
        match="no longer selectable",
    ):
        CandidateSimulationRunner().run(
            assessment=approved,
            portfolio=simulated_portfolio,
            fill_price=Decimal("101"),
            occurred_at=expires_at,
        )


def test_runner_rejects_portfolio_changed_after_assessment() -> None:
    ledger = SimulatedPortfolioLedger()
    simulated_portfolio = portfolio()
    approved = assessment(simulated_portfolio)

    changed_portfolio = ledger.open_position(
        simulated_portfolio,
        pair=PAIR,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("1"),
        occurred_at=RANKED_AT + timedelta(minutes=1),
    )

    with pytest.raises(
        ValueError,
        match="changed after risk assessment",
    ):
        CandidateSimulationRunner().run(
            assessment=approved,
            portfolio=changed_portfolio,
            fill_price=Decimal("101"),
            occurred_at=OPENED_AT,
        )


def test_runner_rejects_simulation_before_risk_assessment() -> None:
    simulated_portfolio = portfolio()
    approved = assessment(simulated_portfolio)

    with pytest.raises(
        ValueError,
        match="cannot precede risk assessment",
    ):
        CandidateSimulationRunner().run(
            assessment=approved,
            portfolio=simulated_portfolio,
            fill_price=Decimal("101"),
            occurred_at=RANKED_AT - timedelta(minutes=1),
        )
