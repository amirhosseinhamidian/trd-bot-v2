from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trd_bot.db.models import BackgroundJobRow, MarketRegimeAssessmentRow
from trd_bot.domain.market_data import MarketType, Timeframe, TradingPair
from trd_bot.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextEvaluationJobPayload,
    MarketRegimeAssessment,
    floor_market_context_boundary,
)
from trd_bot.market_context.health import (
    MarketContextBacklogSummary,
    MarketContextFreshnessStatus,
    MarketContextHealthIssueCode,
    MarketContextMonitoringOverallStatus,
    MarketContextMonitoringSummary,
    MarketContextStreamHealth,
    MarketContextStreamHealthStatus,
)
from trd_bot.market_data.service_levels import (
    MarketDataServiceLevelPolicy,
    default_market_data_service_level_policy,
)

_MAX_RECORDS = 1_000
_MAX_STREAMS = 200
_StreamKey = tuple[str, str, str, str]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-context monitoring time must include timezone information")
    return value.astimezone(UTC)


def _stream_key(source: str, pair: TradingPair) -> _StreamKey:
    return (source, pair.base_asset, pair.quote_asset, pair.market_type.value)


class SqlAlchemyMarketContextMonitoringReader:
    """Build a bounded, sanitized projection from assessments and durable jobs."""

    def __init__(
        self,
        session: Session,
        *,
        policy: MarketDataServiceLevelPolicy | None = None,
    ) -> None:
        self._session = session
        self._policy = policy or default_market_data_service_level_policy()

    def read(self, *, generated_at: datetime | None = None) -> MarketContextMonitoringSummary:
        now = _as_utc(generated_at or datetime.now(UTC))
        expected_as_of = floor_market_context_boundary(now, Timeframe.HOUR_1)
        assessments = self._latest_assessments()
        jobs = self._latest_jobs()
        keys = tuple(sorted(set(assessments) | set(jobs)))[:_MAX_STREAMS]
        streams = tuple(
            self._stream_health(
                key=key,
                assessment=assessments.get(key),
                job=jobs.get(key),
                expected_as_of=expected_as_of,
                now=now,
            )
            for key in keys
        )
        backlog = self._backlog(streams)

        healthy_count = sum(
            stream.health_status is MarketContextStreamHealthStatus.HEALTHY for stream in streams
        )
        degraded_count = sum(
            stream.health_status is MarketContextStreamHealthStatus.DEGRADED for stream in streams
        )
        stale_count = sum(
            stream.freshness_status is MarketContextFreshnessStatus.STALE for stream in streams
        )
        no_data_count = sum(
            stream.freshness_status is MarketContextFreshnessStatus.NO_DATA for stream in streams
        )
        active_jobs = backlog.queued_jobs + backlog.running_jobs
        if not streams:
            overall = MarketContextMonitoringOverallStatus.NO_DATA
        elif active_jobs >= self._policy.capacity.queue_depth_overload or (
            degraded_count == len(streams)
        ):
            overall = MarketContextMonitoringOverallStatus.CRITICAL
        elif no_data_count == len(streams) and backlog.failed_streams == 0:
            overall = MarketContextMonitoringOverallStatus.NO_DATA
        elif (
            degraded_count > 0
            or stale_count > 0
            or no_data_count > 0
            or active_jobs > 0
            or backlog.retrying_jobs > 0
            or backlog.failed_streams > 0
        ):
            overall = MarketContextMonitoringOverallStatus.WARNING
        else:
            overall = MarketContextMonitoringOverallStatus.HEALTHY

        return MarketContextMonitoringSummary(
            generated_at=now,
            overall_status=overall,
            stream_count=len(streams),
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            stale_count=stale_count,
            no_data_count=no_data_count,
            backlog=backlog,
            streams=streams,
        )

    def _latest_assessments(self) -> dict[_StreamKey, MarketRegimeAssessment]:
        rows = self._session.scalars(
            select(MarketRegimeAssessmentRow)
            .order_by(
                MarketRegimeAssessmentRow.as_of.desc(),
                MarketRegimeAssessmentRow.assessed_at.desc(),
                MarketRegimeAssessmentRow.assessment_id.desc(),
            )
            .limit(_MAX_RECORDS)
        ).all()
        latest: dict[_StreamKey, MarketRegimeAssessment] = {}
        for row in rows:
            assessment = MarketRegimeAssessment.model_validate_json(row.payload_json)
            latest.setdefault(_stream_key(assessment.source, assessment.pair), assessment)
        return latest

    def _latest_jobs(self) -> dict[_StreamKey, BackgroundJob]:
        rows = self._session.scalars(
            select(BackgroundJobRow)
            .where(BackgroundJobRow.kind == BackgroundJobKind.MARKET_CONTEXT_EVALUATION.value)
            .order_by(BackgroundJobRow.created_at.desc(), BackgroundJobRow.job_id.desc())
            .limit(_MAX_RECORDS)
        ).all()
        latest: dict[_StreamKey, BackgroundJob] = {}
        for row in rows:
            try:
                job = BackgroundJob.model_validate_json(row.payload_json)
                payload = MarketContextEvaluationJobPayload.model_validate(job.payload)
            except (ValidationError, ValueError):
                continue
            latest.setdefault(_stream_key(payload.source, payload.pair), job)
        return latest

    def _stream_health(
        self,
        *,
        key: _StreamKey,
        assessment: MarketRegimeAssessment | None,
        job: BackgroundJob | None,
        expected_as_of: datetime,
        now: datetime,
    ) -> MarketContextStreamHealth:
        source, base_asset, quote_asset, market_type = key
        pair = TradingPair(
            base_asset=base_asset,
            quote_asset=quote_asset,
            market_type=MarketType(market_type),
        )
        issues: set[MarketContextHealthIssueCode] = set()

        if assessment is None:
            freshness = MarketContextFreshnessStatus.NO_DATA
            issues.add(MarketContextHealthIssueCode.ASSESSMENT_MISSING)
            assessment_age_seconds = None
            boundary_lag_seconds = None
        else:
            assessment_age_seconds = max(0, int((now - assessment.assessed_at).total_seconds()))
            boundary_lag_seconds = max(
                0,
                int((expected_as_of - assessment.as_of).total_seconds()),
            )
            fresh = (
                assessment.status is MarketContextAssessmentStatus.READY
                and assessment.as_of == expected_as_of
                and assessment.expires_at > now
            )
            freshness = (
                MarketContextFreshnessStatus.FRESH if fresh else MarketContextFreshnessStatus.STALE
            )
            if assessment.status is not MarketContextAssessmentStatus.READY:
                issues.add(MarketContextHealthIssueCode.ASSESSMENT_NOT_READY)
            if assessment.expires_at <= now:
                issues.add(MarketContextHealthIssueCode.ASSESSMENT_EXPIRED)
            if assessment.as_of != expected_as_of:
                issues.add(MarketContextHealthIssueCode.BOUNDARY_LAGGING)

        payload: MarketContextEvaluationJobPayload | None = None
        if job is not None:
            payload = MarketContextEvaluationJobPayload.model_validate(job.payload)
            if job.status is BackgroundJobStatus.FAILED:
                issues.add(MarketContextHealthIssueCode.EVALUATION_FAILED)
            elif job.status in {BackgroundJobStatus.QUEUED, BackgroundJobStatus.RUNNING}:
                issues.add(
                    MarketContextHealthIssueCode.EVALUATION_RETRYING
                    if job.attempt_count > 0
                    else MarketContextHealthIssueCode.EVALUATION_PENDING
                )

        if (
            freshness is MarketContextFreshnessStatus.STALE
            or MarketContextHealthIssueCode.EVALUATION_FAILED in issues
            or MarketContextHealthIssueCode.EVALUATION_RETRYING in issues
        ):
            health = MarketContextStreamHealthStatus.DEGRADED
        elif freshness is MarketContextFreshnessStatus.NO_DATA:
            health = MarketContextStreamHealthStatus.NO_DATA
        else:
            health = MarketContextStreamHealthStatus.HEALTHY

        return MarketContextStreamHealth(
            source=source,
            pair=pair,
            health_status=health,
            freshness_status=freshness,
            issue_codes=tuple(sorted(issues, key=lambda item: item.value)),
            expected_as_of=expected_as_of,
            latest_assessment_id=None if assessment is None else assessment.assessment_id,
            latest_assessment_status=None if assessment is None else assessment.status,
            latest_assessment_as_of=None if assessment is None else assessment.as_of,
            assessed_at=None if assessment is None else assessment.assessed_at,
            expires_at=None if assessment is None else assessment.expires_at,
            assessment_age_seconds=assessment_age_seconds,
            boundary_lag_seconds=boundary_lag_seconds,
            feature_set_version=None if assessment is None else assessment.feature_set_version,
            algorithm_version=None if assessment is None else assessment.algorithm_version,
            latest_job_id=None if job is None else job.job_id,
            latest_job_status=None if job is None else job.status,
            latest_job_as_of=None if payload is None else payload.as_of,
            latest_job_updated_at=None if job is None else job.updated_at,
            latest_job_progress_percent=None if job is None else job.progress_percent,
            latest_job_attempt_count=None if job is None else job.attempt_count,
            latest_job_max_attempts=None if job is None else job.max_attempts,
            latest_job_error_code=None if job is None else job.error_code,
        )

    def _backlog(
        self,
        streams: tuple[MarketContextStreamHealth, ...],
    ) -> MarketContextBacklogSummary:
        def count_jobs(status: BackgroundJobStatus) -> int:
            return int(
                self._session.scalar(
                    select(func.count())
                    .select_from(BackgroundJobRow)
                    .where(
                        BackgroundJobRow.kind == BackgroundJobKind.MARKET_CONTEXT_EVALUATION.value,
                        BackgroundJobRow.status == status.value,
                    )
                )
                or 0
            )

        retrying_jobs = int(
            self._session.scalar(
                select(func.count())
                .select_from(BackgroundJobRow)
                .where(
                    BackgroundJobRow.kind == BackgroundJobKind.MARKET_CONTEXT_EVALUATION.value,
                    BackgroundJobRow.status == BackgroundJobStatus.QUEUED.value,
                    BackgroundJobRow.attempt_count > 0,
                )
            )
            or 0
        )
        return MarketContextBacklogSummary(
            queued_jobs=count_jobs(BackgroundJobStatus.QUEUED),
            running_jobs=count_jobs(BackgroundJobStatus.RUNNING),
            retrying_jobs=retrying_jobs,
            failed_streams=sum(
                stream.latest_job_status is BackgroundJobStatus.FAILED for stream in streams
            ),
            expired_assessments=sum(
                MarketContextHealthIssueCode.ASSESSMENT_EXPIRED in stream.issue_codes
                for stream in streams
            ),
            lagging_streams=sum(
                MarketContextHealthIssueCode.BOUNDARY_LAGGING in stream.issue_codes
                for stream in streams
            ),
            missing_assessments=sum(
                stream.freshness_status is MarketContextFreshnessStatus.NO_DATA
                for stream in streams
            ),
        )
