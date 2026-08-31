from datetime import UTC, datetime
from typing import Annotated, NoReturn, Self
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.api.dependencies import (
    get_dataset_repository,
    get_market_data_connection_repository,
    get_market_data_import_repository,
    get_market_data_provider_catalog,
)
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data import (
    MarketDataConnectionNotFoundError,
    MarketDataConnectionRepository,
    MarketDataConnectionStateError,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderUnavailableError,
)
from trd_bot.market_data.import_history import (
    MarketDataImportOperation,
    MarketDataImportRecord,
    MarketDataImportRepository,
    MarketDataImportStatus,
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
ImportHistoryRepositoryDependency = Annotated[
    MarketDataImportRepository,
    Depends(get_market_data_import_repository),
]


class MarketDataImportHistoryParams(PaginationParams):
    """Pagination and status filter for one connection's import history."""

    status: MarketDataImportStatus | None = None


ImportHistoryQuery = Annotated[MarketDataImportHistoryParams, Query()]
VersionHistoryQuery = Annotated[PaginationParams, Query()]


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


def _history_error_code(error: Exception) -> str:
    if isinstance(error, InvalidDatasetError):
        return "quality_check_failed"
    if isinstance(error, MarketDataConnectionStateError):
        return "connection_state_invalid"
    if isinstance(error, HistoricalDatasetProviderCapabilityError):
        return "provider_capability_unsupported"
    if isinstance(error, HistoricalDatasetImportLimitError):
        return "import_limit_exceeded"
    if isinstance(error, MarketDataProviderUnavailableError):
        return "provider_unavailable"
    return "provider_request_failed"


def _save_import_history(
    *,
    repository: MarketDataImportRepository,
    import_id: str,
    connection_id: str,
    provider_id: str,
    request: HistoricalDatasetImportRequest,
    created_at: datetime,
    status_value: MarketDataImportStatus,
    candle_count: int,
    dataset_id: str | None = None,
    error: Exception | None = None,
    operation: MarketDataImportOperation = MarketDataImportOperation.IMPORT,
    source_dataset_id: str | None = None,
    root_import_id: str | None = None,
    parent_import_id: str | None = None,
    version_number: int | None = None,
    content_changed: bool | None = None,
) -> MarketDataImportRecord:
    error_message = None
    error_code = None
    if error is not None:
        error_code = _history_error_code(error)
        error_message = (str(error).strip() or error.__class__.__name__)[:500]

    return repository.save(
        MarketDataImportRecord(
            import_id=import_id,
            connection_id=connection_id,
            provider_id=provider_id,
            dataset_name=request.name,
            pair=request.pair,
            timeframe=request.timeframe,
            requested_start_time=request.start_time,
            requested_end_time=request.end_time,
            created_at=created_at,
            completed_at=datetime.now(UTC),
            status=status_value,
            candle_count=candle_count,
            dataset_id=dataset_id,
            error_code=error_code,
            error_message=error_message,
            operation=operation,
            source_dataset_id=source_dataset_id,
            root_import_id=root_import_id,
            parent_import_id=parent_import_id,
            version_number=version_number,
            content_changed=content_changed,
        )
    )


def _get_import_or_404(
    *,
    connection_id: str,
    import_id: str,
    connections: MarketDataConnectionRepository,
    history: MarketDataImportRepository,
) -> MarketDataImportRecord:
    if connections.get(connection_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="market-data connection not found",
        )

    record = history.get(import_id)
    if record is None or record.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="market-data import not found",
        )
    return record


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
    history: ImportHistoryRepositoryDependency,
) -> DatasetSummary:
    """Fetch, quality-check, persist a dataset, and record the immutable attempt."""

    service = _service(
        connections=connections,
        providers=providers,
        datasets=datasets,
    )
    tracked_connection = connections.get(connection_id)
    import_id = f"market-data-import-{uuid4().hex}"
    created_at = datetime.now(UTC)

    try:
        dataset = await service.import_dataset(
            connection_id=connection_id,
            import_id=import_id,
            name=request.name,
            pair=request.pair,
            timeframe=request.timeframe,
            start_time=request.start_time,
            end_time=request.end_time,
        )
    except InvalidDatasetError as error:
        if tracked_connection is not None:
            _save_import_history(
                repository=history,
                import_id=import_id,
                connection_id=tracked_connection.connection_id,
                provider_id=tracked_connection.provider_id,
                request=request,
                created_at=created_at,
                status_value=MarketDataImportStatus.FAILED,
                candle_count=error.report.candles_checked,
                error=error,
            )
        _raise_quality_error(error)
    except (
        MarketDataConnectionNotFoundError,
        MarketDataConnectionStateError,
        MarketDataProviderUnavailableError,
        HistoricalDatasetProviderCapabilityError,
        HistoricalDatasetImportLimitError,
        MarketDataProviderError,
    ) as error:
        if tracked_connection is not None:
            _save_import_history(
                repository=history,
                import_id=import_id,
                connection_id=tracked_connection.connection_id,
                provider_id=tracked_connection.provider_id,
                request=request,
                created_at=created_at,
                status_value=MarketDataImportStatus.FAILED,
                candle_count=0,
                error=error,
            )
        _raise_fetch_error(error)

    created_snapshot = dataset.provenance.import_id == import_id
    _save_import_history(
        repository=history,
        import_id=import_id,
        connection_id=connection_id,
        provider_id=dataset.source,
        request=request,
        created_at=created_at,
        status_value=MarketDataImportStatus.SUCCEEDED,
        candle_count=dataset.candle_count,
        dataset_id=dataset.dataset_id,
        root_import_id=import_id if created_snapshot else None,
        version_number=1 if created_snapshot else None,
    )
    return DatasetSummary.from_dataset(dataset)


@router.get(
    "/{connection_id}/imports",
    response_model=Page[MarketDataImportRecord],
)
def list_historical_imports(
    connection_id: str,
    connections: ConnectionRepositoryDependency,
    history: ImportHistoryRepositoryDependency,
    params: ImportHistoryQuery,
) -> Page[MarketDataImportRecord]:
    """List newest-first immutable import attempts for one configured connection."""

    if connections.get(connection_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="market-data connection not found",
        )

    records = history.list_page(
        connection_id=connection_id,
        status=params.status,
        limit=params.limit,
        offset=params.offset,
    )
    return build_page(
        records,
        total=history.count(connection_id=connection_id, status=params.status),
        pagination=params,
    )


@router.get(
    "/{connection_id}/imports/{import_id}/versions",
    response_model=Page[MarketDataImportRecord],
)
def list_historical_import_versions(
    connection_id: str,
    import_id: str,
    connections: ConnectionRepositoryDependency,
    history: ImportHistoryRepositoryDependency,
    pagination: VersionHistoryQuery,
) -> Page[MarketDataImportRecord]:
    """Return newest-first version and refresh attempts for one dataset lineage."""

    record = _get_import_or_404(
        connection_id=connection_id,
        import_id=import_id,
        connections=connections,
        history=history,
    )
    if record.root_import_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="market-data import does not identify a dataset version lineage",
        )

    records = history.list_page(
        root_import_id=record.root_import_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return build_page(
        records,
        total=history.count(root_import_id=record.root_import_id),
        pagination=pagination,
    )


@router.post(
    "/{connection_id}/imports/{import_id}/refresh",
    response_model=MarketDataImportRecord,
    status_code=status.HTTP_201_CREATED,
)
async def refresh_historical_import(
    connection_id: str,
    import_id: str,
    connections: ConnectionRepositoryDependency,
    providers: ProviderCatalogDependency,
    datasets: DatasetRepositoryDependency,
    history: ImportHistoryRepositoryDependency,
) -> MarketDataImportRecord:
    """Re-fetch the latest immutable dataset version and record a new lineage event."""

    source_record = _get_import_or_404(
        connection_id=connection_id,
        import_id=import_id,
        connections=connections,
        history=history,
    )
    if (
        source_record.status is not MarketDataImportStatus.SUCCEEDED
        or source_record.dataset_id is None
        or source_record.root_import_id is None
        or source_record.version_number is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="market-data import does not identify a refreshable dataset version",
        )

    latest = history.get_latest_successful_version(source_record.root_import_id)
    if latest is None or latest.import_id != source_record.import_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only the latest successful dataset version can be refreshed",
        )

    if datasets.get(source_record.dataset_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="source dataset not found",
        )

    refresh_id = f"market-data-import-{uuid4().hex}"
    created_at = datetime.now(UTC)
    request = HistoricalDatasetImportRequest(
        name=source_record.dataset_name,
        pair=source_record.pair,
        timeframe=source_record.timeframe,
        start_time=source_record.requested_start_time,
        end_time=source_record.requested_end_time,
    )
    service = _service(
        connections=connections,
        providers=providers,
        datasets=datasets,
    )

    try:
        dataset = await service.import_dataset(
            connection_id=connection_id,
            import_id=refresh_id,
            name=request.name,
            pair=request.pair,
            timeframe=request.timeframe,
            start_time=request.start_time,
            end_time=request.end_time,
        )
    except InvalidDatasetError as error:
        _save_import_history(
            repository=history,
            import_id=refresh_id,
            connection_id=connection_id,
            provider_id=source_record.provider_id,
            request=request,
            created_at=created_at,
            status_value=MarketDataImportStatus.FAILED,
            candle_count=error.report.candles_checked,
            error=error,
            operation=MarketDataImportOperation.REFRESH,
            source_dataset_id=source_record.dataset_id,
            root_import_id=source_record.root_import_id,
            parent_import_id=source_record.import_id,
        )
        _raise_quality_error(error)
    except (
        MarketDataConnectionNotFoundError,
        MarketDataConnectionStateError,
        MarketDataProviderUnavailableError,
        HistoricalDatasetProviderCapabilityError,
        HistoricalDatasetImportLimitError,
        MarketDataProviderError,
    ) as error:
        _save_import_history(
            repository=history,
            import_id=refresh_id,
            connection_id=connection_id,
            provider_id=source_record.provider_id,
            request=request,
            created_at=created_at,
            status_value=MarketDataImportStatus.FAILED,
            candle_count=0,
            error=error,
            operation=MarketDataImportOperation.REFRESH,
            source_dataset_id=source_record.dataset_id,
            root_import_id=source_record.root_import_id,
            parent_import_id=source_record.import_id,
        )
        _raise_fetch_error(error)

    return _save_import_history(
        repository=history,
        import_id=refresh_id,
        connection_id=connection_id,
        provider_id=dataset.source,
        request=request,
        created_at=created_at,
        status_value=MarketDataImportStatus.SUCCEEDED,
        candle_count=dataset.candle_count,
        dataset_id=dataset.dataset_id,
        operation=MarketDataImportOperation.REFRESH,
        source_dataset_id=source_record.dataset_id,
        root_import_id=source_record.root_import_id,
        parent_import_id=source_record.import_id,
        version_number=source_record.version_number + 1,
        content_changed=dataset.dataset_id != source_record.dataset_id,
    )


@router.get(
    "/{connection_id}/imports/{import_id}",
    response_model=MarketDataImportRecord,
)
def get_historical_import(
    connection_id: str,
    import_id: str,
    connections: ConnectionRepositoryDependency,
    history: ImportHistoryRepositoryDependency,
) -> MarketDataImportRecord:
    """Return one immutable historical import audit record."""

    return _get_import_or_404(
        connection_id=connection_id,
        import_id=import_id,
        connections=connections,
        history=history,
    )
