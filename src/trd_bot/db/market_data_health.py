from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.market_data_connection_repositories import (
    SqlAlchemyMarketDataConnectionRepository,
)
from trd_bot.db.market_data_event_repositories import SqlAlchemyMarketDataEventStore
from trd_bot.db.models import (
    BackgroundJobRow,
    MarketDataEventDecisionRow,
    MarketDataPollRunRow,
    MarketDataReplayRequestRow,
    MarketDataWatchlistRow,
    MarketDataWindowRevisionRow,
    MarketDataWindowVersionRow,
)
from trd_bot.jobs import BackgroundJobKind, BackgroundJobStatus
from trd_bot.market_data.connections import (
    MarketDataConnectionHealth,
    MarketDataConnectionState,
)
from trd_bot.market_data.events import MarketDataWindowSnapshot, MarketDataWindowState
from trd_bot.market_data.health import (
    MarketDataBacklogSummary,
    MarketDataFreshnessStatus,
    MarketDataMonitoringOverallStatus,
    MarketDataMonitoringSummary,
    MarketDataProviderRouteHealth,
    MarketDataReplayHealth,
    MarketDataStreamHealth,
    MarketDataStreamHealthStatus,
)
from trd_bot.market_data.polling import (
    MarketDataPollRun,
    MarketDataPollRunStatus,
    MarketDataWatchlistEntry,
    MarketDataWatchlistState,
)
from trd_bot.market_data.replay import MarketDataReplayRequest, MarketDataWindowRevision
from trd_bot.market_data.replay_jobs import build_market_data_replay_idempotency_key
from trd_bot.market_data.service_levels import (
    MarketDataServiceLevelPolicy,
    default_market_data_service_level_policy,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-data monitoring time must include timezone information")
    return value.astimezone(UTC)


class SqlAlchemyMarketDataMonitoringReader:
    """Build one bounded read-only projection from durable market-data state."""

    def __init__(
        self,
        session: Session,
        *,
        policy: MarketDataServiceLevelPolicy | None = None,
    ) -> None:
        self._session = session
        self._policy = policy or default_market_data_service_level_policy()
        self._events = SqlAlchemyMarketDataEventStore(session)
        self._connections = SqlAlchemyMarketDataConnectionRepository(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def read(self, *, generated_at: datetime | None = None) -> MarketDataMonitoringSummary:
        now = _as_utc(generated_at or datetime.now(UTC))
        entries = self._watchlist_entries()
        streams = tuple(self._stream_health(entry, now=now) for entry in entries)
        backlog = self._backlog(streams=streams, now=now)
        recent_replays = self._recent_replays(limit=20)

        healthy_count = sum(
            item.health_status is MarketDataStreamHealthStatus.HEALTHY for item in streams
        )
        degraded_count = sum(
            item.health_status is MarketDataStreamHealthStatus.DEGRADED for item in streams
        )
        stale_count = sum(
            item.freshness_status is MarketDataFreshnessStatus.STALE for item in streams
        )
        no_data_count = sum(
            item.freshness_status is MarketDataFreshnessStatus.NO_DATA for item in streams
        )
        paused_count = sum(
            item.health_status is MarketDataStreamHealthStatus.PAUSED for item in streams
        )
        active_streams = tuple(
            item
            for item in streams
            if item.health_status is not MarketDataStreamHealthStatus.PAUSED
        )
        active_count = len(active_streams)
        active_no_data_count = sum(
            item.freshness_status is MarketDataFreshnessStatus.NO_DATA for item in active_streams
        )
        queue_depth = backlog.poll_jobs + backlog.replay_jobs
        if not active_streams or active_no_data_count == active_count:
            overall = MarketDataMonitoringOverallStatus.NO_DATA
        elif queue_depth >= self._policy.capacity.queue_depth_overload or (
            active_count > 0 and degraded_count == active_count
        ):
            overall = MarketDataMonitoringOverallStatus.CRITICAL
        elif (
            degraded_count > 0
            or stale_count > 0
            or no_data_count > 0
            or backlog.poll_jobs > 0
            or backlog.replay_jobs > 0
            or backlog.overdue_watchlists > 0
            or backlog.finalization_windows > 0
            or backlog.unrequested_revisions > 0
            or backlog.pending_replays > 0
            or backlog.failed_replays > 0
        ):
            overall = MarketDataMonitoringOverallStatus.WARNING
        else:
            overall = MarketDataMonitoringOverallStatus.HEALTHY

        return MarketDataMonitoringSummary(
            generated_at=now,
            overall_status=overall,
            stream_count=len(streams),
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            stale_count=stale_count,
            no_data_count=no_data_count,
            paused_count=paused_count,
            backlog=backlog,
            streams=streams,
            recent_replays=recent_replays,
        )

    def _watchlist_entries(self) -> tuple[MarketDataWatchlistEntry, ...]:
        rows = self._session.scalars(
            select(MarketDataWatchlistRow)
            .order_by(
                MarketDataWatchlistRow.created_at,
                MarketDataWatchlistRow.watchlist_id,
            )
            .limit(200)
        ).all()
        return tuple(MarketDataWatchlistEntry.model_validate_json(row.payload_json) for row in rows)

    def _stream_health(
        self,
        entry: MarketDataWatchlistEntry,
        *,
        now: datetime,
    ) -> MarketDataStreamHealth:
        service_level = self._policy.for_timeframe(entry.timeframe)
        latest_poll = self._latest_poll(entry.watchlist_id)
        latest_success = self._latest_successful_poll(entry.watchlist_id)
        finalized = self._latest_finalized_window(entry)
        selected_provider = None if latest_success is None else latest_success.selected_provider_id
        if finalized is not None:
            selected_provider = finalized.source

        watermark_time: datetime | None = None
        if selected_provider is not None:
            watermark = self._events.get_latest_watermark(
                source=selected_provider,
                pair=entry.pair,
                timeframe=entry.timeframe,
            )
            if watermark is not None:
                watermark_time = watermark.watermark.watermark_time

        route_health = tuple(
            self._route_health(
                ordinal=ordinal,
                provider_id=route.provider_id,
                connection_id=route.connection_id,
            )
            for ordinal, route in enumerate(entry.routes, start=1)
        )
        any_usable_route = any(
            item.connection_state is MarketDataConnectionState.ENABLED
            and item.health_status is MarketDataConnectionHealth.HEALTHY
            for item in route_health
        )

        if finalized is None:
            freshness = MarketDataFreshnessStatus.NO_DATA
            data_age_seconds = None
            lag_seconds = None
        else:
            data_age_seconds = max(0, int((now - finalized.window_end).total_seconds()))
            timeframe_seconds = int(entry.timeframe.duration.total_seconds())
            lag_seconds = max(0, data_age_seconds - timeframe_seconds)
            freshness = (
                MarketDataFreshnessStatus.FRESH
                if lag_seconds <= service_level.finalized_freshness_p95_seconds
                else MarketDataFreshnessStatus.STALE
            )

        poll_overdue_seconds = (
            max(0, int((now - entry.next_poll_at).total_seconds()))
            if entry.state is MarketDataWatchlistState.ACTIVE
            else 0
        )
        finalization_backlog = self._finalization_backlog(entry)
        if entry.state is MarketDataWatchlistState.PAUSED:
            health = MarketDataStreamHealthStatus.PAUSED
        elif (
            not any_usable_route
            or (latest_poll is not None and latest_poll.status is MarketDataPollRunStatus.FAILED)
            or freshness is MarketDataFreshnessStatus.STALE
            or poll_overdue_seconds > entry.polling_interval_seconds
            or finalization_backlog > 0
        ):
            health = MarketDataStreamHealthStatus.DEGRADED
        elif freshness is MarketDataFreshnessStatus.NO_DATA:
            health = MarketDataStreamHealthStatus.NO_DATA
        else:
            health = MarketDataStreamHealthStatus.HEALTHY

        return MarketDataStreamHealth(
            watchlist_id=entry.watchlist_id,
            pair=entry.pair,
            timeframe=entry.timeframe,
            watchlist_state=entry.state,
            health_status=health,
            freshness_status=freshness,
            provider_routes=route_health,
            selected_provider_id=selected_provider,
            latest_poll_status=None if latest_poll is None else latest_poll.status,
            latest_poll_completed_at=(None if latest_poll is None else latest_poll.completed_at),
            latest_poll_error_code=(None if latest_poll is None else latest_poll.failure_code),
            latest_finalized_window_end=(None if finalized is None else finalized.window_end),
            latest_watermark_time=watermark_time,
            data_age_seconds=data_age_seconds,
            lag_seconds=lag_seconds,
            freshness_target_seconds=service_level.finalized_freshness_p95_seconds,
            poll_overdue_seconds=poll_overdue_seconds,
            finalization_backlog_count=finalization_backlog,
        )

    def _route_health(
        self,
        *,
        ordinal: int,
        provider_id: str,
        connection_id: str,
    ) -> MarketDataProviderRouteHealth:
        connection = self._connections.get(connection_id)
        return MarketDataProviderRouteHealth(
            ordinal=ordinal,
            provider_id=provider_id,
            connection_id=connection_id,
            connection_state=None if connection is None else connection.state,
            health_status=None if connection is None else connection.health_status,
            last_tested_at=None if connection is None else connection.last_tested_at,
            last_error_code=(
                None
                if connection is None or connection.last_error_code is None
                else connection.last_error_code.value
            ),
        )

    def _latest_poll(self, watchlist_id: str) -> MarketDataPollRun | None:
        row = self._session.scalar(
            select(MarketDataPollRunRow)
            .where(MarketDataPollRunRow.watchlist_id == watchlist_id)
            .order_by(MarketDataPollRunRow.completed_at.desc(), MarketDataPollRunRow.run_id.desc())
            .limit(1)
        )
        return None if row is None else MarketDataPollRun.model_validate_json(row.payload_json)

    def _latest_successful_poll(self, watchlist_id: str) -> MarketDataPollRun | None:
        row = self._session.scalar(
            select(MarketDataPollRunRow)
            .where(
                MarketDataPollRunRow.watchlist_id == watchlist_id,
                MarketDataPollRunRow.status == MarketDataPollRunStatus.SUCCEEDED.value,
            )
            .order_by(MarketDataPollRunRow.completed_at.desc(), MarketDataPollRunRow.run_id.desc())
            .limit(1)
        )
        return None if row is None else MarketDataPollRun.model_validate_json(row.payload_json)

    def _latest_finalized_window(
        self,
        entry: MarketDataWatchlistEntry,
    ) -> MarketDataWindowSnapshot | None:
        provider_ids = tuple(route.provider_id for route in entry.routes)
        row = self._session.scalar(
            select(MarketDataWindowVersionRow)
            .where(
                MarketDataWindowVersionRow.source.in_(provider_ids),
                MarketDataWindowVersionRow.base_asset == entry.pair.base_asset,
                MarketDataWindowVersionRow.quote_asset == entry.pair.quote_asset,
                MarketDataWindowVersionRow.market_type == entry.pair.market_type.value,
                MarketDataWindowVersionRow.timeframe == entry.timeframe.value,
                MarketDataWindowVersionRow.state == MarketDataWindowState.FINALIZED.value,
            )
            .order_by(
                MarketDataWindowVersionRow.window_end.desc(),
                MarketDataWindowVersionRow.version.desc(),
            )
            .limit(1)
        )
        return (
            None if row is None else MarketDataWindowSnapshot.model_validate_json(row.payload_json)
        )

    def _finalization_backlog(self, entry: MarketDataWatchlistEntry) -> int:
        count = 0
        for route in entry.routes:
            watermark = self._events.get_latest_watermark(
                source=route.provider_id,
                pair=entry.pair,
                timeframe=entry.timeframe,
            )
            if watermark is None:
                continue
            count += len(
                self._events.list_finalization_candidate_ids(
                    source=route.provider_id,
                    pair=entry.pair,
                    timeframe=entry.timeframe,
                    watermark_time=watermark.watermark.watermark_time,
                    limit=500,
                )
            )
        return count

    def _backlog(
        self,
        *,
        streams: tuple[MarketDataStreamHealth, ...],
        now: datetime,
    ) -> MarketDataBacklogSummary:
        active_statuses = (
            BackgroundJobStatus.QUEUED.value,
            BackgroundJobStatus.RUNNING.value,
        )
        poll_jobs = self._job_count(BackgroundJobKind.MARKET_DATA_POLL, active_statuses)
        replay_jobs = self._job_count(BackgroundJobKind.MARKET_DATA_REPLAY, active_statuses)
        failed_replays = self._job_count(
            BackgroundJobKind.MARKET_DATA_REPLAY,
            (BackgroundJobStatus.FAILED.value,),
        )
        overdue_watchlists = int(
            self._session.scalar(
                select(func.count())
                .select_from(MarketDataWatchlistRow)
                .where(
                    MarketDataWatchlistRow.state == MarketDataWatchlistState.ACTIVE.value,
                    MarketDataWatchlistRow.next_poll_at <= now,
                )
            )
            or 0
        )
        unrequested_revisions = int(
            self._session.scalar(
                select(func.count())
                .select_from(MarketDataEventDecisionRow)
                .outerjoin(
                    MarketDataReplayRequestRow,
                    MarketDataReplayRequestRow.decision_id
                    == MarketDataEventDecisionRow.decision_id,
                )
                .where(
                    MarketDataEventDecisionRow.requires_replay.is_(True),
                    MarketDataReplayRequestRow.replay_id.is_(None),
                )
            )
            or 0
        )
        pending_replays = int(
            self._session.scalar(
                select(func.count())
                .select_from(MarketDataReplayRequestRow)
                .outerjoin(
                    MarketDataWindowRevisionRow,
                    MarketDataWindowRevisionRow.replay_id == MarketDataReplayRequestRow.replay_id,
                )
                .where(MarketDataWindowRevisionRow.revision_id.is_(None))
            )
            or 0
        )
        completed_revisions = int(
            self._session.scalar(select(func.count()).select_from(MarketDataWindowRevisionRow)) or 0
        )
        return MarketDataBacklogSummary(
            poll_jobs=poll_jobs,
            replay_jobs=replay_jobs,
            overdue_watchlists=overdue_watchlists,
            finalization_windows=sum(item.finalization_backlog_count for item in streams),
            unrequested_revisions=unrequested_revisions,
            pending_replays=pending_replays,
            failed_replays=failed_replays,
            completed_revisions=completed_revisions,
        )

    def _job_count(self, kind: BackgroundJobKind, statuses: tuple[str, ...]) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(BackgroundJobRow)
                .where(
                    BackgroundJobRow.kind == kind.value,
                    BackgroundJobRow.status.in_(statuses),
                )
            )
            or 0
        )

    def _recent_replays(self, *, limit: int) -> tuple[MarketDataReplayHealth, ...]:
        rows = self._session.scalars(
            select(MarketDataReplayRequestRow)
            .order_by(
                MarketDataReplayRequestRow.requested_at.desc(),
                MarketDataReplayRequestRow.replay_id.desc(),
            )
            .limit(limit)
        ).all()
        items: list[MarketDataReplayHealth] = []
        for row in rows:
            request = MarketDataReplayRequest.model_validate_json(row.payload_json)
            job = self._jobs.get_by_idempotency_key(
                kind=BackgroundJobKind.MARKET_DATA_REPLAY,
                idempotency_key=build_market_data_replay_idempotency_key(request.decision_id),
            )
            if job is None:
                continue
            revision_row = self._session.scalar(
                select(MarketDataWindowRevisionRow).where(
                    MarketDataWindowRevisionRow.replay_id == request.replay_id
                )
            )
            revision = (
                None
                if revision_row is None
                else MarketDataWindowRevision.model_validate_json(revision_row.payload_json)
            )
            items.append(
                MarketDataReplayHealth(
                    replay_id=request.replay_id,
                    decision_id=request.decision_id,
                    window_id=request.window_id,
                    reason=request.reason,
                    requested_by=request.requested_by,
                    requested_at=request.requested_at,
                    job_id=job.job_id,
                    job_status=job.status,
                    error_code=job.error_code,
                    revision_id=None if revision is None else revision.revision_id,
                    revision_kind=None if revision is None else revision.kind,
                    revised_version=None if revision is None else revision.revised_version,
                    completed_at=None if revision is None else revision.applied_at,
                )
            )
        return tuple(items)
