from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyMarketDataPollingScheduler,
    SqlAlchemyMarketDataPollJobRunner,
    SqlAlchemyMarketDataPollRunRepository,
    SqlAlchemyMarketDataWatchlistManager,
    SqlAlchemyMarketDataWatchlistRepository,
    SqlAlchemyMarketDataWindowFinalizer,
    SqlAlchemyProviderRequestBudgetGate,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.market_data_connection_repositories import (
    SqlAlchemyMarketDataConnectionRepository,
)
from trd_bot.db.models import (
    MarketDataEventDecisionRow,
    MarketDataOutboxRow,
    MarketDataPollRunRow,
    MarketDataProviderBudgetRow,
    MarketDataRawObservationRow,
    MarketDataWatermarkRow,
    MarketDataWindowFinalizationRow,
    MarketDataWindowVersionRow,
)
from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataPollAttemptOutcome,
    MarketDataPollingFailedError,
    MarketDataPollJobPayload,
    MarketDataPollRunStatus,
    MarketDataProvider,
    MarketDataProviderAccessMode,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderMetadata,
    MarketDataWatchlistState,
    default_market_data_service_level_policy,
)

NOW = datetime(2026, 10, 14, 12, 5, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")


class SyntheticPollingProvider(MarketDataProvider):
    def __init__(
        self,
        *,
        provider_id: str,
        candles: list[OHLCVCandle] | None = None,
        failure: MarketDataProviderError | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._candles = candles or []
        self._failure = failure
        self.calls: list[tuple[datetime, datetime, int | None]] = []

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return MarketDataProviderMetadata(
            provider_id=self._provider_id,
            display_name=self._provider_id,
            requires_credentials=False,
            supported_market_types=(MarketType.SPOT,),
            supported_timeframes=tuple(Timeframe),
            default_pair=PAIR,
            access_mode=MarketDataProviderAccessMode.DIRECT,
            max_closed_candles=None,
        )

    async def test_connection(self) -> None:
        return None

    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        assert pair == PAIR
        assert timeframe is Timeframe.HOUR_1
        self.calls.append((start_time, end_time, limit))
        if self._failure is not None:
            raise self._failure
        return list(self._candles)


def create_candles(provider_id: str) -> list[OHLCVCandle]:
    return [
        OHLCVCandle(
            source=provider_id,
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=datetime(2026, 10, 14, hour, tzinfo=UTC),
            close_time=datetime(2026, 10, 14, hour + 1, tzinfo=UTC),
            received_at=NOW,
            open_price=Decimal("100"),
            high_price=Decimal("110"),
            low_price=Decimal("95"),
            close_price=Decimal("105"),
            volume=Decimal("1250.5"),
            is_closed=True,
        )
        for hour in (9, 10, 11)
    ]


def save_ready_connection(
    factory: object,
    *,
    connection_id: str,
    provider_id: str,
) -> None:
    connection = MarketDataConnection(
        connection_id=connection_id,
        provider_id=provider_id,
        display_name=provider_id,
        state=MarketDataConnectionState.ENABLED,
        health_status=MarketDataConnectionHealth.HEALTHY,
        created_at=NOW,
        updated_at=NOW,
        last_tested_at=NOW,
    )
    with factory() as session:  # type: ignore[operator]
        SqlAlchemyMarketDataConnectionRepository(session).save(connection)


def prepare_watchlist(factory: object, catalog: MarketDataProviderCatalog) -> object:
    save_ready_connection(
        factory,
        connection_id="market-data-connection-kraken",
        provider_id="kraken-public",
    )
    save_ready_connection(
        factory,
        connection_id="market-data-connection-binance",
        provider_id="binance-public",
    )
    with factory() as session:  # type: ignore[operator]
        return SqlAlchemyMarketDataWatchlistManager(
            session=session,
            providers=catalog,
            clock=lambda: NOW,
        ).create(
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            kraken_connection_id="market-data-connection-kraken",
            binance_connection_id="market-data-connection-binance",
        )


def enqueue_due(factory: object) -> tuple[object, object]:
    with factory() as session:  # type: ignore[operator]
        jobs = SqlAlchemyMarketDataPollingScheduler(session).enqueue_due(now=NOW)
        assert len(jobs) == 1
        job = jobs[0]
        payload = MarketDataPollJobPayload.model_validate(job.payload)
        return job, payload


def row_count(session: object, row_type: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(row_type)))  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_polling_uses_explicit_kraken_then_binance_fallback_and_ingests() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    kraken = SyntheticPollingProvider(
        provider_id="kraken-public",
        failure=MarketDataProviderError("private upstream detail"),
    )
    binance = SyntheticPollingProvider(
        provider_id="binance-public",
        candles=create_candles("binance-public"),
    )
    catalog = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: kraken,
            "binance-public": lambda: binance,
        }
    )

    try:
        entry = prepare_watchlist(factory, catalog)
        job, payload = enqueue_due(factory)
        run = await SqlAlchemyMarketDataPollJobRunner(
            session_factory=factory,
            providers=catalog,
            clock=lambda: NOW + timedelta(seconds=1),
        ).run(
            payload=payload,  # type: ignore[arg-type]
            job_id=job.job_id,  # type: ignore[attr-defined]
            job_attempt=1,
        )

        assert run.status is MarketDataPollRunStatus.SUCCEEDED
        assert run.watchlist_id == entry.watchlist_id  # type: ignore[attr-defined]
        assert run.selected_provider_id == "binance-public"
        assert [attempt.outcome for attempt in run.attempts] == [
            MarketDataPollAttemptOutcome.PROVIDER_FAILED,
            MarketDataPollAttemptOutcome.SUCCEEDED,
        ]
        assert run.received_candles == 3
        assert run.accepted_events == 3
        assert kraken.calls == [
            (
                datetime(2026, 10, 14, 9, tzinfo=UTC),
                datetime(2026, 10, 14, 12, tzinfo=UTC),
                3,
            )
        ]
        assert len(binance.calls) == 1

        with factory() as session:
            assert row_count(session, MarketDataRawObservationRow) == 3
            assert row_count(session, MarketDataEventDecisionRow) == 3
            assert row_count(session, MarketDataWindowVersionRow) == 5
            assert row_count(session, MarketDataWindowFinalizationRow) == 2
            assert row_count(session, MarketDataOutboxRow) == 3
            assert row_count(session, MarketDataWatermarkRow) == 2
            assert row_count(session, MarketDataPollRunRow) == 1
            assert row_count(session, MarketDataProviderBudgetRow) == 2
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_primary_success_does_not_contact_fallback() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    kraken = SyntheticPollingProvider(
        provider_id="kraken-public",
        candles=create_candles("kraken-public"),
    )
    binance = SyntheticPollingProvider(
        provider_id="binance-public",
        candles=create_candles("binance-public"),
    )
    catalog = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: kraken,
            "binance-public": lambda: binance,
        }
    )

    try:
        prepare_watchlist(factory, catalog)
        job, payload = enqueue_due(factory)
        run = await SqlAlchemyMarketDataPollJobRunner(
            session_factory=factory,
            providers=catalog,
            clock=lambda: NOW + timedelta(seconds=1),
        ).run(
            payload=payload,  # type: ignore[arg-type]
            job_id=job.job_id,  # type: ignore[attr-defined]
            job_attempt=1,
        )

        assert run.selected_provider_id == "kraken-public"
        assert len(run.attempts) == 1
        assert len(kraken.calls) == 1
        assert binance.calls == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_no_data_is_terminal_evidence_without_market_mutation() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    kraken = SyntheticPollingProvider(provider_id="kraken-public")
    binance = SyntheticPollingProvider(provider_id="binance-public")
    catalog = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: kraken,
            "binance-public": lambda: binance,
        }
    )

    try:
        prepare_watchlist(factory, catalog)
        job, payload = enqueue_due(factory)
        run = await SqlAlchemyMarketDataPollJobRunner(
            session_factory=factory,
            providers=catalog,
            clock=lambda: NOW + timedelta(seconds=1),
        ).run(
            payload=payload,  # type: ignore[arg-type]
            job_id=job.job_id,  # type: ignore[attr-defined]
            job_attempt=1,
        )

        assert run.status is MarketDataPollRunStatus.NO_DATA
        assert [attempt.outcome for attempt in run.attempts] == [
            MarketDataPollAttemptOutcome.NO_DATA,
            MarketDataPollAttemptOutcome.NO_DATA,
        ]
        with factory() as session:
            assert row_count(session, MarketDataRawObservationRow) == 0
            assert row_count(session, MarketDataWatermarkRow) == 0
            assert row_count(session, MarketDataPollRunRow) == 1
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_local_primary_budget_exhaustion_uses_fallback_budget() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    kraken = SyntheticPollingProvider(
        provider_id="kraken-public",
        candles=create_candles("kraken-public"),
    )
    binance = SyntheticPollingProvider(
        provider_id="binance-public",
        candles=create_candles("binance-public"),
    )
    catalog = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: kraken,
            "binance-public": lambda: binance,
        }
    )

    try:
        prepare_watchlist(factory, catalog)
        budget = default_market_data_service_level_policy().for_provider("kraken-public")
        for _ in range(budget.burst_requests):
            with factory() as session:
                decision = SqlAlchemyProviderRequestBudgetGate(session).acquire(
                    budget=budget,
                    now=NOW,
                )
                assert decision.acquired is True

        job, payload = enqueue_due(factory)
        run = await SqlAlchemyMarketDataPollJobRunner(
            session_factory=factory,
            providers=catalog,
            clock=lambda: NOW + timedelta(seconds=1),
        ).run(
            payload=payload,  # type: ignore[arg-type]
            job_id=job.job_id,  # type: ignore[attr-defined]
            job_attempt=1,
        )

        assert run.selected_provider_id == "binance-public"
        assert [attempt.outcome for attempt in run.attempts] == [
            MarketDataPollAttemptOutcome.RATE_LIMITED_LOCALLY,
            MarketDataPollAttemptOutcome.SUCCEEDED,
        ]
        assert kraken.calls == []
        assert len(binance.calls) == 1
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_failed_poll_attempt_replays_the_same_retry_policy() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    catalog = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: SyntheticPollingProvider(
                provider_id="kraken-public",
                failure=MarketDataProviderError("private upstream detail"),
            ),
            "binance-public": lambda: SyntheticPollingProvider(
                provider_id="binance-public",
                failure=MarketDataProviderError("private upstream detail"),
            ),
        }
    )

    try:
        prepare_watchlist(factory, catalog)
        job, payload = enqueue_due(factory)
        runner = SqlAlchemyMarketDataPollJobRunner(
            session_factory=factory,
            providers=catalog,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        for _ in range(2):
            with pytest.raises(MarketDataPollingFailedError) as failure:
                await runner.run(
                    payload=payload,  # type: ignore[arg-type]
                    job_id=job.job_id,  # type: ignore[attr-defined]
                    job_attempt=1,
                )
            assert failure.value.error_code == "provider_routes_exhausted"
            assert failure.value.retryable is True

        with factory() as session:
            assert row_count(session, MarketDataPollRunRow) == 1
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_finalization_failure_is_recorded_as_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    kraken = SyntheticPollingProvider(
        provider_id="kraken-public",
        candles=create_candles("kraken-public"),
    )
    binance = SyntheticPollingProvider(provider_id="binance-public")
    catalog = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: kraken,
            "binance-public": lambda: binance,
        }
    )

    def fail_finalization(*_args: object, **_kwargs: object) -> tuple[object, ...]:
        raise RuntimeError("private database detail")

    monkeypatch.setattr(
        SqlAlchemyMarketDataWindowFinalizer,
        "finalize_eligible",
        fail_finalization,
    )

    try:
        prepare_watchlist(factory, catalog)
        job, payload = enqueue_due(factory)
        with pytest.raises(MarketDataPollingFailedError) as failure:
            await SqlAlchemyMarketDataPollJobRunner(
                session_factory=factory,
                providers=catalog,
                clock=lambda: NOW + timedelta(seconds=1),
            ).run(
                payload=payload,  # type: ignore[arg-type]
                job_id=job.job_id,  # type: ignore[attr-defined]
                job_attempt=1,
            )

        assert failure.value.error_code == "market_data_finalization_failed"
        assert failure.value.retryable is True
        assert binance.calls == []
        with factory() as session:
            stored = SqlAlchemyMarketDataPollRunRepository(session).get_by_job_attempt(
                job_id=job.job_id,  # type: ignore[attr-defined]
                job_attempt=1,
            )
            assert stored is not None
            assert stored.failure_code == "market_data_finalization_failed"
            assert stored.attempts[-1].outcome is (MarketDataPollAttemptOutcome.FINALIZATION_FAILED)
    finally:
        engine.dispose()


def test_scheduler_advances_cadence_without_duplicate_slots_and_respects_pause() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    catalog = MarketDataProviderCatalog(
        {
            "kraken-public": lambda: SyntheticPollingProvider(provider_id="kraken-public"),
            "binance-public": lambda: SyntheticPollingProvider(provider_id="binance-public"),
        }
    )

    try:
        entry = prepare_watchlist(factory, catalog)
        with factory() as session:
            scheduler = SqlAlchemyMarketDataPollingScheduler(session)
            first = scheduler.enqueue_due(now=NOW)
            repeated = scheduler.enqueue_due(now=NOW)
            assert len(first) == 1
            assert repeated == ()

        with factory() as session:
            stored = SqlAlchemyMarketDataWatchlistRepository(session).get(
                entry.watchlist_id  # type: ignore[attr-defined]
            )
            assert stored is not None
            assert stored.last_job_id == first[0].job_id
            assert stored.next_poll_at == NOW + timedelta(seconds=120)
            paused = SqlAlchemyMarketDataWatchlistManager(
                session=session,
                providers=catalog,
                clock=lambda: NOW + timedelta(seconds=120),
            ).pause(stored.watchlist_id)
            assert paused.state is MarketDataWatchlistState.PAUSED

        with factory() as session:
            assert (
                SqlAlchemyMarketDataPollingScheduler(session).enqueue_due(
                    now=NOW + timedelta(seconds=120)
                )
                == ()
            )
    finally:
        engine.dispose()


def test_provider_token_bucket_enforces_burst_and_sustained_budget() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    budget = default_market_data_service_level_policy().for_provider("kraken-public")

    try:
        decisions = []
        for _ in range(4):
            with factory() as session:
                decisions.append(
                    SqlAlchemyProviderRequestBudgetGate(session).acquire(
                        budget=budget,
                        now=NOW,
                    )
                )
        assert [decision.acquired for decision in decisions] == [True, True, True, False]
        assert decisions[-1].retry_after_seconds == 6

        with factory() as session:
            refilled = SqlAlchemyProviderRequestBudgetGate(session).acquire(
                budget=budget,
                now=NOW + timedelta(seconds=6),
            )
        assert refilled.acquired is True
    finally:
        engine.dispose()
