from typing import Annotated, NoReturn, Self

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_market_data_connection_repository,
    get_market_data_provider_catalog,
)
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data import (
    MarketDataConnectionNotFoundError,
    MarketDataConnectionRepository,
    MarketDataConnectionStateError,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderUnavailableError,
)
from trd_bot.research import DatasetRepository, DatasetSummary, InvalidDatasetError
from trd_bot.research.historical_dataset_imports import (
    HistoricalDatasetImportLimitError,
    HistoricalDatasetImportPreview,
    HistoricalDatasetImportService,
    HistoricalDatasetProviderCapabilityError,
)

router = APIRouter(
    prefix="/market-data/connections",
    tags=["Historical market-data imports"],
)

ConnectionRepositoryDependency = Annotated[
    MarketDataConnectionRepository,
    Depends(get_market_data_connection_repository),
]
ProviderCatalogDependency = Annotated[
    MarketDataProviderCatalog,
    Depends(get_market_data_provider_catalog),
]
DatasetRepositoryDependency = Annotated[
    DatasetRepository,
    Depends(get_dataset_repository),
]


class HistoricalDatasetImportRequest(BaseModel):
    """Bounded historical series request for preview or immutable import."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    pair: TradingPair
    timeframe: Timeframe
    start_time: AwareDatetime
    end_time: AwareDatetime

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("dataset name cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end time must be after start time")
        return self


def _service(
    *,
    connections: MarketDataConnectionRepository,
    providers: MarketDataProviderCatalog,
    datasets: DatasetRepository,
) -> HistoricalDatasetImportService:
    return HistoricalDatasetImportService(
        connections=connections,
        providers=providers,
        datasets=datasets,
    )


def _raise_fetch_error(
    error: (
        MarketDataConnectionNotFoundError
        | MarketDataConnectionStateError
        | MarketDataProviderUnavailableError
        | HistoricalDatasetProviderCapabilityError
        | HistoricalDatasetImportLimitError
        | MarketDataProviderError
    ),
) -> NoReturn:
    if isinstance(error, MarketDataConnectionNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    if isinstance(error, MarketDataConnectionStateError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    if isinstance(error, HistoricalDatasetProviderCapabilityError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    if isinstance(error, HistoricalDatasetImportLimitError):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(error),
        ) from error

    if isinstance(error, MarketDataProviderUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(error),
    ) from error


def _raise_quality_error(error: InvalidDatasetError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "message": "dataset failed quality checks",
            "candles_checked": error.report.candles_checked,
            "issues": [issue.model_dump(mode="json") for issue in error.report.issues],
        },
    ) from error


@router.post(
    "/{connection_id}/datasets/preview",
    response_model=HistoricalDatasetImportPreview,
)
async def preview_historical_dataset_import(
    connection_id: str,
    request: HistoricalDatasetImportRequest,
    connections: ConnectionRepositoryDependency,
    providers: ProviderCatalogDependency,
    datasets: DatasetRepositoryDependency,
) -> HistoricalDatasetImportPreview:
    """Fetch and validate normalized candles without creating a dataset."""

    service = _service(
        connections=connections,
        providers=providers,
        datasets=datasets,
    )

    try:
        return await service.preview(
            connection_id=connection_id,
            name=request.name,
            pair=request.pair,
            timeframe=request.timeframe,
            start_time=request.start_time,
            end_time=request.end_time,
        )
    except (
        MarketDataConnectionNotFoundError,
        MarketDataConnectionStateError,
        MarketDataProviderUnavailableError,
        HistoricalDatasetProviderCapabilityError,
        HistoricalDatasetImportLimitError,
        MarketDataProviderError,
    ) as error:
        _raise_fetch_error(error)


@router.post(
    "/{connection_id}/datasets",
    response_model=DatasetSummary,
    status_code=status.HTTP_201_CREATED,
)
async def import_historical_dataset(
    connection_id: str,
    request: HistoricalDatasetImportRequest,
    connections: ConnectionRepositoryDependency,
    providers: ProviderCatalogDependency,
    datasets: DatasetRepositoryDependency,
) -> DatasetSummary:
    """Fetch, quality-check, and persist one immutable historical dataset."""

    service = _service(
        connections=connections,
        providers=providers,
        datasets=datasets,
    )

    try:
        dataset = await service.import_dataset(
            connection_id=connection_id,
            name=request.name,
            pair=request.pair,
            timeframe=request.timeframe,
            start_time=request.start_time,
            end_time=request.end_time,
        )
    except InvalidDatasetError as error:
        _raise_quality_error(error)
    except (
        MarketDataConnectionNotFoundError,
        MarketDataConnectionStateError,
        MarketDataProviderUnavailableError,
        HistoricalDatasetProviderCapabilityError,
        HistoricalDatasetImportLimitError,
        MarketDataProviderError,
    ) as error:
        _raise_fetch_error(error)

    return DatasetSummary.from_dataset(dataset)
