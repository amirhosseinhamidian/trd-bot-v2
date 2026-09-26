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
    ExperimentCatalogQuery,
    ExperimentParameter,
    ExperimentSortDirection,
    ExperimentSortField,
    InMemoryExperimentRegistry,
    ResearchPipeline,
    ResearchPipelineResult,
)
from trd_bot.research.experiments import ExperimentSummary
from trd_bot.strategies import (
    EMACrossoverStrategy,
    StrategyDefinition,
    StrategyRegistry,
    build_default_strategy_registry,
)

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
    assert experiment.strategy_fingerprint is not None
    assert experiment.strategy_fingerprint.startswith("sha256:")
    assert experiment.horizon_candles == 1
    assert experiment.result == result


def test_experiment_identity_includes_exact_strategy_fingerprint() -> None:
    result = create_result()
    default_registry = build_default_strategy_registry()
    default_definition = default_registry.require(
        name="ema-crossover",
        version="1.0.0",
    )
    assert default_definition.metadata is not None

    changed_registry = StrategyRegistry()
    changed_registry.register(
        StrategyDefinition(
            name=default_definition.name,
            version=default_definition.version,
            factory=default_definition.factory,
            metadata=default_definition.metadata.model_copy(
                update={"behavior_fingerprint": f"sha256:{'f' * 64}"},
            ),
        )
    )

    original = ExperimentBuilder(default_registry).build(
        result=result,
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )
    changed = ExperimentBuilder(changed_registry).build(
        result=result,
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )

    assert original.strategy_fingerprint != changed.strategy_fingerprint
    assert original.experiment_id != changed.experiment_id


def test_legacy_experiment_payload_without_fingerprint_remains_readable() -> None:
    experiment = ExperimentBuilder().build(
        result=create_result(),
        parameters=create_parameters(),
        created_at=CREATED_AT,
    )
    legacy_payload = experiment.model_dump(mode="json")
    legacy_payload.pop("strategy_fingerprint")

    restored = type(experiment).model_validate(legacy_payload)

    assert restored.strategy_fingerprint is None


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
    assert summary.strategy_fingerprint == experiment.strategy_fingerprint
    assert summary.generated_signals == experiment.result.generated_signals
    assert summary.total_trades == experiment.result.performance_report.total_trades
    assert summary.net_pnl == experiment.result.performance_report.net_pnl
    assert summary.total_return == experiment.result.performance_report.total_return
    assert summary.win_rate == experiment.result.performance_report.win_rate
    assert (
        summary.max_drawdown_fraction == experiment.result.performance_report.max_drawdown_fraction
    )
    assert summary.profit_factor == experiment.result.performance_report.profit_factor
    assert summary.benchmark_type == experiment.result.benchmark_result.benchmark_type
    assert (
        summary.benchmark_return
        == experiment.result.benchmark_result.performance_report.total_return
    )
    assert summary.excess_return == experiment.result.benchmark_comparison.return_delta
    assert (
        summary.benchmark_max_drawdown_fraction
        == experiment.result.benchmark_result.performance_report.max_drawdown_fraction
    )
    assert (
        summary.max_drawdown_fraction_delta
        == experiment.result.benchmark_comparison.max_drawdown_fraction_delta
    )
    assert (
        summary.strategy_has_lower_drawdown
        == experiment.result.benchmark_comparison.strategy_has_lower_drawdown
    )
    assert summary.comparison_outcome == experiment.result.benchmark_comparison.outcome
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


def test_registry_filters_experiments_and_counts_matches() -> None:
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

    query = ExperimentCatalogQuery(
        strategy_name=" ema-crossover ",
        horizon_candles=2,
    )

    assert registry.count() == 2
    assert registry.count_matching(query) == 1

    assert registry.search_page(
        query=query,
        limit=10,
        offset=0,
    ) == (second,)


def test_registry_sorts_experiments_by_horizon_descending() -> None:
    experiments = tuple(
        ExperimentBuilder().build(
            result=create_result(horizon_candles=horizon),
            parameters=create_parameters(),
            created_at=CREATED_AT,
        )
        for horizon in (1, 2, 3)
    )

    registry = InMemoryExperimentRegistry()

    for experiment in experiments:
        registry.save(experiment)

    query = ExperimentCatalogQuery(
        sort_by=(ExperimentSortField.HORIZON_CANDLES),
        sort_direction=(ExperimentSortDirection.DESCENDING),
    )

    assert registry.search_page(
        query=query,
        limit=10,
        offset=0,
    ) == tuple(reversed(experiments))
