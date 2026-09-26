from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data import (
    DataQualityReport,
    MarketDataConnectionNotFoundError,
    MarketDataConnectionRepository,
    MarketDataConnectionStateError,
    MarketDataProviderCatalog,
    MarketDataProviderError,
    MarketDataProviderErrorCode,
    MarketDataProviderUnavailableError,
    redact_sensitive_text,
)
from trd_bot.market_data.import_history import (
    MarketDataImportOperation,
    MarketDataImportRecord,
    MarketDataImportRepository,
    MarketDataImportStatus,
)
from trd_bot.research.datasets import DatasetRepository, InvalidDatasetError
from trd_bot.research.historical_dataset_commits import (
    HistoricalDatasetCommitter,
    HistoricalDatasetRefreshConflictError,
)
from trd_bot.research.historical_dataset_imports import (
    HistoricalDatasetImportLimitError,
    HistoricalDatasetImportService,
    HistoricalDatasetPreviewMismatchError,
    HistoricalDatasetProviderCapabilityError,
)


class HistoricalDatasetJobOperation(StrEnum):
    IMPORT = "import"
    REFRESH = "refresh"


class HistoricalDatasetJobRequest(BaseModel):
    """Serializable request persisted inside a durable market-data job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    pair: TradingPair
    timeframe: Timeframe
    start_time: AwareDatetime
    end_time: AwareDatetime
    preview_checksum: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

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


class HistoricalDatasetJobPayload(BaseModel):
    """Version-one allowlisted payload for import and refresh jobs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: HistoricalDatasetJobOperation
    connection_id: str = Field(min_length=1, max_length=100)
    request: HistoricalDatasetJobRequest | None = None
    source_import_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_operation(self) -> Self:
        if self.operation is HistoricalDatasetJobOperation.IMPORT:
            if (
                self.request is None
                or self.request.preview_checksum is None
                or self.source_import_id is not None
            ):
                raise ValueError("import job requires a request and no source import")
        elif self.request is not None or self.source_import_id is None:
            raise ValueError("refresh job requires a source import and no request")
        return self


ProgressReporter = Callable[[int], None]
CancellationCheck = Callable[[], bool]


class HistoricalDatasetJobRunner:
    """Execute one durable import attempt using domain repositories."""

    def __init__(
        self,
        *,
        connections: MarketDataConnectionRepository,
        providers: MarketDataProviderCatalog,
        datasets: DatasetRepository,
        history: MarketDataImportRepository,
        committer: HistoricalDatasetCommitter,
    ) -> None:
        self._connections = connections
        self._providers = providers
        self._datasets = datasets
        self._history = history
        self._committer = committer

    async def run(
        self,
        *,
        payload: HistoricalDatasetJobPayload,
        import_id: str,
        created_at: datetime,
        report_progress: ProgressReporter,
        cancellation_requested: CancellationCheck,
    ) -> MarketDataImportRecord | None:
        if cancellation_requested():
            return None
        report_progress(10)

        if payload.operation is HistoricalDatasetJobOperation.IMPORT:
            assert payload.request is not None
            return await self._run_import(
                payload=payload,
                request=payload.request,
                import_id=import_id,
                created_at=created_at,
                report_progress=report_progress,
                cancellation_requested=cancellation_requested,
            )

        assert payload.source_import_id is not None
        return await self._run_refresh(
            payload=payload,
            source_import_id=payload.source_import_id,
            import_id=import_id,
            created_at=created_at,
            report_progress=report_progress,
            cancellation_requested=cancellation_requested,
        )

    async def _run_import(
        self,
        *,
        payload: HistoricalDatasetJobPayload,
        request: HistoricalDatasetJobRequest,
        import_id: str,
        created_at: datetime,
        report_progress: ProgressReporter,
        cancellation_requested: CancellationCheck,
    ) -> MarketDataImportRecord | None:
        service = self._service()
        tracked_connection = self._connections.get(payload.connection_id)
        try:
            dataset = await service.build_dataset(
                connection_id=payload.connection_id,
                import_id=import_id,
                name=request.name,
                pair=request.pair,
                timeframe=request.timeframe,
                start_time=request.start_time,
                end_time=request.end_time,
                expected_preview_checksum=request.preview_checksum,
            )
        except InvalidDatasetError as error:
            if tracked_connection is not None:
                self._history.save(
                    _build_record(
                        import_id=import_id,
                        connection_id=tracked_connection.connection_id,
                        provider_id=tracked_connection.provider_id,
                        request=request,
                        created_at=created_at,
                        status_value=MarketDataImportStatus.FAILED,
                        candle_count=error.report.candles_checked,
                        error=error,
                        quality_report=error.report,
                    )
                )
            raise
        except (
            MarketDataConnectionNotFoundError,
            MarketDataConnectionStateError,
            MarketDataProviderUnavailableError,
            HistoricalDatasetProviderCapabilityError,
            HistoricalDatasetImportLimitError,
            HistoricalDatasetPreviewMismatchError,
            MarketDataProviderError,
        ) as error:
            if tracked_connection is not None:
                self._history.save(
                    _build_record(
                        import_id=import_id,
                        connection_id=tracked_connection.connection_id,
                        provider_id=tracked_connection.provider_id,
                        request=request,
                        created_at=created_at,
                        status_value=MarketDataImportStatus.FAILED,
                        candle_count=0,
                        error=error,
                    )
                )
            raise

        report_progress(75)
        if cancellation_requested():
            return None
        record = _build_record(
            import_id=import_id,
            connection_id=payload.connection_id,
            provider_id=dataset.source,
            request=request,
            created_at=created_at,
            status_value=MarketDataImportStatus.SUCCEEDED,
            candle_count=dataset.candle_count,
            dataset_id=dataset.dataset_id,
            quality_report=dataset.quality_report,
        )
        result = self._committer.commit(dataset=dataset, record=record)
        report_progress(95)
        return result.record

    async def _run_refresh(
        self,
        *,
        payload: HistoricalDatasetJobPayload,
        source_import_id: str,
        import_id: str,
        created_at: datetime,
        report_progress: ProgressReporter,
        cancellation_requested: CancellationCheck,
    ) -> MarketDataImportRecord | None:
        source_record = self._refreshable_source(payload.connection_id, source_import_id)
        request = HistoricalDatasetJobRequest(
            name=source_record.dataset_name,
            pair=source_record.pair,
            timeframe=source_record.timeframe,
            start_time=source_record.requested_start_time,
            end_time=source_record.requested_end_time,
        )
        try:
            dataset = await self._service().build_dataset(
                connection_id=payload.connection_id,
                import_id=import_id,
                name=request.name,
                pair=request.pair,
                timeframe=request.timeframe,
                start_time=request.start_time,
                end_time=request.end_time,
            )
        except (
            InvalidDatasetError,
            MarketDataConnectionNotFoundError,
            MarketDataConnectionStateError,
            MarketDataProviderUnavailableError,
            HistoricalDatasetProviderCapabilityError,
            HistoricalDatasetImportLimitError,
            HistoricalDatasetPreviewMismatchError,
            MarketDataProviderError,
        ) as error:
            quality_report = error.report if isinstance(error, InvalidDatasetError) else None
            self._history.save(
                _build_record(
                    import_id=import_id,
                    connection_id=payload.connection_id,
                    provider_id=source_record.provider_id,
                    request=request,
                    created_at=created_at,
                    status_value=MarketDataImportStatus.FAILED,
                    candle_count=(quality_report.candles_checked if quality_report else 0),
                    error=error,
                    quality_report=quality_report,
                    operation=MarketDataImportOperation.REFRESH,
                    source_dataset_id=source_record.dataset_id,
                    root_import_id=source_record.root_import_id,
                    parent_import_id=source_record.import_id,
                )
            )
            raise

        report_progress(75)
        if cancellation_requested():
            return None
        assert source_record.dataset_id is not None
        assert source_record.root_import_id is not None
        assert source_record.version_number is not None
        record = _build_record(
            import_id=import_id,
            connection_id=payload.connection_id,
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
            quality_report=dataset.quality_report,
        )
        try:
            result = self._committer.commit(
                dataset=dataset,
                record=record,
                expected_parent_import_id=source_record.import_id,
            )
        except HistoricalDatasetRefreshConflictError as error:
            self._history.save(
                _build_record(
                    import_id=import_id,
                    connection_id=payload.connection_id,
                    provider_id=source_record.provider_id,
                    request=request,
                    created_at=created_at,
                    status_value=MarketDataImportStatus.FAILED,
                    candle_count=dataset.candle_count,
                    error=error,
                    quality_report=dataset.quality_report,
                    operation=MarketDataImportOperation.REFRESH,
                    source_dataset_id=source_record.dataset_id,
                    root_import_id=source_record.root_import_id,
                    parent_import_id=source_record.import_id,
                )
            )
            raise
        report_progress(95)
        return result.record

    def _refreshable_source(
        self,
        connection_id: str,
        source_import_id: str,
    ) -> MarketDataImportRecord:
        source = self._history.get(source_import_id)
        if source is None or source.connection_id != connection_id:
            raise ValueError("market-data import not found")
        if (
            source.status is not MarketDataImportStatus.SUCCEEDED
            or source.dataset_id is None
            or source.root_import_id is None
            or source.version_number is None
        ):
            raise ValueError("market-data import is not refreshable")
        latest = self._history.get_latest_successful_version(source.root_import_id)
        if latest is None or latest.import_id != source.import_id:
            raise HistoricalDatasetRefreshConflictError(
                "only the latest successful dataset version can be refreshed"
            )
        if self._datasets.get(source.dataset_id) is None:
            raise ValueError("source dataset not found")
        return source

    def _service(self) -> HistoricalDatasetImportService:
        return HistoricalDatasetImportService(
            connections=self._connections,
            providers=self._providers,
        )


def _history_error_code(error: Exception) -> str:
    if isinstance(error, InvalidDatasetError):
        return "quality_check_failed"
    if isinstance(error, MarketDataConnectionStateError):
        return "connection_state_invalid"
    if isinstance(error, HistoricalDatasetProviderCapabilityError):
        return "provider_capability_unsupported"
    if isinstance(error, HistoricalDatasetImportLimitError):
        return "import_limit_exceeded"
    if isinstance(error, HistoricalDatasetPreviewMismatchError):
        return "preview_mismatch"
    if isinstance(error, HistoricalDatasetRefreshConflictError):
        return "refresh_conflict"
    if isinstance(error, MarketDataProviderUnavailableError):
        return MarketDataProviderErrorCode.UNAVAILABLE.value
    if isinstance(error, MarketDataProviderError):
        return error.code.value
    return MarketDataProviderErrorCode.REQUEST_FAILED.value


def _build_record(
    *,
    import_id: str,
    connection_id: str,
    provider_id: str,
    request: HistoricalDatasetJobRequest,
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
    quality_report: DataQualityReport | None = None,
) -> MarketDataImportRecord:
    error_code = None
    error_message = None
    if error is not None:
        error_code = _history_error_code(error)
        error_message = redact_sensitive_text(error, fallback=error.__class__.__name__)
    return MarketDataImportRecord(
        import_id=import_id,
        connection_id=connection_id,
        provider_id=provider_id,
        dataset_name=request.name,
        pair=request.pair,
        timeframe=request.timeframe,
        requested_start_time=request.start_time,
        requested_end_time=request.end_time,
        created_at=created_at.astimezone(UTC),
        completed_at=datetime.now(UTC),
        status=status_value,
        candle_count=candle_count,
        dataset_id=dataset_id,
        error_code=error_code,
        error_message=error_message,
        quality_report=quality_report,
        operation=operation,
        source_dataset_id=source_dataset_id,
        root_import_id=root_import_id,
        parent_import_id=parent_import_id,
        version_number=version_number,
        content_changed=content_changed,
    )
