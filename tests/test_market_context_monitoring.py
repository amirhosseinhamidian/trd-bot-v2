from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.test_market_context_features import AS_OF, PAIR, SOURCE, complete_input
from trd_bot.api.dependencies import get_market_context_monitoring_reader
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyMarketContextEvaluationEnqueuer,
    SqlAlchemyMarketContextEvaluationRunner,
    SqlAlchemyMarketContextMonitoringReader,
    SqlAlchemyMarketDataEventStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.jobs import BackgroundJobStatus
from trd_bot.main import app
from trd_bot.market_context import (
    MarketContextBacklogSummary,
    MarketContextEvaluationJobPayload,
    MarketContextFreshnessStatus,
    MarketContextHealthIssueCode,
    MarketContextMonitoringOverallStatus,
    MarketContextMonitoringSummary,
    MarketContextStreamHealthStatus,
)

REQUESTED_AT = AS_OF + timedelta(minutes=5)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def _seed_successful_evaluation(factory: sessionmaker[Session]) -> None:
    windows, _ = complete_input()
    with factory.begin() as session:
        event_store = SqlAlchemyMarketDataEventStore(session)
        for window in windows:
            event_store.stage_window_version(window)

    with factory() as session:
        queued = (
            SqlAlchemyMarketContextEvaluationEnqueuer(session)
            .enqueue(
                source=SOURCE,
                pair=PAIR,
                as_of=AS_OF,
                requested_at=REQUESTED_AT,
            )
            .job
        )

    worker_id = "market-context-monitoring-test"
    with factory() as session:
        jobs = SqlAlchemyBackgroundJobRepository(session)
        claimed = jobs.claim_next(
            worker_id=worker_id,
            lease_duration=timedelta(minutes=1),
            now=REQUESTED_AT,
        )
        assert claimed is not None

    assessment = SqlAlchemyMarketContextEvaluationRunner(factory).run(
        MarketContextEvaluationJobPayload.model_validate(queued.payload)
    )
    with factory() as session:
        SqlAlchemyBackgroundJobRepository(session).succeed(
            job_id=queued.job_id,
            worker_id=worker_id,
            result_reference=assessment.assessment_id,
            now=REQUESTED_AT + timedelta(seconds=10),
        )


def test_reader_reports_no_data_without_discovered_streams(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        summary = SqlAlchemyMarketContextMonitoringReader(session).read(
            generated_at=AS_OF + timedelta(minutes=30)
        )

    assert summary.overall_status is MarketContextMonitoringOverallStatus.NO_DATA
    assert summary.stream_count == 0
    assert summary.streams == ()
    assert summary.backlog == MarketContextBacklogSummary(
        queued_jobs=0,
        running_jobs=0,
        retrying_jobs=0,
        failed_streams=0,
        expired_assessments=0,
        lagging_streams=0,
        missing_assessments=0,
    )


def test_reader_reports_current_ready_assessment_then_detects_expiry_and_boundary_lag(
    factory: sessionmaker[Session],
) -> None:
    _seed_successful_evaluation(factory)

    with factory() as session:
        fresh = SqlAlchemyMarketContextMonitoringReader(session).read(
            generated_at=AS_OF + timedelta(minutes=30)
        )
        stale = SqlAlchemyMarketContextMonitoringReader(session).read(
            generated_at=AS_OF + timedelta(hours=1, minutes=10)
        )

    assert fresh.overall_status is MarketContextMonitoringOverallStatus.HEALTHY
    assert fresh.healthy_count == 1
    assert fresh.streams[0].freshness_status is MarketContextFreshnessStatus.FRESH
    assert fresh.streams[0].health_status is MarketContextStreamHealthStatus.HEALTHY
    assert fresh.streams[0].latest_job_status is BackgroundJobStatus.SUCCEEDED
    assert fresh.streams[0].latest_job_progress_percent == 100
    assert fresh.streams[0].issue_codes == ()

    assert stale.overall_status is MarketContextMonitoringOverallStatus.CRITICAL
    assert stale.stale_count == 1
    assert stale.streams[0].boundary_lag_seconds == 3600
    assert stale.streams[0].issue_codes == (
        MarketContextHealthIssueCode.ASSESSMENT_EXPIRED,
        MarketContextHealthIssueCode.BOUNDARY_LAGGING,
    )


def test_reader_exposes_retry_backlog_and_sanitized_failure_state(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        queued = (
            SqlAlchemyMarketContextEvaluationEnqueuer(session)
            .enqueue(
                source=SOURCE,
                pair=PAIR,
                as_of=AS_OF,
                requested_at=REQUESTED_AT,
            )
            .job
        )
    with factory() as session:
        jobs = SqlAlchemyBackgroundJobRepository(session)
        claimed = jobs.claim_next(
            worker_id="retrying-context-worker",
            lease_duration=timedelta(minutes=1),
            now=REQUESTED_AT,
        )
        assert claimed is not None
        jobs.fail(
            job_id=queued.job_id,
            worker_id="retrying-context-worker",
            error_code="market_context_inputs_not_ready",
            error_message="sensitive upstream detail",
            retryable=True,
            retry_delay=timedelta(seconds=5),
            now=REQUESTED_AT + timedelta(seconds=1),
        )

    with factory() as session:
        summary = SqlAlchemyMarketContextMonitoringReader(session).read(
            generated_at=REQUESTED_AT + timedelta(seconds=2)
        )

    stream = summary.streams[0]
    serialized = summary.model_dump(mode="json")
    assert summary.overall_status is MarketContextMonitoringOverallStatus.CRITICAL
    assert summary.backlog.queued_jobs == 1
    assert summary.backlog.retrying_jobs == 1
    assert summary.backlog.missing_assessments == 1
    assert stream.health_status is MarketContextStreamHealthStatus.DEGRADED
    assert stream.latest_job_status is BackgroundJobStatus.QUEUED
    assert stream.issue_codes == (
        MarketContextHealthIssueCode.ASSESSMENT_MISSING,
        MarketContextHealthIssueCode.EVALUATION_RETRYING,
    )
    assert "payload" not in str(serialized)
    assert "worker" not in str(serialized)
    assert "sensitive upstream detail" not in str(serialized)


class StaticMarketContextMonitoringReader:
    def __init__(self, summary: MarketContextMonitoringSummary) -> None:
        self._summary = summary

    def read(self, *, generated_at: datetime | None = None) -> MarketContextMonitoringSummary:
        del generated_at
        return self._summary


@pytest.fixture
def market_context_api() -> Iterator[TestClient]:
    summary = MarketContextMonitoringSummary(
        generated_at=datetime(2026, 10, 16, 14, 30, tzinfo=UTC),
        overall_status=MarketContextMonitoringOverallStatus.NO_DATA,
        stream_count=0,
        healthy_count=0,
        degraded_count=0,
        stale_count=0,
        no_data_count=0,
        backlog=MarketContextBacklogSummary(
            queued_jobs=0,
            running_jobs=0,
            retrying_jobs=0,
            failed_streams=0,
            expired_assessments=0,
            lagging_streams=0,
            missing_assessments=0,
        ),
        streams=(),
    )
    app.dependency_overrides[get_market_context_monitoring_reader] = lambda: (
        StaticMarketContextMonitoringReader(summary)
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_market_context_monitoring_reader, None)


def test_api_exposes_read_only_market_context_monitoring_projection(
    market_context_api: TestClient,
) -> None:
    response = market_context_api.get("/api/v1/monitoring/market-context")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "market-context-monitoring-v1",
        "generated_at": "2026-10-16T14:30:00Z",
        "overall_status": "no_data",
        "stream_count": 0,
        "healthy_count": 0,
        "degraded_count": 0,
        "stale_count": 0,
        "no_data_count": 0,
        "backlog": {
            "queued_jobs": 0,
            "running_jobs": 0,
            "retrying_jobs": 0,
            "failed_streams": 0,
            "expired_assessments": 0,
            "lagging_streams": 0,
            "missing_assessments": 0,
        },
        "streams": [],
    }
    assert market_context_api.post("/api/v1/monitoring/market-context").status_code == 405
