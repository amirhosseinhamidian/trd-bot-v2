from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import MarketType, OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    InMemoryMarketDataConnectionRepository,
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataProvider,
    MarketDataProviderAccessMode,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderMetadata,
)
from trd_bot.market_data.import_history import InMemoryMarketDataImportRepository
from trd_bot.research import (
    InMemoryDatasetRepository,
    InMemoryHistoricalDatasetCommitter,
    calculate_dataset_checksum,
)
from trd_bot.research.historical_dataset_jobs import (
    HistoricalDatasetJobOperation,
    HistoricalDatasetJobPayload,
    HistoricalDatasetJobRequest,
    HistoricalDatasetJobRunner,
)

NOW = datetime(2026, 9, 25, 8, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
CONNECTION_ID = "market-data-connection-job-test"


def candle(offset: int, *, close_price: str = "105") -> OHLCVCandle:
    open_time = NOW + timedelta(hours=offset)
    return OHLCVCandle(
        source="job-provider",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=open_time,
        close_time=open_time + timedelta(hours=1) - timedelta(milliseconds=1),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal(close_price),
        volume=Decimal("1000"),
        is_closed=True,
    )


@dataclass
class ProviderState:
    candles: list[OHLCVCandle]
    failure: str | None = None


class JobProvider(MarketDataProvider):
    def __init__(self, state: ProviderState) -> None:
        self._state = state

    @property
    def metadata(self) -> MarketDataProviderMetadata:
        return MarketDataProviderMetadata(
            provider_id="job-provider",
            display_name="Job Provider",
            requires_credentials=False,
            supported_market_types=(MarketType.SPOT,),
            supported_timeframes=(Timeframe.HOUR_1,),
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
        del pair, timeframe, start_time, end_time
        if self._state.failure is not None:
            raise MarketDataProviderError(self._state.failure)
        return self._state.candles if limit is None else self._state.candles[:limit]


@dataclass
class RunnerDependencies:
    runner: HistoricalDatasetJobRunner
    datasets: InMemoryDatasetRepository
    history: InMemoryMarketDataImportRepository
    state: ProviderState


@pytest.fixture
def dependencies() -> RunnerDependencies:
    state = ProviderState(candles=[candle(0), candle(1)])
    connections = InMemoryMarketDataConnectionRepository()
    connections.save(
        MarketDataConnection(
            connection_id=CONNECTION_ID,
            provider_id="job-provider",
            display_name="Job provider connection",
            state=MarketDataConnectionState.ENABLED,
            health_status=MarketDataConnectionHealth.HEALTHY,
            created_at=NOW,
            updated_at=NOW,
            last_tested_at=NOW,
        )
    )
    datasets = InMemoryDatasetRepository()
    history = InMemoryMarketDataImportRepository()
    runner = HistoricalDatasetJobRunner(
        connections=connections,
        providers=MarketDataProviderCatalog({"job-provider": lambda: JobProvider(state)}),
        datasets=datasets,
        history=history,
        committer=InMemoryHistoricalDatasetCommitter(datasets=datasets, history=history),
    )
    return RunnerDependencies(runner=runner, datasets=datasets, history=history, state=state)


def import_payload() -> HistoricalDatasetJobPayload:
    candles = [candle(0), candle(1)]
    return HistoricalDatasetJobPayload(
        operation=HistoricalDatasetJobOperation.IMPORT,
        connection_id=CONNECTION_ID,
        request=HistoricalDatasetJobRequest(
            name="BTC job import",
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            start_time=NOW,
            end_time=NOW + timedelta(hours=2),
            preview_checksum=calculate_dataset_checksum(candles),
        ),
    )


@pytest.mark.asyncio
async def test_job_runner_commits_import_and_reports_progress(
    dependencies: RunnerDependencies,
) -> None:
    progress: list[int] = []
    record = await dependencies.runner.run(
        payload=import_payload(),
        import_id="market-data-import-job-success-1",
        created_at=NOW,
        report_progress=progress.append,
        cancellation_requested=lambda: False,
    )

    assert record is not None
    assert record.status.value == "succeeded"
    assert record.root_import_id == record.import_id
    assert record.version_number == 1
    assert dependencies.datasets.count() == 1
    assert dependencies.history.get(record.import_id) == record
    assert progress == [10, 75, 95]


@pytest.mark.asyncio
async def test_job_runner_records_safe_provider_failure(
    dependencies: RunnerDependencies,
) -> None:
    dependencies.state.failure = "provider failed; token=secret-value"

    with pytest.raises(MarketDataProviderError):
        await dependencies.runner.run(
            payload=import_payload(),
            import_id="market-data-import-job-failed-1",
            created_at=NOW,
            report_progress=lambda _: None,
            cancellation_requested=lambda: False,
        )

    record = dependencies.history.get("market-data-import-job-failed-1")
    assert record is not None
    assert record.status.value == "failed"
    assert record.error_code == "provider_request_failed"
    assert record.error_message == "provider failed; token=[REDACTED]"
    assert dependencies.datasets.count() == 0


@pytest.mark.asyncio
async def test_job_runner_stops_before_commit_when_cancelled(
    dependencies: RunnerDependencies,
) -> None:
    checks = iter((False, True))
    record = await dependencies.runner.run(
        payload=import_payload(),
        import_id="market-data-import-job-cancelled-1",
        created_at=NOW,
        report_progress=lambda _: None,
        cancellation_requested=lambda: next(checks),
    )

    assert record is None
    assert dependencies.datasets.count() == 0
    assert dependencies.history.count() == 0


@pytest.mark.asyncio
async def test_job_runner_refreshes_latest_successful_version(
    dependencies: RunnerDependencies,
) -> None:
    root = await dependencies.runner.run(
        payload=import_payload(),
        import_id="market-data-import-job-root-1",
        created_at=NOW,
        report_progress=lambda _: None,
        cancellation_requested=lambda: False,
    )
    assert root is not None
    dependencies.state.candles = [candle(0), candle(1, close_price="106")]
    refreshed = await dependencies.runner.run(
        payload=HistoricalDatasetJobPayload(
            operation=HistoricalDatasetJobOperation.REFRESH,
            connection_id=CONNECTION_ID,
            source_import_id=root.import_id,
        ),
        import_id="market-data-import-job-refresh-1",
        created_at=NOW + timedelta(minutes=1),
        report_progress=lambda _: None,
        cancellation_requested=lambda: False,
    )

    assert refreshed is not None
    assert refreshed.operation.value == "refresh"
    assert refreshed.parent_import_id == root.import_id
    assert refreshed.version_number == 2
    assert refreshed.content_changed is True
    assert dependencies.datasets.count() == 2
