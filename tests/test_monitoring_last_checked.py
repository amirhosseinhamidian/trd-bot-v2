from datetime import UTC, datetime

from fastapi.testclient import TestClient

from trd_bot.api.dependencies import (
    get_architecture_recommendation_repository,
    get_monitoring_runtime_state_repository,
    get_system_metric_repository,
)
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyMonitoringRuntimeStateRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.monitoring_collector_runner import SqlAlchemyMonitoringCollectorRunner
from trd_bot.main import app
from trd_bot.monitoring import (
    InMemoryArchitectureRecommendationRepository,
    InMemoryMonitoringRuntimeStateRepository,
    InMemorySystemMetricRepository,
)

CHECKED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)


def test_collector_runner_persists_last_successful_check() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    runner = SqlAlchemyMonitoringCollectorRunner(
        session_factory=factory,
        observation_provider=lambda: (),
        policies=(),
        clock=lambda: CHECKED_AT,
    )

    try:
        result = runner.run_once()

        assert result.checked_at == CHECKED_AT

        with factory() as session:
            state = SqlAlchemyMonitoringRuntimeStateRepository(session).get()

        assert state.last_checked_at == CHECKED_AT
    finally:
        engine.dispose()


def test_monitoring_summary_exposes_persisted_last_checked_at() -> None:
    metrics = InMemorySystemMetricRepository()
    recommendations = InMemoryArchitectureRecommendationRepository()
    runtime_state = InMemoryMonitoringRuntimeStateRepository()

    app.dependency_overrides[get_system_metric_repository] = lambda: metrics
    app.dependency_overrides[get_architecture_recommendation_repository] = lambda: recommendations
    app.dependency_overrides[get_monitoring_runtime_state_repository] = lambda: runtime_state

    client = TestClient(app)

    try:
        before = client.get("/api/v1/monitoring/summary")
        assert before.status_code == 200
        assert before.json()["last_checked_at"] is None

        runtime_state.mark_checked(checked_at=CHECKED_AT)

        after = client.get("/api/v1/monitoring/summary")
        assert after.status_code == 200

        value = after.json()["last_checked_at"]
        assert value is not None
        assert datetime.fromisoformat(value.replace("Z", "+00:00")) == CHECKED_AT
    finally:
        app.dependency_overrides.pop(get_system_metric_repository, None)
        app.dependency_overrides.pop(
            get_architecture_recommendation_repository,
            None,
        )
        app.dependency_overrides.pop(
            get_monitoring_runtime_state_repository,
            None,
        )
