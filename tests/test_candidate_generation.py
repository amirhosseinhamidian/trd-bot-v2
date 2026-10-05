from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tests.test_experiment_replay import build_experiment
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.research.candidate_generation import (
    CandidateGenerationPolicy,
    CandidateGenerator,
)
from trd_bot.research.candidates import CandidateAction


def test_generates_long_candidate_from_source_signal_without_lookahead() -> None:
    dataset, experiment = build_experiment()
    source_signal = experiment.result.signals[0]

    candidates = CandidateGenerator().generate(
        experiment=experiment,
        dataset=dataset,
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.experiment_id == experiment.experiment_id
    assert candidate.dataset_id == dataset.dataset_id
    assert candidate.signal_id == source_signal.signal_id

    assert candidate.action is CandidateAction.LONG
    assert candidate.source_direction == source_signal.direction

    assert candidate.confidence == Decimal("0.50")
    assert candidate.created_at == datetime(2026, 8, 20, 15, tzinfo=UTC)
    assert candidate.valid_until == datetime(2026, 8, 20, 16, tzinfo=UTC)

    assert candidate.trade_plan is not None
    assert candidate.trade_plan.entry_zone.lower_price == Decimal("6")
    assert candidate.trade_plan.entry_zone.upper_price == Decimal("6")
    assert candidate.trade_plan.invalidation_price == Decimal("5")

    assert len(candidate.trade_plan.targets) == 1
    assert candidate.trade_plan.targets[0].label == "target-1"
    assert candidate.trade_plan.targets[0].price == Decimal("8")


from trd_bot.strategies.signals import (  # noqa: E402
    SignalDirection,
    StrategySignal,
    build_signal_id,
)


def experiment_with_signal(
    *,
    direction: SignalDirection,
    score: Decimal,
):
    dataset, experiment = build_experiment()
    source = experiment.result.signals[0]

    signal = StrategySignal(
        signal_id=build_signal_id(
            strategy_name=source.strategy_name,
            strategy_version=source.strategy_version,
            dataset_id=source.dataset_id,
            candle_close_time=source.candle_close_time,
            direction=direction,
        ),
        strategy_name=source.strategy_name,
        strategy_version=source.strategy_version,
        dataset_id=source.dataset_id,
        pair=source.pair,
        timeframe=source.timeframe,
        candle_open_time=source.candle_open_time,
        candle_close_time=source.candle_close_time,
        generated_at=source.generated_at,
        direction=direction,
        score=score,
        reason=f"Synthetic {direction.value} signal for candidate generation.",
        features=source.features,
    )

    result = experiment.result.model_copy(
        update={
            "signals": (signal,),
        }
    )
    experiment = experiment.model_copy(
        update={
            "result": result,
        }
    )

    return dataset, experiment


def test_generates_short_candidate_with_two_r_target() -> None:
    dataset, experiment = experiment_with_signal(
        direction=SignalDirection.SHORT,
        score=Decimal("-0.80"),
    )

    candidates = CandidateGenerator().generate(
        experiment=experiment,
        dataset=dataset,
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.action is CandidateAction.SHORT
    assert candidate.trade_plan is not None

    assert candidate.trade_plan.entry_zone.lower_price == Decimal("6")
    assert candidate.trade_plan.entry_zone.upper_price == Decimal("6")

    assert candidate.trade_plan.invalidation_price == Decimal("7")
    assert candidate.trade_plan.targets[0].price == Decimal("4")


def test_skips_neutral_signal() -> None:
    dataset, experiment = experiment_with_signal(
        direction=SignalDirection.NEUTRAL,
        score=Decimal("0"),
    )

    candidates = CandidateGenerator().generate(
        experiment=experiment,
        dataset=dataset,
    )

    assert candidates == ()


def test_rejects_experiment_dataset_lineage_mismatch() -> None:
    dataset, experiment = build_experiment()

    mismatched_experiment = experiment.model_copy(
        update={
            "dataset_id": "dataset-mismatched",
        }
    )

    with pytest.raises(
        ValueError,
        match="experiment and candidate dataset lineage must match",
    ):
        CandidateGenerator().generate(
            experiment=mismatched_experiment,
            dataset=dataset,
        )


def test_future_candles_do_not_change_generated_candidate() -> None:
    dataset, experiment = build_experiment()
    source_signal = experiment.result.signals[0]

    baseline = CandidateGenerator().generate(
        experiment=experiment,
        dataset=dataset,
    )

    altered_candles = tuple(
        candle.model_copy(
            update={
                "open_price": Decimal("500"),
                "high_price": Decimal("600"),
                "low_price": Decimal("400"),
                "close_price": Decimal("550"),
            }
        )
        if candle.open_time >= source_signal.candle_close_time
        else candle
        for candle in dataset.candles
    )

    future_changed_dataset = dataset.model_copy(
        update={
            "candles": altered_candles,
        }
    )

    regenerated = CandidateGenerator().generate(
        experiment=experiment,
        dataset=future_changed_dataset,
    )

    assert regenerated == baseline


def test_rejects_signal_without_exact_source_candle() -> None:
    dataset, experiment = build_experiment()
    source = experiment.result.signals[0]

    shifted_signal = StrategySignal(
        signal_id=build_signal_id(
            strategy_name=source.strategy_name,
            strategy_version=source.strategy_version,
            dataset_id=source.dataset_id,
            candle_close_time=datetime(2026, 8, 20, 15, 30, tzinfo=UTC),
            direction=source.direction,
        ),
        strategy_name=source.strategy_name,
        strategy_version=source.strategy_version,
        dataset_id=source.dataset_id,
        pair=source.pair,
        timeframe=source.timeframe,
        candle_open_time=datetime(2026, 8, 20, 14, 30, tzinfo=UTC),
        candle_close_time=datetime(2026, 8, 20, 15, 30, tzinfo=UTC),
        generated_at=datetime(2026, 8, 20, 15, 30, tzinfo=UTC),
        direction=source.direction,
        score=source.score,
        reason=source.reason,
        features=source.features,
    )

    shifted_result = experiment.result.model_copy(
        update={
            "signals": (shifted_signal,),
        }
    )

    shifted_experiment = experiment.model_copy(
        update={
            "result": shifted_result,
        }
    )

    with pytest.raises(
        ValueError,
        match="candidate source signal must map to exactly one dataset candle",
    ):
        CandidateGenerator().generate(
            experiment=shifted_experiment,
            dataset=dataset,
        )


@pytest.mark.parametrize(
    ("signal_update", "expected_error"),
    (
        (
            {"dataset_id": "dataset-wrong"},
            "candidate source signal dataset lineage must match",
        ),
        (
            {
                "pair": TradingPair(
                    base_asset="ETH",
                    quote_asset="USDT",
                )
            },
            "candidate source signal pair must match dataset",
        ),
        (
            {"timeframe": Timeframe.HOURS_4},
            "candidate source signal timeframe must match dataset",
        ),
    ),
)
def test_rejects_signal_lineage_that_does_not_match_dataset(
    signal_update: dict[str, object],
    expected_error: str,
) -> None:
    dataset, experiment = build_experiment()
    source = experiment.result.signals[0]

    mismatched_signal = source.model_copy(
        update=signal_update,
    )

    mismatched_result = experiment.result.model_copy(
        update={
            "signals": (mismatched_signal,),
        }
    )

    mismatched_experiment = experiment.model_copy(
        update={
            "result": mismatched_result,
        }
    )

    with pytest.raises(
        ValueError,
        match=expected_error,
    ):
        CandidateGenerator().generate(
            experiment=mismatched_experiment,
            dataset=dataset,
        )


def test_generation_policy_controls_confidence_and_reward_risk_ratio() -> None:
    dataset, experiment = build_experiment()

    generator = CandidateGenerator(
        policy=CandidateGenerationPolicy(
            confidence_prior=Decimal("0.70"),
            reward_risk_ratio=Decimal("3.00"),
        )
    )

    candidates = generator.generate(
        experiment=experiment,
        dataset=dataset,
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.confidence == Decimal("0.70")
    assert candidate.trade_plan is not None

    # LONG fixture:
    # entry = 6
    # invalidation = 5
    # unit risk = 1
    # 3R target = 9
    assert candidate.trade_plan.targets[0].price == Decimal("9")


def test_candidate_generation_is_deterministic() -> None:
    dataset, experiment = build_experiment()
    generator = CandidateGenerator()

    first = generator.generate(
        experiment=experiment,
        dataset=dataset,
    )
    second = generator.generate(
        experiment=experiment,
        dataset=dataset,
    )

    assert first == second
    assert tuple(candidate.candidate_id for candidate in first) == tuple(
        candidate.candidate_id for candidate in second
    )
