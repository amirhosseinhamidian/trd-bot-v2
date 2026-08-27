from datetime import UTC, datetime

import pytest

from tests.test_candidate_position_monitoring import (
    candle,
    dataset,
    simulation,
)
from trd_bot.research.portfolio_risk_exit import (
    CandidatePortfolioRiskExitDirectiveProducer,
)
from trd_bot.research.position_monitoring import CandidateExitReason


def test_drawdown_below_approved_risk_budget_produces_no_directive() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="101",
                low_price="98",
                close_price="98",
            ),
        )
    )
    opened = simulation(
        monitoring_dataset=monitoring_dataset,
        valid_until=datetime(2026, 8, 26, 17, tzinfo=UTC),
    )

    directives = CandidatePortfolioRiskExitDirectiveProducer().produce(
        simulation=opened,
        monitoring_candles=monitoring_dataset.candles,
    )

    assert directives == ()


def test_drawdown_equal_to_approved_risk_budget_produces_portfolio_risk() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="101",
                low_price="96",
                close_price="96",
            ),
        )
    )
    opened = simulation(
        monitoring_dataset=monitoring_dataset,
        valid_until=datetime(2026, 8, 26, 17, tzinfo=UTC),
    )

    directives = CandidatePortfolioRiskExitDirectiveProducer().produce(
        simulation=opened,
        monitoring_candles=monitoring_dataset.candles,
    )

    assert opened.assessment.risk_budget == 100
    assert len(directives) == 1
    assert directives[0].reason is CandidateExitReason.PORTFOLIO_RISK
    assert directives[0].occurred_at == datetime(2026, 8, 26, 14, tzinfo=UTC)


def test_producer_uses_first_closed_candle_that_breaches_risk_budget() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="101",
                low_price="98",
                close_price="99",
            ),
            candle(
                14,
                high_price="100",
                low_price="96",
                close_price="96",
            ),
            candle(
                15,
                high_price="99",
                low_price="94",
                close_price="95",
            ),
        )
    )
    opened = simulation(
        monitoring_dataset=monitoring_dataset,
        valid_until=datetime(2026, 8, 26, 18, tzinfo=UTC),
    )

    directives = CandidatePortfolioRiskExitDirectiveProducer().produce(
        simulation=opened,
        monitoring_candles=tuple(reversed(monitoring_dataset.candles)),
    )

    assert len(directives) == 1
    assert directives[0].occurred_at == datetime(2026, 8, 26, 15, tzinfo=UTC)


def test_recovery_before_later_breach_is_marked_deterministically() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="104",
                low_price="100",
                close_price="103",
            ),
            candle(
                14,
                high_price="103",
                low_price="96",
                close_price="96",
            ),
        )
    )
    opened = simulation(
        monitoring_dataset=monitoring_dataset,
        valid_until=datetime(2026, 8, 26, 17, tzinfo=UTC),
    )

    directives = CandidatePortfolioRiskExitDirectiveProducer().produce(
        simulation=opened,
        monitoring_candles=monitoring_dataset.candles,
    )

    assert len(directives) == 1
    assert directives[0].occurred_at == datetime(2026, 8, 26, 15, tzinfo=UTC)


def test_monitoring_candle_lineage_mismatch_is_rejected() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="101",
                low_price="99",
                close_price="100",
            ),
        )
    )
    opened = simulation(
        monitoring_dataset=monitoring_dataset,
        valid_until=datetime(2026, 8, 26, 17, tzinfo=UTC),
    )
    mismatched = monitoring_dataset.candles[-1].model_copy(
        update={
            "pair": monitoring_dataset.pair.model_copy(
                update={"base_asset": "ETH"},
            )
        }
    )

    with pytest.raises(
        ValueError,
        match="portfolio risk monitoring candles must match selected candidate",
    ):
        CandidatePortfolioRiskExitDirectiveProducer().produce(
            simulation=opened,
            monitoring_candles=(mismatched,),
        )
