from datetime import UTC, datetime
from decimal import Decimal

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode
from trd_bot.research.candidate_ranking import CandidateRanker
from trd_bot.research.candidate_simulation_runner import CandidateSimulationRunner
from trd_bot.research.candidates import (
    CandidateBuilder,
    CandidateEntryZone,
    CandidateTarget,
    CandidateTradePlan,
)
from trd_bot.research.datasets import DatasetBuilder
from trd_bot.research.position_monitoring import (
    CandidateExitReason,
    CandidatePositionMonitor,
)
from trd_bot.research.risk_policy import CandidateRiskEvaluator, CandidateRiskPolicy
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
CANDIDATE_CREATED_AT = datetime(2026, 8, 26, 11, 1, tzinfo=UTC)
RANKED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)
SIMULATION_OPENED_AT = datetime(2026, 8, 26, 13, tzinfo=UTC)


def candle(
    hour: int,
    *,
    high_price: str,
    low_price: str,
    close_price: str,
) -> OHLCVCandle:
    close = Decimal(close_price)

    return OHLCVCandle(
        source="test-exchange",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 8, 26, hour, tzinfo=UTC),
        close_time=datetime(2026, 8, 26, hour + 1, tzinfo=UTC),
        received_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
        open_price=close,
        high_price=Decimal(high_price),
        low_price=Decimal(low_price),
        close_price=close,
        volume=Decimal("1000"),
        is_closed=True,
    )


def dataset(
    *,
    future_candles: tuple[OHLCVCandle, ...],
):
    candles = (
        candle(
            10,
            high_price="103",
            low_price="99",
            close_price="102",
        ),
        candle(
            11,
            high_price="104",
            low_price="100",
            close_price="101",
        ),
        candle(
            12,
            high_price="102",
            low_price="100",
            close_price="101",
        ),
        *future_candles,
    )

    return DatasetBuilder().build(
        name="position monitoring dataset",
        candles=candles,
        created_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
    )


def simulation(
    *,
    monitoring_dataset,
    valid_until: datetime,
    action: SignalDirection = SignalDirection.LONG,
):
    score = Decimal("0.80")
    entry_zone = CandidateEntryZone(
        lower_price=Decimal("100"),
        upper_price=Decimal("102"),
    )
    invalidation = Decimal("97")
    target = Decimal("108")
    fill_price = Decimal("101")

    if action is SignalDirection.SHORT:
        score = Decimal("-0.80")
        entry_zone = CandidateEntryZone(
            lower_price=Decimal("98"),
            upper_price=Decimal("100"),
        )
        invalidation = Decimal("103")
        target = Decimal("92")
        fill_price = Decimal("99")

    signal = StrategySignal(
        signal_id=build_signal_id(
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            dataset_id=monitoring_dataset.dataset_id,
            candle_close_time=CLOSE_TIME,
            direction=action,
        ),
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        dataset_id=monitoring_dataset.dataset_id,
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        candle_open_time=OPEN_TIME,
        candle_close_time=CLOSE_TIME,
        generated_at=CLOSE_TIME,
        direction=action,
        score=score,
        reason="Historical signal for position monitoring.",
        features=(
            StrategyFeature(
                name="test_feature",
                value=Decimal("1"),
            ),
        ),
    )
    candidate = CandidateBuilder.from_signal(
        signal=signal,
        experiment_id="experiment-0123456789abcdef",
        horizon_candles=4,
        confidence=Decimal("0.80"),
        created_at=CANDIDATE_CREATED_AT,
        valid_until=valid_until,
        trade_plan=CandidateTradePlan(
            entry_zone=entry_zone,
            invalidation_price=invalidation,
            targets=(
                CandidateTarget(
                    label="target-1",
                    price=target,
                ),
            ),
        ),
    )
    entry = (
        CandidateRanker()
        .rank(
            candidates=(candidate,),
            at=RANKED_AT,
        )
        .entries[0]
    )
    portfolio = SimulatedPortfolioLedger().create(
        mode=SimulationMode.PAPER,
        dataset_id=monitoring_dataset.dataset_id,
        starting_cash=Decimal("10000"),
        created_at=datetime(2026, 8, 26, 11, tzinfo=UTC),
    )
    assessment = CandidateRiskEvaluator(
        policy=CandidateRiskPolicy(
            min_reward_risk_ratio=Decimal("1.00"),
        )
    ).evaluate(
        entry=entry,
        portfolio=portfolio,
        at=RANKED_AT,
    )

    return CandidateSimulationRunner().run(
        assessment=assessment,
        portfolio=portfolio,
        fill_price=fill_price,
        occurred_at=SIMULATION_OPENED_AT,
    )


def test_monitor_marks_interim_candle_then_closes_at_target() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="106",
                low_price="99",
                close_price="104",
            ),
            candle(
                14,
                high_price="109",
                low_price="103",
                close_price="107",
            ),
        )
    )

    result = CandidatePositionMonitor().run(
        simulation=simulation(
            monitoring_dataset=monitoring_dataset,
            valid_until=datetime(2026, 8, 26, 17, tzinfo=UTC),
        ),
        dataset=monitoring_dataset,
    )

    assert result.trigger.reason is CandidateExitReason.TARGET
    assert result.trigger.price == Decimal("108")
    assert result.trigger.target_label == "target-1"
    assert result.monitored_candles == 2
    assert result.marked_candles == 1
    assert result.closed_position.exit_price == Decimal("108")


def test_monitor_closes_at_invalidation() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="104",
                low_price="96",
                close_price="99",
            ),
            candle(
                14,
                high_price="105",
                low_price="98",
                close_price="103",
            ),
        )
    )

    result = CandidatePositionMonitor().run(
        simulation=simulation(
            monitoring_dataset=monitoring_dataset,
            valid_until=datetime(2026, 8, 26, 17, tzinfo=UTC),
        ),
        dataset=monitoring_dataset,
    )

    assert result.trigger.reason is CandidateExitReason.INVALIDATION
    assert result.trigger.price == Decimal("97")
    assert result.monitored_candles == 1
    assert result.marked_candles == 0


def test_invalidation_wins_when_same_candle_touches_target_and_stop() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="109",
                low_price="96",
                close_price="104",
            ),
            candle(
                14,
                high_price="105",
                low_price="100",
                close_price="103",
            ),
        )
    )

    result = CandidatePositionMonitor().run(
        simulation=simulation(
            monitoring_dataset=monitoring_dataset,
            valid_until=datetime(2026, 8, 26, 17, tzinfo=UTC),
        ),
        dataset=monitoring_dataset,
    )

    assert result.trigger.reason is CandidateExitReason.INVALIDATION
    assert result.trigger.price == Decimal("97")


def test_monitor_closes_at_time_expiry_on_closed_candle_price() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="106",
                low_price="99",
                close_price="104",
            ),
            candle(
                14,
                high_price="106",
                low_price="100",
                close_price="105",
            ),
        )
    )

    result = CandidatePositionMonitor().run(
        simulation=simulation(
            monitoring_dataset=monitoring_dataset,
            valid_until=datetime(2026, 8, 26, 14, tzinfo=UTC),
        ),
        dataset=monitoring_dataset,
    )

    assert result.trigger.reason is CandidateExitReason.TIME_EXPIRY
    assert result.trigger.price == Decimal("104")
    assert result.closed_at == datetime(2026, 8, 26, 14, tzinfo=UTC)


def test_monitor_closes_at_end_of_data_when_no_other_exit_occurs() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="106",
                low_price="99",
                close_price="104",
            ),
            candle(
                14,
                high_price="106",
                low_price="100",
                close_price="105",
            ),
        )
    )

    result = CandidatePositionMonitor().run(
        simulation=simulation(
            monitoring_dataset=monitoring_dataset,
            valid_until=datetime(2026, 8, 26, 18, tzinfo=UTC),
        ),
        dataset=monitoring_dataset,
    )

    assert result.trigger.reason is CandidateExitReason.END_OF_DATA
    assert result.trigger.price == Decimal("105")
    assert result.monitored_candles == 2
    assert result.marked_candles == 1


def test_short_monitor_uses_short_invalidation_and_target_direction() -> None:
    monitoring_dataset = dataset(
        future_candles=(
            candle(
                13,
                high_price="101",
                low_price="94",
                close_price="96",
            ),
            candle(
                14,
                high_price="100",
                low_price="91",
                close_price="93",
            ),
        )
    )

    result = CandidatePositionMonitor().run(
        simulation=simulation(
            monitoring_dataset=monitoring_dataset,
            valid_until=datetime(2026, 8, 26, 17, tzinfo=UTC),
            action=SignalDirection.SHORT,
        ),
        dataset=monitoring_dataset,
    )

    assert result.trigger.reason is CandidateExitReason.TARGET
    assert result.trigger.price == Decimal("92")
    assert result.closed_position.exit_price == Decimal("92")
