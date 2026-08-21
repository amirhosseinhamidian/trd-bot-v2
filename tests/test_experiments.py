from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import (
    OHLCVCandle,
    Timeframe,
    TradingPair,
)
from trd_bot.research import (
    DatasetBuilder,
    ExperimentBuilder,
    ExperimentParameter,
    InMemoryExperimentRegistry,
    ResearchPipeline,
    ResearchPipelineResult,
)
from trd_bot.research.experiments import ExperimentSummary
from trd_bot.strategies import EMACrossoverStrategy

PAIR = TradingPair(
    base_asset="BTC",
    quote_asset="USDT",
)

CREATED_AT = datetime(
    2026,
    8,
    21,
    20,
    tzinfo=UTC,
)


def create_result(
    *,
    horizon_candles: int = 1,
) -> ResearchPipelineResult:
    close_prices = ["5", "4", "3", "4", "6", "8", "9"]
    candles = []

    for index, price_text in enumerate(close_prices):
        price = Decimal(price_text)
        hour = 10 + index

        candles.append(
            OHLCVCandle(
                source="test-exchange",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=datetime(
                    2026,
                    8,
                    21,
                    hour,
                    tzinfo=UTC,
                ),
                close_time=datetime(
                    2026,
                    8,
                    21,
                    hour + 1,
                    tzinfo=UTC,
                ),
                received_at=CREATED_AT,
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    dataset = DatasetBuilder().build(
        name="Experiment dataset",
        candles=candles,
    )

    return ResearchPipeline().run(
        dataset=dataset,
        strategy=EMACrossoverStrategy(
            fast_period=2,
            slow_period=3,
        ),
        horizon_candles=horizon_candles,
    )


def create_parameters() -> tuple[ExperimentParameter, ...]:
    return (
        ExperimentParameter(
            name="slow_period",
            value="3",
        ),
        ExperimentParameter(
            name="fast_period",
            value="2",
        ),
    )


def test_experiment_id_is_deterministic() -> None:
    result = create_result()

    first = ExperimentBuilder().build(
        result=result,
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )

    second = ExperimentBuilder().build(
        result=result,
        parameters=tuple(reversed(create_parameters())),
        created_at=CREATED_AT,
    )

    assert first.experiment_id == second.experiment_id
    assert first.parameters[0].name == "fast_period"
    assert first.parameters[1].name == "slow_period"


def test_experiment_contains_research_metadata() -> None:
    result = create_result()

    experiment = ExperimentBuilder().build(
        result=result,
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )

    assert experiment.dataset_id == result.dataset_id
    assert experiment.strategy_name == "ema-crossover"
    assert experiment.strategy_version == "1.0.0"
    assert experiment.horizon_candles == 1
    assert experiment.result == result


def test_registry_saves_and_retrieves_experiment() -> None:
    experiment = ExperimentBuilder().build(
        result=create_result(),
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )

    registry = InMemoryExperimentRegistry()

    saved = registry.save(experiment)

    assert saved == experiment
    assert registry.get(experiment.experiment_id) == experiment
    assert registry.list_all() == (experiment,)


def test_registry_save_is_idempotent() -> None:
    result = create_result()

    first = ExperimentBuilder().build(
        result=result,
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )

    second = ExperimentBuilder().build(
        result=result,
        parameters=create_parameters(),
        created_at=datetime(
            2026,
            8,
            22,
            10,
            tzinfo=UTC,
        ),
    )

    registry = InMemoryExperimentRegistry()

    registry.save(first)
    saved_again = registry.save(second)

    assert saved_again is first
    assert len(registry.list_all()) == 1


def test_registry_rejects_conflicting_content() -> None:
    experiment = ExperimentBuilder().build(
        result=create_result(),
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )

    conflicting_result = experiment.result.model_copy(
        update={"generated_signals": 999},
    )

    conflicting_experiment = experiment.model_copy(
        update={"result": conflicting_result},
    )

    registry = InMemoryExperimentRegistry()
    registry.save(experiment)

    with pytest.raises(
        ValueError,
        match="different content",
    ):
        registry.save(conflicting_experiment)


def test_experiment_summary_excludes_full_result() -> None:
    experiment = ExperimentBuilder().build(
        result=create_result(),
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )

    summary = ExperimentSummary.from_experiment(experiment)
    payload = summary.model_dump()

    assert summary.experiment_id == experiment.experiment_id
    assert summary.dataset_id == experiment.dataset_id
    assert summary.generated_signals == experiment.result.generated_signals
    assert "result" not in payload


def test_registry_returns_paginated_experiments() -> None:
    first = ExperimentBuilder().build(
        result=create_result(horizon_candles=1),
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )

    second = ExperimentBuilder().build(
        result=create_result(horizon_candles=2),
        parameters=create_parameters(),
        created_at=datetime(
            2026,
            8,
            22,
            20,
            tzinfo=UTC,
        ),
    )

    registry = InMemoryExperimentRegistry()
    registry.save(first)
    registry.save(second)

    assert registry.count() == 2
    assert registry.list_page(limit=1, offset=0) == (first,)
    assert registry.list_page(limit=1, offset=1) == (second,)
    assert registry.list_page(limit=10, offset=2) == ()


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),
        (1, -1),
    ],
)
def test_registry_rejects_invalid_pagination(
    limit: int,
    offset: int,
) -> None:
    registry = InMemoryExperimentRegistry()

    with pytest.raises(ValueError):
        registry.list_page(
            limit=limit,
            offset=offset,
        )
