from datetime import UTC, datetime
from decimal import Decimal

from tests.test_candidate_replay_lifecycle import (
    EVALUATED_AT,
    candidate,
    candle,
    simulated_portfolio,
)
from trd_bot.research import CandidateRanker, DatasetBuilder
from trd_bot.research.dataset_replay_lifecycle import CandidateReplayLifecycleRunner
from trd_bot.research.position_monitoring import (
    CandidateExitDirective,
    CandidateExitReason,
)


def lifecycle_dataset_with_monitoring_horizon():
    return DatasetBuilder().build(
        name="candidate lifecycle quality observation dataset",
        candles=(
            candle(10, high_price="103", low_price="99", close_price="102"),
            candle(11, high_price="104", low_price="100", close_price="101"),
            candle(12, high_price="99", low_price="96", close_price="98"),
            candle(13, high_price="101", low_price="99", close_price="100"),
            candle(14, high_price="103", low_price="99", close_price="100"),
            candle(15, high_price="103", low_price="99", close_price="100"),
            candle(16, high_price="103", low_price="99", close_price="100"),
        ),
        created_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
    )


def ranked_entries_without_price_exit(*, dataset_id: str):
    return (
        CandidateRanker()
        .rank(
            candidates=(
                candidate(
                    dataset_id=dataset_id,
                    experiment_id="experiment-4444444444444444",
                    confidence="0.95",
                    entry_low="120",
                    entry_high="122",
                    invalidation="117",
                    target="132",
                ),
                candidate(
                    dataset_id=dataset_id,
                    experiment_id="experiment-5555555555555555",
                    confidence="0.80",
                    entry_low="100",
                    entry_high="102",
                    invalidation="90",
                    target="150",
                ),
            ),
            at=EVALUATED_AT,
        )
        .entries
    )


def observation_candles(dataset, *hours: int):
    requested = set(hours)
    return tuple(candle for candle in dataset.candles if candle.open_time.hour in requested)


def test_valid_monitoring_observations_preserve_normal_exit_behavior() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()

    result = CandidateReplayLifecycleRunner().run(
        entries=ranked_entries_without_price_exit(dataset_id=dataset.dataset_id),
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        monitoring_observations=observation_candles(dataset, 14, 15, 16),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.TIME_EXPIRY


def test_monitoring_observation_gap_generates_data_unreliable_exit() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()

    result = CandidateReplayLifecycleRunner().run(
        entries=ranked_entries_without_price_exit(dataset_id=dataset.dataset_id),
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        monitoring_observations=observation_candles(dataset, 14, 16),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.DATA_UNRELIABLE
    assert result.monitoring.trigger.occurred_at == datetime(
        2026,
        8,
        26,
        16,
        tzinfo=UTC,
    )
    assert result.monitoring.trigger.price == Decimal("100")


def test_generated_data_unreliable_wins_same_time_manual_directive() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()

    result = CandidateReplayLifecycleRunner().run(
        entries=ranked_entries_without_price_exit(dataset_id=dataset.dataset_id),
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        exit_directives=(
            CandidateExitDirective(
                reason=CandidateExitReason.TREND_REVERSAL,
                occurred_at=datetime(2026, 8, 26, 16, tzinfo=UTC),
            ),
        ),
        monitoring_observations=observation_candles(dataset, 14, 16),
    )

    assert result.monitoring is not None
    assert result.monitoring.trigger.reason is CandidateExitReason.DATA_UNRELIABLE


def test_monitoring_observations_must_match_dataset_series() -> None:
    dataset = lifecycle_dataset_with_monitoring_horizon()
    mismatched = observation_candles(dataset, 14)[0].model_copy(update={"source": "other-source"})

    try:
        CandidateReplayLifecycleRunner().run(
            entries=ranked_entries_without_price_exit(dataset_id=dataset.dataset_id),
            portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
            dataset=dataset,
            evaluated_at=EVALUATED_AT,
            monitoring_observations=(mismatched,),
        )
    except ValueError as error:
        assert str(error) == "monitoring observations must match lifecycle dataset series"
    else:
        raise AssertionError("mismatched monitoring observations must fail")
