from datetime import UTC, datetime
from decimal import Decimal

from trd_bot.db import (
    ArchitectureRecommendationRow,
    DatabaseBase,
    SystemMetricSampleRow,
    create_database_engine,
    create_session_factory,
)


def test_monitoring_rows_can_be_persisted() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    recorded_at = datetime(
        2026,
        8,
        24,
        10,
        tzinfo=UTC,
    )

    metric_row = SystemMetricSampleRow(
        sample_id=("metric-sample-0000000000000001"),
        recorded_at=recorded_at,
        metric_name="api_request_latency_p95",
        source="api",
        unit="seconds",
        value=Decimal("0.450"),
        window_seconds=300,
        observed_count=150,
        labels_json={
            "route": "/api/v1/research/overview",
        },
    )

    recommendation_row = ArchitectureRecommendationRow(
        recommendation_id=("recommendation-0000000000000001"),
        candidate="redis",
        severity="warning",
        status="active",
        first_detected_at=recorded_at,
        last_detected_at=recorded_at,
        payload_json=('{"interpretation":"capacity_planning_only"}'),
    )

    try:
        with factory.begin() as session:
            session.add_all(
                [
                    metric_row,
                    recommendation_row,
                ]
            )

        with factory() as session:
            stored_metric = session.get(
                SystemMetricSampleRow,
                metric_row.sample_id,
            )

            stored_recommendation = session.get(
                ArchitectureRecommendationRow,
                recommendation_row.recommendation_id,
            )

            assert stored_metric is not None
            assert stored_metric.metric_name == "api_request_latency_p95"
            assert stored_metric.labels_json["route"] == "/api/v1/research/overview"

            assert stored_recommendation is not None
            assert stored_recommendation.candidate == "redis"
    finally:
        engine.dispose()
