from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    DataQualityReport,
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionNotFoundError,
    MarketDataConnectionRepository,
    MarketDataConnectionState,
    MarketDataConnectionStateError,
    MarketDataProviderCatalog,
    MarketDataQualityChecker,
)
from trd_bot.research.datasets import (
    DatasetBuilder,
    DatasetRepository,
    DatasetSnapshot,
    InvalidDatasetError,
)

MAX_HISTORICAL_IMPORT_CANDLES = 100_000


class HistoricalDatasetProviderCapabilityError(ValueError):
    """Raised when a connection cannot serve the requested market series."""


class HistoricalDatasetImportLimitError(ValueError):
    """Raised when one import would exceed the bounded dataset payload size."""


class HistoricalDatasetImportPreview(BaseModel):
    """Quality and coverage preview for normalized external historical candles."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    provider_id: str
    name: str
    pair: TradingPair
    timeframe: Timeframe
    requested_start_time: datetime
    requested_end_time: datetime
    candle_count: int = Field(ge=0)
    first_open_time: datetime | None
    last_close_time: datetime | None
    quality_report: DataQualityReport
    ready_to_import: bool


class HistoricalDatasetImportService:
    """Fetch, validate, preview, and persist read-only historical market data."""

    def __init__(
        self,
        *,
        connections: MarketDataConnectionRepository,
        providers: MarketDataProviderCatalog,
        datasets: DatasetRepository,
        quality_checker: MarketDataQualityChecker | None = None,
    ) -> None:
        self._connections = connections
        self._providers = providers
        self._datasets = datasets
        self._quality_checker = quality_checker or MarketDataQualityChecker()

    async def preview(
        self,
        *,
        connection_id: str,
        name: str,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
    ) -> HistoricalDatasetImportPreview:
        connection, candles, quality_report = await self._fetch_and_check(
            connection_id=connection_id,
            pair=pair,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
        )

        return HistoricalDatasetImportPreview(
            connection_id=connection.connection_id,
            provider_id=connection.provider_id,
            name=name,
            pair=pair,
            timeframe=timeframe,
            requested_start_time=start_time,
            requested_end_time=end_time,
            candle_count=len(candles),
            first_open_time=candles[0].open_time if candles else None,
            last_close_time=candles[-1].close_time if candles else None,
            quality_report=quality_report,
            ready_to_import=quality_report.is_valid,
        )

    async def import_dataset(
        self,
        *,
        connection_id: str,
        name: str,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
    ) -> DatasetSnapshot:
        _, candles, quality_report = await self._fetch_and_check(
            connection_id=connection_id,
            pair=pair,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
        )

        if not quality_report.is_valid:
            raise InvalidDatasetError(quality_report)

        dataset = DatasetBuilder(quality_checker=self._quality_checker).build(
            name=name,
            candles=candles,
        )
        return self._datasets.save(dataset)

    async def _fetch_and_check(
        self,
        *,
        connection_id: str,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
    ) -> tuple[MarketDataConnection, tuple[OHLCVCandle, ...], DataQualityReport]:
        connection = self._connections.get(connection_id)
        if connection is None:
            raise MarketDataConnectionNotFoundError("market-data connection not found")

        if connection.state is not MarketDataConnectionState.ENABLED:
            raise MarketDataConnectionStateError(
                "market-data connection must be enabled before historical import"
            )

        if connection.health_status is not MarketDataConnectionHealth.HEALTHY:
            raise MarketDataConnectionStateError(
                "market-data connection must be healthy before historical import"
            )

        provider = self._providers.create(connection.provider_id)
        metadata = provider.metadata

        if pair.market_type not in metadata.supported_market_types:
            raise HistoricalDatasetProviderCapabilityError(
                "market type is not supported by connection provider"
            )

        if timeframe not in metadata.supported_timeframes:
            raise HistoricalDatasetProviderCapabilityError(
                "timeframe is not supported by connection provider"
            )

        candles = tuple(
            await provider.get_candles(
                pair=pair,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                limit=MAX_HISTORICAL_IMPORT_CANDLES + 1,
            )
        )

        if len(candles) > MAX_HISTORICAL_IMPORT_CANDLES:
            raise HistoricalDatasetImportLimitError(
                "historical import exceeds the maximum candle count"
            )

        quality_report = self._quality_checker.check(candles)
        return connection, candles, quality_report
