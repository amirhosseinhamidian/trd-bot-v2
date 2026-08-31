from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair


class MarketDataImportStatus(StrEnum):
    """Final status of one synchronous historical dataset import attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MarketDataImportOperation(StrEnum):
    """Operation that produced one immutable market-data audit record."""

    IMPORT = "import"
    REFRESH = "refresh"


class MarketDataImportRecord(BaseModel):
    """Immutable audit record for one historical dataset import attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    import_id: str = Field(min_length=1, max_length=100)
    connection_id: str = Field(min_length=1, max_length=100)
    provider_id: str = Field(min_length=1, max_length=100)
    dataset_name: str = Field(min_length=1, max_length=100)
    pair: TradingPair
    timeframe: Timeframe
    requested_start_time: datetime
    requested_end_time: datetime
    created_at: datetime
    completed_at: datetime
    status: MarketDataImportStatus
    candle_count: int = Field(ge=0)
    dataset_id: str | None = Field(default=None, min_length=1, max_length=100)
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    error_message: str | None = Field(default=None, min_length=1, max_length=500)

    operation: MarketDataImportOperation = MarketDataImportOperation.IMPORT
    source_dataset_id: str | None = Field(default=None, min_length=1, max_length=100)
    root_import_id: str | None = Field(default=None, min_length=1, max_length=100)
    parent_import_id: str | None = Field(default=None, min_length=1, max_length=100)
    version_number: int | None = Field(default=None, ge=1)
    content_changed: bool | None = None

    @field_validator("import_id", "connection_id", "provider_id", "dataset_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("import history text fields cannot be empty")
        return normalized

    @field_validator(
        "dataset_id",
        "error_code",
        "error_message",
        "source_dataset_id",
        "root_import_id",
        "parent_import_id",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("import history optional text cannot be empty")
        return normalized

    @field_validator(
        "requested_start_time",
        "requested_end_time",
        "created_at",
        "completed_at",
    )
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("import history timestamps must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.requested_end_time <= self.requested_start_time:
            raise ValueError("requested end time must be after requested start time")
        if self.completed_at < self.created_at:
            raise ValueError("completed time cannot be before created time")

        if self.status is MarketDataImportStatus.SUCCEEDED:
            if self.dataset_id is None:
                raise ValueError("successful import must reference a dataset")
            if self.candle_count <= 0:
                raise ValueError("successful import must contain candles")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("successful import cannot contain failure metadata")
        else:
            if self.dataset_id is not None:
                raise ValueError("failed import cannot reference a dataset")
            if self.error_code is None or self.error_message is None:
                raise ValueError("failed import must contain failure metadata")

        if self.operation is MarketDataImportOperation.IMPORT:
            if (
                self.source_dataset_id is not None
                or self.parent_import_id is not None
                or self.content_changed is not None
            ):
                raise ValueError("initial import cannot contain refresh lineage metadata")

            has_version_lineage = (
                self.root_import_id is not None or self.version_number is not None
            )
            if has_version_lineage:
                if self.status is not MarketDataImportStatus.SUCCEEDED:
                    raise ValueError("failed initial import cannot define a dataset version")
                if self.root_import_id != self.import_id or self.version_number != 1:
                    raise ValueError("initial import lineage must identify version one as its root")
        else:
            if self.source_dataset_id is None:
                raise ValueError("refresh must reference its source dataset")
            if self.root_import_id is None or self.parent_import_id is None:
                raise ValueError("refresh must reference root and parent imports")

            if self.status is MarketDataImportStatus.SUCCEEDED:
                if self.version_number is None or self.version_number < 2:
                    raise ValueError("successful refresh must define version two or greater")
                if self.content_changed is None:
                    raise ValueError("successful refresh must record whether content changed")
            else:
                if self.version_number is not None or self.content_changed is not None:
                    raise ValueError("failed refresh cannot claim a completed dataset version")

        return self


class MarketDataImportRepository(Protocol):
    """Persistence contract for immutable historical import records."""

    def save(self, record: MarketDataImportRecord) -> MarketDataImportRecord: ...

    def get(self, import_id: str) -> MarketDataImportRecord | None: ...

    def count(
        self,
        *,
        connection_id: str | None = None,
        status: MarketDataImportStatus | None = None,
        root_import_id: str | None = None,
        dataset_id: str | None = None,
    ) -> int: ...

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        connection_id: str | None = None,
        status: MarketDataImportStatus | None = None,
        root_import_id: str | None = None,
        dataset_id: str | None = None,
    ) -> tuple[MarketDataImportRecord, ...]: ...

    def get_latest_successful_version(
        self,
        root_import_id: str,
    ) -> MarketDataImportRecord | None: ...


class InMemoryMarketDataImportRepository:
    """In-memory immutable import history used by tests and isolated workflows."""

    def __init__(self) -> None:
        self._records: dict[str, MarketDataImportRecord] = {}

    def save(self, record: MarketDataImportRecord) -> MarketDataImportRecord:
        existing = self._records.get(record.import_id)
        if existing is not None:
            if existing != record:
                raise ValueError("market-data import ID already exists with different content")
            return existing

        self._records[record.import_id] = record
        return record

    def get(self, import_id: str) -> MarketDataImportRecord | None:
        return self._records.get(import_id)

    def count(
        self,
        *,
        connection_id: str | None = None,
        status: MarketDataImportStatus | None = None,
        root_import_id: str | None = None,
        dataset_id: str | None = None,
    ) -> int:
        return len(
            self._filter(
                connection_id=connection_id,
                status=status,
                root_import_id=root_import_id,
                dataset_id=dataset_id,
            )
        )

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        connection_id: str | None = None,
        status: MarketDataImportStatus | None = None,
        root_import_id: str | None = None,
        dataset_id: str | None = None,
    ) -> tuple[MarketDataImportRecord, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        records = sorted(
            self._filter(
                connection_id=connection_id,
                status=status,
                root_import_id=root_import_id,
                dataset_id=dataset_id,
            ),
            key=lambda record: (record.created_at, record.import_id),
            reverse=True,
        )
        return tuple(records[offset : offset + limit])

    def get_latest_successful_version(
        self,
        root_import_id: str,
    ) -> MarketDataImportRecord | None:
        versions = tuple(
            record
            for record in self._records.values()
            if record.root_import_id == root_import_id
            and record.status is MarketDataImportStatus.SUCCEEDED
            and record.version_number is not None
        )
        if not versions:
            return None
        return max(
            versions,
            key=lambda record: (record.version_number or 0, record.created_at, record.import_id),
        )

    def _filter(
        self,
        *,
        connection_id: str | None,
        status: MarketDataImportStatus | None,
        root_import_id: str | None,
        dataset_id: str | None,
    ) -> tuple[MarketDataImportRecord, ...]:
        return tuple(
            record
            for record in self._records.values()
            if (connection_id is None or record.connection_id == connection_id)
            and (status is None or record.status is status)
            and (root_import_id is None or record.root_import_id == root_import_id)
            and (dataset_id is None or record.dataset_id == dataset_id)
        )
