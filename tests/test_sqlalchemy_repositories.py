from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentRegistry,
    SqlAlchemyWalkForwardRunRegistry,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import (
    DatasetBuilder,
    DatasetCatalogQuery,
    DatasetSnapshot,
    DatasetSortDirection,
    ExperimentBuilder,
    ExperimentParameter,
    ResearchExperiment,
    ResearchPipeline,
    WalkForwardConfig,
    WalkForwardDatasetMaterializer,
    WalkForwardExecutor,
    WalkForwardPlanner,
    WalkForwardResearchRun,
    WalkForwardRunBuilder,
)
from trd_bot.strategies import EMACrossoverStrategy

CREATED_AT = datetime(2026, 8, 22, 10, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'repositories.db'}"
    engine = create_database_engine(database_url)
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def create_dataset(
    *,
    created_at: datetime = CREATED_AT,
    start_day: int = 1,
    source: str = "test-exchange",
    pair: TradingPair = PAIR,
    timeframe: Timeframe = Timeframe.HOUR_1,
) -> DatasetSnapshot:
    start = datetime(
        2026,
        8,
        start_day,
        10,
        tzinfo=UTC,
    )

    interval = {
        Timeframe.MINUTES_15: timedelta(minutes=15),
        Timeframe.HOUR_1: timedelta(hours=1),
        Timeframe.HOURS_4: timedelta(hours=4),
        Timeframe.DAY_1: timedelta(days=1),
    }[timeframe]

    prices = (
        "5",
        "4",
        "3",
        "4",
        "6",
        "5",
        "3",
        "4",
        "6",
        "8",
    )

    candles = []

    for index, price_text in enumerate(prices):
        price = Decimal(price_text)
        open_time = start + interval * index

        candles.append(
            OHLCVCandle(
                source=source,
                pair=pair,
                timeframe=timeframe,
                open_time=open_time,
                close_time=open_time + interval,
                received_at=CREATED_AT,
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(
        name="Repository dataset",
        candles=candles,
        created_at=created_at,
    )


def create_experiment(
    dataset: DatasetSnapshot,
    *,
    created_at: datetime = CREATED_AT,
    parameter_value: str = "2",
) -> ResearchExperiment:
    result = ResearchPipeline().run(
        dataset=dataset,
        strategy=EMACrossoverStrategy(fast_period=2, slow_period=3),
    )
    return ExperimentBuilder().build(
        result=result,
        parameters=(
            ExperimentParameter(name="fast_period", value=parameter_value),
            ExperimentParameter(name="slow_period", value="3"),
        ),
        created_at=created_at,
    )


def create_walk_forward_run(
    dataset: DatasetSnapshot,
    *,
    created_at: datetime = CREATED_AT,
    fast_period: int = 2,
    slow_period: int = 3,
) -> WalkForwardResearchRun:
    config = WalkForwardConfig(train_candles=4, test_candles=2, step_candles=2)
    plan = WalkForwardPlanner().plan(dataset=dataset, config=config)
    materialization = WalkForwardDatasetMaterializer().materialize(
        dataset=dataset,
        plan=plan,
    )
    result = WalkForwardExecutor().execute(
        dataset=dataset,
        materialization=materialization,
        strategy=EMACrossoverStrategy(
            fast_period=fast_period,
            slow_period=slow_period,
        ),
        strategy_parameters=(
            ExperimentParameter(name="fast_period", value=str(fast_period)),
            ExperimentParameter(name="slow_period", value=str(slow_period)),
        ),
    )
    return WalkForwardRunBuilder().build(
        result=result,
        walk_forward_config=config,
        created_at=created_at,
    )


def test_dataset_persists_across_sessions(
    session_factory: sessionmaker[Session],
) -> None:
    dataset = create_dataset()
    with session_factory() as session:
        SqlAlchemyDatasetRepository(session).save(dataset)

    with session_factory() as session:
        repository = SqlAlchemyDatasetRepository(session)
        assert repository.get(dataset.dataset_id) == dataset
        assert repository.count() == 1


def test_dataset_save_is_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    first = create_dataset()
    second = create_dataset(created_at=CREATED_AT + timedelta(days=1)).model_copy(
        update={"name": "Another display name"}
    )
    with session_factory() as session:
        repository = SqlAlchemyDatasetRepository(session)
        repository.save(first)
        saved_again = repository.save(second)

        assert saved_again == first
        assert repository.count() == 1


def test_dataset_rejects_conflicting_content(
    session_factory: sessionmaker[Session],
) -> None:
    dataset = create_dataset()
    conflicting = dataset.model_copy(update={"checksum": "b" * 64})
    with session_factory() as session:
        repository = SqlAlchemyDatasetRepository(session)
        repository.save(dataset)
        with pytest.raises(ValueError, match="different content"):
            repository.save(conflicting)


def test_dataset_search_filters_sorts_and_counts_matches(
    session_factory: sessionmaker[Session],
) -> None:
    first = create_dataset()

    second = create_dataset(
        created_at=CREATED_AT + timedelta(hours=1),
        start_day=2,
        source="historical-archive",
        pair=TradingPair(
            base_asset="ETH",
            quote_asset="USDT",
        ),
        timeframe=Timeframe.HOURS_4,
    )

    third = create_dataset(
        created_at=CREATED_AT + timedelta(hours=2),
        start_day=3,
        pair=TradingPair(
            base_asset="BTC",
            quote_asset="USDC",
        ),
    )

    query = DatasetCatalogQuery(
        source="test-exchange",
        base_asset="btc",
        sort_direction=(DatasetSortDirection.DESCENDING),
    )

    with session_factory() as session:
        repository = SqlAlchemyDatasetRepository(session)

        repository.save(first)
        repository.save(second)
        repository.save(third)

        assert repository.count() == 3
        assert repository.count_matching(query) == 2

        assert repository.search_page(
            query=query,
            limit=10,
            offset=0,
        ) == (
            third,
            first,
        )


def test_experiment_persists_and_paginates(
    session_factory: sessionmaker[Session],
) -> None:
    dataset = create_dataset()
    first = create_experiment(dataset)
    second = create_experiment(
        dataset,
        created_at=CREATED_AT + timedelta(days=1),
        parameter_value="3",
    )
    with session_factory() as session:
        repository = SqlAlchemyExperimentRegistry(session)
        repository.save(first)
        repository.save(second)

    with session_factory() as session:
        repository = SqlAlchemyExperimentRegistry(session)
        assert repository.get(first.experiment_id) == first
        assert repository.count() == 2
        assert repository.list_page(limit=1, offset=1) == (second,)


def test_experiment_save_is_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    dataset = create_dataset()
    first = create_experiment(dataset)
    second = first.model_copy(update={"created_at": CREATED_AT + timedelta(days=1)})
    with session_factory() as session:
        repository = SqlAlchemyExperimentRegistry(session)
        repository.save(first)
        assert repository.save(second) == first
        assert repository.count() == 1


def test_experiment_rejects_conflicting_content(
    session_factory: sessionmaker[Session],
) -> None:
    experiment = create_experiment(create_dataset())
    conflicting = experiment.model_copy(
        update={"result": experiment.result.model_copy(update={"generated_signals": 999})}
    )
    with session_factory() as session:
        repository = SqlAlchemyExperimentRegistry(session)
        repository.save(experiment)
        with pytest.raises(ValueError, match="different content"):
            repository.save(conflicting)


def test_walk_forward_run_persists_and_paginates(
    session_factory: sessionmaker[Session],
) -> None:
    dataset = create_dataset()
    first = create_walk_forward_run(dataset)
    second = create_walk_forward_run(
        dataset,
        created_at=CREATED_AT + timedelta(days=1),
        fast_period=3,
        slow_period=4,
    )
    with session_factory() as session:
        repository = SqlAlchemyWalkForwardRunRegistry(session)
        repository.save(first)
        repository.save(second)

    with session_factory() as session:
        repository = SqlAlchemyWalkForwardRunRegistry(session)
        assert repository.get(first.execution_id) == first
        assert repository.count() == 2
        assert repository.list_page(limit=1, offset=1) == (second,)


def test_walk_forward_run_save_is_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    dataset = create_dataset()
    first = create_walk_forward_run(dataset)
    second = first.model_copy(update={"created_at": CREATED_AT + timedelta(days=1)})
    with session_factory() as session:
        repository = SqlAlchemyWalkForwardRunRegistry(session)
        repository.save(first)
        assert repository.save(second) == first
        assert repository.count() == 1


def test_walk_forward_run_rejects_conflicting_content(
    session_factory: sessionmaker[Session],
) -> None:
    run = create_walk_forward_run(create_dataset())
    conflicting = run.model_copy(
        update={
            "walk_forward_config": run.walk_forward_config.model_copy(update={"gap_candles": 1})
        }
    )
    with session_factory() as session:
        repository = SqlAlchemyWalkForwardRunRegistry(session)
        repository.save(run)
        with pytest.raises(ValueError, match="different content"):
            repository.save(conflicting)


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (1, -1)])
def test_sqlalchemy_repositories_reject_invalid_pagination(
    session_factory: sessionmaker[Session],
    limit: int,
    offset: int,
) -> None:
    with session_factory() as session:
        repositories = (
            SqlAlchemyDatasetRepository(session),
            SqlAlchemyExperimentRegistry(session),
            SqlAlchemyWalkForwardRunRegistry(session),
        )
        for repository in repositories:
            with pytest.raises(ValueError):
                repository.list_page(limit=limit, offset=offset)
