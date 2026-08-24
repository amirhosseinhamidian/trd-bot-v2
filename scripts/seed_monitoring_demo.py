from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.engine import URL, make_url

from trd_bot.core.config import Settings
from trd_bot.db import (
    SqlAlchemyArchitectureRecommendationRepository,
    SqlAlchemySystemMetricRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.monitoring import (
    METRIC_UNITS,
    ArchitectureCandidate,
    ArchitectureCheckpointEvaluator,
    ArchitectureCheckpointPolicy,
    CheckpointEvaluationResult,
    SystemMetricName,
    SystemMetricSample,
    SystemMetricSource,
    build_metric_sample_id,
    default_checkpoint_policies,
)

DEMO_BASE_TIME = datetime(
    2026,
    8,
    24,
    12,
    tzinfo=UTC,
)

WINDOW_SECONDS = 300
OBSERVED_COUNT = 100


@dataclass(frozen=True, slots=True)
class DemoMetricSeries:
    """One deterministic demo metric series."""

    metric_name: SystemMetricName
    source: SystemMetricSource
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DemoScenario:
    """One synthetic architecture checkpoint scenario."""

    name: str
    candidate: ArchitectureCandidate
    start_time: datetime
    metric_series: tuple[
        DemoMetricSeries,
        ...,
    ]


DEMO_SCENARIOS = (
    DemoScenario(
        name="redis-healthy",
        candidate=ArchitectureCandidate.REDIS,
        start_time=DEMO_BASE_TIME,
        metric_series=(
            DemoMetricSeries(
                metric_name=(SystemMetricName.API_REQUEST_LATENCY_P95),
                source=SystemMetricSource.API,
                values=(
                    "0.180",
                    "0.220",
                    "0.200",
                ),
            ),
            DemoMetricSeries(
                metric_name=(SystemMetricName.API_REPEATED_READ_RATIO),
                source=SystemMetricSource.API,
                values=(
                    "0.20",
                    "0.25",
                    "0.22",
                ),
            ),
        ),
    ),
    DemoScenario(
        name="postgresql-warning",
        candidate=(ArchitectureCandidate.POSTGRESQL_TUNING),
        start_time=(DEMO_BASE_TIME + timedelta(minutes=30)),
        metric_series=(
            DemoMetricSeries(
                metric_name=(SystemMetricName.DATABASE_QUERY_LATENCY_P95),
                source=(SystemMetricSource.DATABASE),
                values=(
                    "0.400",
                    "0.450",
                    "0.420",
                ),
            ),
        ),
    ),
    DemoScenario(
        name="timescaledb-warning",
        candidate=(ArchitectureCandidate.TIMESCALEDB),
        start_time=(DEMO_BASE_TIME + timedelta(minutes=60)),
        metric_series=(
            DemoMetricSeries(
                metric_name=(SystemMetricName.TIME_SERIES_QUERY_LATENCY_P95),
                source=(SystemMetricSource.DATABASE),
                values=(
                    "1.40",
                    "1.60",
                    "1.50",
                ),
            ),
            DemoMetricSeries(
                metric_name=(SystemMetricName.CANDLE_STORAGE_SHARE),
                source=(SystemMetricSource.DATABASE),
                values=(
                    "0.65",
                    "0.68",
                    "0.70",
                ),
            ),
        ),
    ),
    DemoScenario(
        name="clickhouse-critical",
        candidate=(ArchitectureCandidate.CLICKHOUSE),
        start_time=(DEMO_BASE_TIME + timedelta(minutes=90)),
        metric_series=(
            DemoMetricSeries(
                metric_name=(SystemMetricName.ANALYTICAL_QUERY_LATENCY_P95),
                source=(SystemMetricSource.DATABASE),
                values=(
                    "12",
                    "13",
                    "11",
                ),
            ),
            DemoMetricSeries(
                metric_name=(SystemMetricName.ANALYTICAL_DATABASE_RESOURCE_SHARE),
                source=(SystemMetricSource.DATABASE),
                values=(
                    "0.70",
                    "0.72",
                    "0.68",
                ),
            ),
        ),
    ),
)


def validate_seed_target(settings: Settings) -> URL:
    """Prevent demo monitoring data from reaching production."""

    if settings.environment != "development":
        raise RuntimeError("monitoring demo seed may run only in the development environment")

    url = make_url(settings.database_url)

    if url.get_backend_name() != "postgresql":
        raise RuntimeError("monitoring demo seed requires PostgreSQL")

    if url.host not in {
        "127.0.0.1",
        "localhost",
    }:
        raise RuntimeError("monitoring demo seed may run only against local PostgreSQL")

    if url.database != "trd_bot":
        raise RuntimeError("monitoring demo seed may run only against the trd_bot database")

    return url


def get_demo_policy(
    candidate: ArchitectureCandidate,
) -> ArchitectureCheckpointPolicy:
    """Return one checkpoint policy labeled as demo data."""

    base_policy = next(
        policy for policy in default_checkpoint_policies() if policy.candidate is candidate
    )

    payload = base_policy.model_dump()

    payload["title"] = f"[DEMO] {base_policy.title}"

    payload["summary"] = f"Synthetic capacity-planning scenario. {base_policy.summary}"

    return ArchitectureCheckpointPolicy.model_validate(payload)


def save_metric_series(
    repository: SqlAlchemySystemMetricRepository,
    *,
    scenario_name: str,
    start_time: datetime,
    series: DemoMetricSeries,
) -> None:
    """Persist three deterministic metric windows."""

    for index, value in enumerate(series.values):
        recorded_at = start_time + timedelta(seconds=WINDOW_SECONDS * index)

        sample_id = build_metric_sample_id(
            metric_name=series.metric_name,
            source=series.source,
            recorded_at=recorded_at,
            window_seconds=WINDOW_SECONDS,
        )

        sample = SystemMetricSample(
            sample_id=sample_id,
            metric_name=series.metric_name,
            source=series.source,
            unit=METRIC_UNITS[series.metric_name],
            value=Decimal(value),
            recorded_at=recorded_at,
            window_seconds=WINDOW_SECONDS,
            observed_count=OBSERVED_COUNT,
            labels={
                "synthetic": "true",
                "scenario": scenario_name,
                "environment": "development",
            },
        )

        repository.save(sample)


def evaluate_scenario(
    *,
    evaluator: ArchitectureCheckpointEvaluator,
    scenario: DemoScenario,
) -> CheckpointEvaluationResult:
    """Evaluate a demo scenario after its final window."""

    evaluation_time = scenario.start_time + timedelta(
        seconds=(WINDOW_SECONDS * len(scenario.metric_series[0].values))
    )

    return evaluator.evaluate(
        policy=get_demo_policy(scenario.candidate),
        evaluated_at=evaluation_time,
    )


def print_result(
    scenario: DemoScenario,
    result: CheckpointEvaluationResult,
) -> None:
    """Print one concise demo scenario result."""

    print(f"{scenario.name}: {result.outcome.value}")

    if result.recommendation is not None:
        print(
            "  recommendation:",
            result.recommendation.recommendation_id,
        )
        print(
            "  severity:",
            result.recommendation.severity.value,
        )
        print(
            "  status:",
            result.recommendation.status.value,
        )


def main() -> None:
    """Seed deterministic monitoring metrics and recommendations."""

    settings = Settings()
    database_url = validate_seed_target(settings)

    print(
        "Seeding monitoring demo into:",
        database_url.render_as_string(hide_password=True),
    )

    engine = create_database_engine(
        settings.database_url,
        echo=settings.debug,
    )

    factory = create_session_factory(engine)

    try:
        with factory() as session:
            metric_repository = SqlAlchemySystemMetricRepository(session)

            recommendation_repository = SqlAlchemyArchitectureRecommendationRepository(session)

            evaluator = ArchitectureCheckpointEvaluator(
                metric_repository=(metric_repository),
                recommendation_repository=(recommendation_repository),
            )

            for scenario in DEMO_SCENARIOS:
                for series in scenario.metric_series:
                    save_metric_series(
                        metric_repository,
                        scenario_name=scenario.name,
                        start_time=(scenario.start_time),
                        series=series,
                    )

                result = evaluate_scenario(
                    evaluator=evaluator,
                    scenario=scenario,
                )

                print_result(
                    scenario,
                    result,
                )

    finally:
        engine.dispose()

    print()
    print("Expected demo state:")
    print("  metric samples: 21")
    print("  active recommendations: 3")
    print("  healthy scenarios: 1")
    print("Monitoring demo seed completed.")


if __name__ == "__main__":
    main()
