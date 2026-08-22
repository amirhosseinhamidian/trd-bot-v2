from datetime import UTC, datetime, timedelta

from trd_bot.research import (
    DatasetSnapshot,
    ResearchActivityBuilder,
    ResearchActivityType,
    ResearchExperiment,
    WalkForwardExecutionResult,
    WalkForwardResearchRun,
)

CREATED_AT = datetime(
    2026,
    8,
    22,
    10,
    tzinfo=UTC,
)


def test_activity_builder_maps_dataset_metadata() -> None:
    dataset = DatasetSnapshot.model_construct(
        dataset_id="dataset-one",
        name="Historical BTC dataset",
        created_at=CREATED_AT,
    )

    item = ResearchActivityBuilder().build(datasets=(dataset,))[0]

    assert item.activity_type is ResearchActivityType.DATASET
    assert item.resource_id == "dataset-one"
    assert item.dataset_id == "dataset-one"
    assert item.label == "Historical BTC dataset"
    assert item.strategy_name is None


def test_activity_builder_maps_experiment_metadata() -> None:
    experiment = ResearchExperiment.model_construct(
        experiment_id=("experiment-0000000000000001"),
        created_at=CREATED_AT,
        dataset_id="dataset-one",
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        horizon_candles=2,
    )

    item = ResearchActivityBuilder().build(experiments=(experiment,))[0]

    assert item.activity_type is ResearchActivityType.EXPERIMENT
    assert item.resource_id == experiment.experiment_id
    assert item.strategy_name == "ema-crossover"
    assert item.strategy_version == "1.0.0"
    assert item.horizon_candles == 2


def test_activity_builder_maps_walk_forward_metadata() -> None:
    result = WalkForwardExecutionResult.model_construct(
        source_dataset_id="dataset-one",
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        horizon_candles=3,
    )

    run = WalkForwardResearchRun.model_construct(
        execution_id=("walk-forward-execution-0000000000000001"),
        created_at=CREATED_AT,
        result=result,
    )

    item = ResearchActivityBuilder().build(walk_forward_runs=(run,))[0]

    assert item.activity_type is ResearchActivityType.WALK_FORWARD_RUN
    assert item.resource_id == run.execution_id
    assert item.dataset_id == "dataset-one"
    assert item.horizon_candles == 3


def test_activity_builder_orders_newest_items_first() -> None:
    older = DatasetSnapshot.model_construct(
        dataset_id="dataset-older",
        name="Older dataset",
        created_at=CREATED_AT,
    )

    newer = DatasetSnapshot.model_construct(
        dataset_id="dataset-newer",
        name="Newer dataset",
        created_at=(CREATED_AT + timedelta(hours=1)),
    )

    items = ResearchActivityBuilder().build(
        datasets=(
            older,
            newer,
        )
    )

    assert [item.resource_id for item in items] == [
        "dataset-newer",
        "dataset-older",
    ]


def test_activity_builder_returns_empty_feed_without_resources() -> None:
    assert ResearchActivityBuilder().build() == ()
