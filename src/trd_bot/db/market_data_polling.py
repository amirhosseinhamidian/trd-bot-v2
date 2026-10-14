import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.market_data_connection_repositories import (
    SqlAlchemyMarketDataConnectionRepository,
)
from trd_bot.db.market_data_event_repositories import SqlAlchemyMarketDataEventStore
from trd_bot.db.market_data_ingestion import SqlAlchemyMarketDataIngestor
from trd_bot.db.models import (
    MarketDataPollRunRow,
    MarketDataProviderBudgetRow,
    MarketDataWatchlistRow,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.jobs import BackgroundJob, BackgroundJobBuilder, BackgroundJobKind
from trd_bot.market_data.connections import (
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataProviderCatalog,
)
from trd_bot.market_data.events import (
    MarketDataEvent,
    MarketDataEventDisposition,
    MarketDataWatermark,
)
from trd_bot.market_data.polling import (
    MarketDataPollAttempt,
    MarketDataPollAttemptOutcome,
    MarketDataPollingFailedError,
    MarketDataPollJobPayload,
    MarketDataPollRun,
    MarketDataPollRunStatus,
    MarketDataWatchlistEntry,
    MarketDataWatchlistRoute,
    MarketDataWatchlistState,
)
from trd_bot.market_data.providers import MarketDataProviderError
from trd_bot.market_data.quality import MarketDataQualityChecker
from trd_bot.market_data.service_levels import (
    MarketDataServiceLevelPolicy,
    ProviderRequestBudget,
    default_market_data_service_level_policy,
)
from trd_bot.market_data.storage import (
    MarketDataRawObservation,
    VersionedMarketDataWatermark,
)

PollingClock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyMarketDataWatchlistRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, entry: MarketDataWatchlistEntry) -> MarketDataWatchlistEntry:
        self.stage(entry)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValueError("market-data watchlist entry could not be persisted") from error
        return entry

    def stage(self, entry: MarketDataWatchlistEntry) -> None:
        row = self._session.get(MarketDataWatchlistRow, entry.watchlist_id)
        if row is None:
            row = MarketDataWatchlistRow(watchlist_id=entry.watchlist_id)
            self._session.add(row)
        self._update_row(row, entry)
        self._session.flush()

    def get(self, watchlist_id: str) -> MarketDataWatchlistEntry | None:
        row = self._session.get(MarketDataWatchlistRow, watchlist_id)
        return None if row is None else self._to_model(row)

    def list_due(
        self,
        *,
        now: datetime,
        limit: int,
        for_update: bool = False,
    ) -> tuple[MarketDataWatchlistEntry, ...]:
        if limit <= 0 or limit > 100:
            raise ValueError("watchlist due limit must be between 1 and 100")
        normalized = _as_utc(now)
        statement = (
            select(MarketDataWatchlistRow)
            .where(
                MarketDataWatchlistRow.state == MarketDataWatchlistState.ACTIVE.value,
                MarketDataWatchlistRow.next_poll_at <= normalized,
            )
            .order_by(
                MarketDataWatchlistRow.next_poll_at,
                MarketDataWatchlistRow.watchlist_id,
            )
            .limit(limit)
        )
        if for_update:
            statement = statement.with_for_update(skip_locked=True)
        rows = self._session.scalars(statement).all()
        return tuple(self._to_model(row) for row in rows)

    @staticmethod
    def _to_model(row: MarketDataWatchlistRow) -> MarketDataWatchlistEntry:
        return MarketDataWatchlistEntry.model_validate_json(row.payload_json)

    @staticmethod
    def _update_row(
        row: MarketDataWatchlistRow,
        entry: MarketDataWatchlistEntry,
    ) -> None:
        row.schema_version = entry.schema_version
        row.base_asset = entry.pair.base_asset
        row.quote_asset = entry.pair.quote_asset
        row.market_type = entry.pair.market_type.value
        row.timeframe = entry.timeframe.value
        row.state = entry.state.value
        row.policy_version = entry.policy_version
        row.polling_interval_seconds = entry.polling_interval_seconds
        row.lookback_candles = entry.lookback_candles
        row.next_poll_at = entry.next_poll_at
        row.last_enqueued_for = entry.last_enqueued_for
        row.last_job_id = entry.last_job_id
        row.payload_json = entry.model_dump_json()
        row.created_at = entry.created_at
        row.updated_at = entry.updated_at


class SqlAlchemyMarketDataWatchlistManager:
    """Create and control watchlist entries with the frozen provider order."""

    def __init__(
        self,
        *,
        session: Session,
        providers: MarketDataProviderCatalog,
        policy: MarketDataServiceLevelPolicy | None = None,
        clock: PollingClock = utc_now,
    ) -> None:
        self._session = session
        self._repository = SqlAlchemyMarketDataWatchlistRepository(session)
        self._connections = SqlAlchemyMarketDataConnectionRepository(session)
        self._providers = providers
        self._policy = policy or default_market_data_service_level_policy()
        self._clock = clock

    def create(
        self,
        *,
        pair: TradingPair,
        timeframe: Timeframe,
        kraken_connection_id: str,
        binance_connection_id: str,
        lookback_candles: int = 3,
    ) -> MarketDataWatchlistEntry:
        routes = (
            self._validated_route(kraken_connection_id, "kraken-public", pair, timeframe),
            self._validated_route(binance_connection_id, "binance-public", pair, timeframe),
        )
        service_level = self._policy.for_timeframe(timeframe)
        entry = MarketDataWatchlistEntry.build(
            pair=pair,
            timeframe=timeframe,
            routes=routes,
            polling_interval_seconds=service_level.polling_interval_seconds,
            lookback_candles=lookback_candles,
            now=self._now(),
        )
        return self._repository.save(entry)

    def pause(self, watchlist_id: str) -> MarketDataWatchlistEntry:
        return self._set_state(watchlist_id, MarketDataWatchlistState.PAUSED)

    def resume(self, watchlist_id: str) -> MarketDataWatchlistEntry:
        return self._set_state(watchlist_id, MarketDataWatchlistState.ACTIVE)

    def _set_state(
        self,
        watchlist_id: str,
        state: MarketDataWatchlistState,
    ) -> MarketDataWatchlistEntry:
        entry = self._repository.get(watchlist_id)
        if entry is None:
            raise KeyError(watchlist_id)
        now = self._now()
        if entry.state is state:
            return entry
        update: dict[str, object] = {"state": state, "updated_at": now}
        if state is MarketDataWatchlistState.ACTIVE:
            update["next_poll_at"] = now
        updated = MarketDataWatchlistEntry.model_validate(
            entry.model_copy(update=update).model_dump()
        )
        return self._repository.save(updated)

    def _validated_route(
        self,
        connection_id: str,
        provider_id: str,
        pair: TradingPair,
        timeframe: Timeframe,
    ) -> MarketDataWatchlistRoute:
        connection = self._connections.get(connection_id)
        if connection is None:
            raise ValueError("watchlist connection does not exist")
        if connection.provider_id != provider_id:
            raise ValueError("watchlist connection does not match the required provider order")
        if (
            connection.state is not MarketDataConnectionState.ENABLED
            or connection.health_status is not MarketDataConnectionHealth.HEALTHY
        ):
            raise ValueError("watchlist connections must be enabled and healthy")
        metadata = self._providers.get_metadata(provider_id)
        if metadata is None or metadata.requires_credentials:
            raise ValueError("watchlist provider must be an allowlisted public adapter")
        if (
            pair.market_type not in metadata.supported_market_types
            or timeframe not in metadata.supported_timeframes
        ):
            raise ValueError("watchlist stream is not supported by provider")
        self._policy.for_provider(provider_id)
        return MarketDataWatchlistRoute(
            connection_id=connection_id,
            provider_id=provider_id,
        )

    def _now(self) -> datetime:
        return _as_utc(self._clock())


class SqlAlchemyMarketDataPollingScheduler:
    """Atomically enqueue due watchlist slots and advance their cadence."""

    def __init__(
        self,
        session: Session,
        *,
        builder: BackgroundJobBuilder | None = None,
    ) -> None:
        self._session = session
        self._watchlist = SqlAlchemyMarketDataWatchlistRepository(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)
        self._builder = builder or BackgroundJobBuilder()

    def enqueue_due(
        self,
        *,
        now: datetime,
        limit: int = 25,
    ) -> tuple[BackgroundJob, ...]:
        normalized = _as_utc(now)
        entries = self._watchlist.list_due(
            now=normalized,
            limit=limit,
            for_update=True,
        )
        jobs: list[BackgroundJob] = []
        try:
            for entry in entries:
                scheduled_for = entry.next_poll_at
                payload = MarketDataPollJobPayload(
                    watchlist_id=entry.watchlist_id,
                    scheduled_for=scheduled_for,
                )
                job = self._builder.build(
                    kind=BackgroundJobKind.MARKET_DATA_POLL,
                    payload=payload.model_dump(mode="json"),
                    idempotency_key=(
                        f"market-data-poll:{entry.watchlist_id}:{scheduled_for.isoformat()}"
                    ),
                    now=normalized,
                )
                stored, _ = self._jobs.stage(job)
                self._watchlist.stage(
                    entry.mark_enqueued(
                        job_id=stored.job_id,
                        enqueued_at=normalized,
                    )
                )
                jobs.append(stored)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return tuple(jobs)


@dataclass(frozen=True, slots=True)
class ProviderBudgetDecision:
    acquired: bool
    retry_after_seconds: int


class SqlAlchemyProviderRequestBudgetGate:
    """Transactional token bucket enforcing the frozen provider request budget."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def acquire(
        self,
        *,
        budget: ProviderRequestBudget,
        now: datetime,
    ) -> ProviderBudgetDecision:
        normalized = _as_utc(now)
        for insert_attempt in range(2):
            row = self._session.scalar(
                select(MarketDataProviderBudgetRow)
                .where(MarketDataProviderBudgetRow.provider_id == budget.provider_id)
                .with_for_update()
            )
            if row is not None:
                break
            self._session.add(
                MarketDataProviderBudgetRow(
                    provider_id=budget.provider_id,
                    tokens=Decimal(budget.burst_requests - 1),
                    refilled_at=normalized,
                    updated_at=normalized,
                )
            )
            try:
                self._session.commit()
            except IntegrityError:
                self._session.rollback()
                if insert_attempt == 1:
                    raise
                continue
            return ProviderBudgetDecision(acquired=True, retry_after_seconds=0)
        else:
            raise AssertionError("provider budget initialization did not return")

        elapsed_seconds = max(
            Decimal("0"),
            Decimal(str((normalized - _as_utc(row.refilled_at)).total_seconds())),
        )
        refill_per_second = Decimal(budget.sustained_requests_per_minute) / Decimal(60)
        tokens = min(
            Decimal(budget.burst_requests),
            Decimal(row.tokens) + (elapsed_seconds * refill_per_second),
        )
        acquired = tokens >= Decimal("1")
        if acquired:
            tokens -= Decimal("1")
            retry_after = 0
        else:
            retry_after = max(
                1,
                math.ceil(float((Decimal("1") - tokens) / refill_per_second)),
            )
        row.tokens = tokens
        row.refilled_at = normalized
        row.updated_at = normalized
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return ProviderBudgetDecision(
            acquired=acquired,
            retry_after_seconds=retry_after,
        )


class SqlAlchemyMarketDataPollRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, run: MarketDataPollRun) -> MarketDataPollRun:
        existing = self.get(run.run_id)
        if existing is not None:
            if existing != run:
                raise ValueError("poll run ID already exists with different content")
            return existing
        self._session.add(
            MarketDataPollRunRow(
                run_id=run.run_id,
                schema_version=run.schema_version,
                job_id=run.job_id,
                job_attempt=run.job_attempt,
                watchlist_id=run.watchlist_id,
                scheduled_for=run.scheduled_for,
                status=run.status.value,
                attempt_count=len(run.attempts),
                selected_connection_id=run.selected_connection_id,
                selected_provider_id=run.selected_provider_id,
                received_candles=run.received_candles,
                accepted_events=run.accepted_events,
                duplicate_events=run.duplicate_events,
                revision_required_events=run.revision_required_events,
                watermark_before_id=run.watermark_before_id,
                watermark_after_id=run.watermark_after_id,
                failure_retryable=run.failure_retryable,
                failure_code=run.failure_code,
                failure_message=run.failure_message,
                payload_json=run.model_dump_json(),
                started_at=run.started_at,
                completed_at=run.completed_at,
            )
        )
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            existing = self.get_by_job_attempt(
                job_id=run.job_id,
                job_attempt=run.job_attempt,
            )
            if existing is not None and existing == run:
                return existing
            raise ValueError("market-data poll run could not be persisted") from error
        return run

    def get(self, run_id: str) -> MarketDataPollRun | None:
        row = self._session.get(MarketDataPollRunRow, run_id)
        return None if row is None else MarketDataPollRun.model_validate_json(row.payload_json)

    def get_by_job_attempt(
        self,
        *,
        job_id: str,
        job_attempt: int,
    ) -> MarketDataPollRun | None:
        row = self._session.scalar(
            select(MarketDataPollRunRow).where(
                MarketDataPollRunRow.job_id == job_id,
                MarketDataPollRunRow.job_attempt == job_attempt,
            )
        )
        return None if row is None else MarketDataPollRun.model_validate_json(row.payload_json)


class SqlAlchemyMarketDataPollJobRunner:
    """Fetch one due stream with explicit fallback and ingest every accepted observation."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        providers: MarketDataProviderCatalog,
        policy: MarketDataServiceLevelPolicy | None = None,
        quality_checker: MarketDataQualityChecker | None = None,
        clock: PollingClock = utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._providers = providers
        self._policy = policy or default_market_data_service_level_policy()
        self._quality_checker = quality_checker or MarketDataQualityChecker()
        self._clock = clock

    async def run(
        self,
        *,
        payload: MarketDataPollJobPayload,
        job_id: str,
        job_attempt: int,
    ) -> MarketDataPollRun:
        run_id = MarketDataPollRun.build_run_id(
            job_id=job_id,
            job_attempt=job_attempt,
        )
        with self._session_factory() as session:
            runs = SqlAlchemyMarketDataPollRunRepository(session)
            existing = runs.get(run_id)
            if existing is not None:
                if existing.status is MarketDataPollRunStatus.FAILED:
                    raise MarketDataPollingFailedError(
                        error_code=existing.failure_code or "market_data_poll_failed",
                        error_message=existing.failure_message or "Market-data polling failed.",
                        retryable=existing.failure_retryable,
                    )
                return existing
            entry = SqlAlchemyMarketDataWatchlistRepository(session).get(payload.watchlist_id)

        if entry is None:
            raise MarketDataPollingFailedError(
                error_code="watchlist_not_found",
                error_message="Market-data watchlist entry was not found.",
                retryable=False,
            )
        if entry.state is not MarketDataWatchlistState.ACTIVE:
            raise MarketDataPollingFailedError(
                error_code="watchlist_not_active",
                error_message="Market-data watchlist entry is not active.",
                retryable=False,
            )
        if (
            entry.last_enqueued_for is None
            or payload.scheduled_for < entry.created_at
            or payload.scheduled_for > entry.last_enqueued_for
        ):
            raise MarketDataPollingFailedError(
                error_code="poll_schedule_invalid",
                error_message="Market-data poll schedule is not valid for this watchlist.",
                retryable=False,
            )

        started_at = self._now()
        range_start, range_end = self._collection_range(entry, started_at)
        attempts: list[MarketDataPollAttempt] = []

        for ordinal, route in enumerate(entry.routes, start=1):
            attempt_started_at = self._now()
            connection_error = self._connection_error(route)
            if connection_error is not None:
                attempts.append(
                    self._attempt(
                        ordinal=ordinal,
                        route=route,
                        outcome=MarketDataPollAttemptOutcome.CONNECTION_UNAVAILABLE,
                        error_code=connection_error,
                        started_at=attempt_started_at,
                    )
                )
                continue

            budget = self._policy.for_provider(route.provider_id)
            with self._session_factory() as session:
                budget_decision = SqlAlchemyProviderRequestBudgetGate(session).acquire(
                    budget=budget,
                    now=attempt_started_at,
                )
            if not budget_decision.acquired:
                attempts.append(
                    self._attempt(
                        ordinal=ordinal,
                        route=route,
                        outcome=MarketDataPollAttemptOutcome.RATE_LIMITED_LOCALLY,
                        error_code="provider_budget_exhausted",
                        started_at=attempt_started_at,
                    )
                )
                continue

            try:
                provider = self._providers.create(route.provider_id)
                candles = await provider.get_candles(
                    pair=entry.pair,
                    timeframe=entry.timeframe,
                    start_time=range_start,
                    end_time=range_end,
                    limit=entry.lookback_candles,
                )
            except MarketDataProviderError as error:
                attempts.append(
                    self._attempt(
                        ordinal=ordinal,
                        route=route,
                        outcome=MarketDataPollAttemptOutcome.PROVIDER_FAILED,
                        error_code=error.code.value,
                        started_at=attempt_started_at,
                    )
                )
                continue
            except Exception:
                attempts.append(
                    self._attempt(
                        ordinal=ordinal,
                        route=route,
                        outcome=MarketDataPollAttemptOutcome.PROVIDER_FAILED,
                        error_code="provider_request_failed",
                        started_at=attempt_started_at,
                    )
                )
                continue

            if not candles:
                attempts.append(
                    self._attempt(
                        ordinal=ordinal,
                        route=route,
                        outcome=MarketDataPollAttemptOutcome.NO_DATA,
                        started_at=attempt_started_at,
                    )
                )
                continue

            quality_error = self._quality_error(
                candles=candles,
                entry=entry,
                expected_source=route.provider_id,
                range_start=range_start,
                range_end=range_end,
                observed_at=self._now(),
            )
            if quality_error is not None:
                attempts.append(
                    self._attempt(
                        ordinal=ordinal,
                        route=route,
                        outcome=MarketDataPollAttemptOutcome.QUALITY_REJECTED,
                        error_code=quality_error,
                        started_at=attempt_started_at,
                        received_candles=len(candles),
                    )
                )
                continue

            decided_at = self._now()
            try:
                watermark_before = self._ensure_watermark(
                    entry=entry,
                    source=route.provider_id,
                    first_event_time=min(candle.close_time for candle in candles),
                    now=decided_at,
                )
                results = []
                for candle in candles:
                    with self._session_factory() as session:
                        results.append(
                            SqlAlchemyMarketDataIngestor(session).ingest(
                                observation=MarketDataRawObservation.from_candle(
                                    candle,
                                    created_at=decided_at,
                                ),
                                event=MarketDataEvent.from_candle(candle),
                                decided_at=decided_at,
                            )
                        )
                watermark_after = self._advance_watermark(
                    entry=entry,
                    source=route.provider_id,
                    high_water_event_time=max(candle.close_time for candle in candles),
                    now=self._now(),
                )
            except Exception as error:
                attempts.append(
                    self._attempt(
                        ordinal=ordinal,
                        route=route,
                        outcome=MarketDataPollAttemptOutcome.INGESTION_FAILED,
                        error_code="market_data_ingestion_failed",
                        started_at=attempt_started_at,
                        received_candles=len(candles),
                    )
                )
                self._save_failed_run(
                    run_id=run_id,
                    job_id=job_id,
                    job_attempt=job_attempt,
                    entry=entry,
                    payload=payload,
                    attempts=attempts,
                    started_at=started_at,
                    error_code="market_data_ingestion_failed",
                    error_message="Market-data ingestion failed.",
                    retryable=True,
                )
                raise MarketDataPollingFailedError(
                    error_code="market_data_ingestion_failed",
                    error_message="Market-data ingestion failed.",
                    retryable=True,
                ) from error

            attempts.append(
                self._attempt(
                    ordinal=ordinal,
                    route=route,
                    outcome=MarketDataPollAttemptOutcome.SUCCEEDED,
                    started_at=attempt_started_at,
                    received_candles=len(candles),
                )
            )
            run = MarketDataPollRun(
                run_id=run_id,
                job_id=job_id,
                job_attempt=job_attempt,
                watchlist_id=entry.watchlist_id,
                scheduled_for=payload.scheduled_for,
                status=MarketDataPollRunStatus.SUCCEEDED,
                attempts=tuple(attempts),
                selected_connection_id=route.connection_id,
                selected_provider_id=route.provider_id,
                received_candles=len(candles),
                accepted_events=sum(
                    result.decision.disposition is MarketDataEventDisposition.ACCEPTED
                    for result in results
                ),
                duplicate_events=sum(
                    result.decision.disposition is MarketDataEventDisposition.DUPLICATE
                    for result in results
                ),
                revision_required_events=sum(
                    result.decision.disposition is MarketDataEventDisposition.REVISION_REQUIRED
                    for result in results
                ),
                watermark_before_id=watermark_before.watermark_id,
                watermark_after_id=watermark_after.watermark_id,
                started_at=started_at,
                completed_at=self._now(),
            )
            return self._save_run(run)

        if attempts and all(
            attempt.outcome is MarketDataPollAttemptOutcome.NO_DATA for attempt in attempts
        ):
            run = MarketDataPollRun(
                run_id=run_id,
                job_id=job_id,
                job_attempt=job_attempt,
                watchlist_id=entry.watchlist_id,
                scheduled_for=payload.scheduled_for,
                status=MarketDataPollRunStatus.NO_DATA,
                attempts=tuple(attempts),
                received_candles=0,
                accepted_events=0,
                duplicate_events=0,
                revision_required_events=0,
                started_at=started_at,
                completed_at=self._now(),
            )
            return self._save_run(run)

        retryable = any(
            attempt.outcome
            in {
                MarketDataPollAttemptOutcome.PROVIDER_FAILED,
                MarketDataPollAttemptOutcome.RATE_LIMITED_LOCALLY,
            }
            for attempt in attempts
        )
        budget_exhausted = all(
            attempt.outcome is MarketDataPollAttemptOutcome.RATE_LIMITED_LOCALLY
            for attempt in attempts
        )
        error_code = (
            "provider_budget_exhausted" if budget_exhausted else "provider_routes_exhausted"
        )
        error_message = (
            "Local provider request budgets are exhausted."
            if budget_exhausted
            else "All configured market-data provider routes failed."
        )
        self._save_failed_run(
            run_id=run_id,
            job_id=job_id,
            job_attempt=job_attempt,
            entry=entry,
            payload=payload,
            attempts=attempts,
            started_at=started_at,
            error_code=error_code,
            error_message=error_message,
            retryable=retryable,
        )
        raise MarketDataPollingFailedError(
            error_code=error_code,
            error_message=error_message,
            retryable=retryable,
        )

    def _connection_error(self, route: MarketDataWatchlistRoute) -> str | None:
        with self._session_factory() as session:
            connection = SqlAlchemyMarketDataConnectionRepository(session).get(route.connection_id)
        if connection is None or connection.provider_id != route.provider_id:
            return "poll_connection_missing"
        if (
            connection.state is not MarketDataConnectionState.ENABLED
            or connection.health_status is not MarketDataConnectionHealth.HEALTHY
        ):
            return "poll_connection_not_ready"
        return None

    def _quality_error(
        self,
        *,
        candles: list[OHLCVCandle],
        entry: MarketDataWatchlistEntry,
        expected_source: str,
        range_start: datetime,
        range_end: datetime,
        observed_at: datetime,
    ) -> str | None:
        if any(
            candle.source != expected_source
            or candle.pair != entry.pair
            or candle.timeframe is not entry.timeframe
            for candle in candles
        ):
            return "provider_stream_mismatch"
        skew = self._policy.for_timeframe(entry.timeframe).maximum_future_clock_skew_seconds
        if any(candle.close_time > observed_at + timedelta(seconds=skew) for candle in candles):
            return "provider_future_clock_skew"
        report = self._quality_checker.check(
            candles,
            requested_start_time=range_start,
            requested_end_time=range_end,
            requested_timeframe=entry.timeframe,
        )
        return None if report.is_valid else "provider_quality_rejected"

    def _ensure_watermark(
        self,
        *,
        entry: MarketDataWatchlistEntry,
        source: str,
        first_event_time: datetime,
        now: datetime,
    ) -> VersionedMarketDataWatermark:
        for attempt in range(2):
            try:
                with self._session_factory.begin() as session:
                    store = SqlAlchemyMarketDataEventStore(session)
                    existing = store.get_latest_watermark(
                        source=source,
                        pair=entry.pair,
                        timeframe=entry.timeframe,
                        for_update=True,
                    )
                    if existing is not None:
                        return existing
                    service_level = self._policy.for_timeframe(entry.timeframe)
                    record = VersionedMarketDataWatermark.build(
                        watermark=MarketDataWatermark.build(
                            source=source,
                            pair=entry.pair,
                            timeframe=entry.timeframe,
                            high_water_event_time=first_event_time,
                            allowed_lateness_seconds=service_level.allowed_lateness_seconds,
                            calculated_at=now,
                        ),
                        version=1,
                        policy_version=entry.policy_version,
                        stored_at=now,
                    )
                    store.stage_watermark(record)
                    return record
            except IntegrityError:
                if attempt == 1:
                    raise
        raise AssertionError("watermark bootstrap retry loop did not return")

    def _advance_watermark(
        self,
        *,
        entry: MarketDataWatchlistEntry,
        source: str,
        high_water_event_time: datetime,
        now: datetime,
    ) -> VersionedMarketDataWatermark:
        for attempt in range(2):
            try:
                with self._session_factory.begin() as session:
                    store = SqlAlchemyMarketDataEventStore(session)
                    current = store.get_latest_watermark(
                        source=source,
                        pair=entry.pair,
                        timeframe=entry.timeframe,
                        for_update=True,
                    )
                    if current is None:
                        raise RuntimeError("polling watermark disappeared during ingestion")
                    if high_water_event_time <= current.watermark.high_water_event_time:
                        return current
                    advanced = current.watermark.model_copy(
                        update={
                            "high_water_event_time": high_water_event_time,
                            "watermark_time": high_water_event_time
                            - timedelta(seconds=current.watermark.allowed_lateness_seconds),
                            "calculated_at": now,
                        }
                    )
                    advanced = MarketDataWatermark.model_validate(advanced.model_dump())
                    record = VersionedMarketDataWatermark.build(
                        watermark=advanced,
                        version=current.version + 1,
                        policy_version=entry.policy_version,
                        stored_at=now,
                    )
                    store.stage_watermark(record)
                    return record
            except IntegrityError:
                if attempt == 1:
                    raise
        raise AssertionError("watermark advance retry loop did not return")

    def _attempt(
        self,
        *,
        ordinal: int,
        route: MarketDataWatchlistRoute,
        outcome: MarketDataPollAttemptOutcome,
        started_at: datetime,
        received_candles: int = 0,
        error_code: str | None = None,
    ) -> MarketDataPollAttempt:
        return MarketDataPollAttempt(
            ordinal=ordinal,
            connection_id=route.connection_id,
            provider_id=route.provider_id,
            outcome=outcome,
            received_candles=received_candles,
            error_code=error_code,
            started_at=started_at,
            completed_at=self._now(),
        )

    def _save_failed_run(
        self,
        *,
        run_id: str,
        job_id: str,
        job_attempt: int,
        entry: MarketDataWatchlistEntry,
        payload: MarketDataPollJobPayload,
        attempts: list[MarketDataPollAttempt],
        started_at: datetime,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> MarketDataPollRun:
        run = MarketDataPollRun(
            run_id=run_id,
            job_id=job_id,
            job_attempt=job_attempt,
            watchlist_id=entry.watchlist_id,
            scheduled_for=payload.scheduled_for,
            status=MarketDataPollRunStatus.FAILED,
            attempts=tuple(attempts),
            received_candles=0,
            accepted_events=0,
            duplicate_events=0,
            revision_required_events=0,
            failure_retryable=retryable,
            failure_code=error_code,
            failure_message=error_message,
            started_at=started_at,
            completed_at=self._now(),
        )
        return self._save_run(run)

    def _save_run(self, run: MarketDataPollRun) -> MarketDataPollRun:
        with self._session_factory() as session:
            return SqlAlchemyMarketDataPollRunRepository(session).save(run)

    @staticmethod
    def _collection_range(
        entry: MarketDataWatchlistEntry,
        now: datetime,
    ) -> tuple[datetime, datetime]:
        duration = entry.timeframe.duration
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        elapsed = now - epoch
        intervals = int(elapsed.total_seconds() // duration.total_seconds())
        end = epoch + (duration * intervals)
        start = end - (duration * entry.lookback_candles)
        return start, end

    def _now(self) -> datetime:
        return _as_utc(self._clock())
