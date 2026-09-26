import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from io import BytesIO, StringIO
from pathlib import PurePath
from typing import Final, Self

import pyarrow.parquet as parquet  # type: ignore[import-untyped]
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data.quality import DataQualityReport, MarketDataQualityChecker
from trd_bot.research.datasets import (
    DatasetBuilder,
    DatasetProvenance,
    DatasetProvenanceKind,
    DatasetSnapshot,
    calculate_dataset_checksum,
)

MAX_DATASET_FILE_BYTES: Final = 10 * 1024 * 1024
MAX_DATASET_FILE_ROWS: Final = 100_000
MAX_DATASET_FILE_COLUMNS: Final = 100
MAX_DATASET_FILE_CELLS: Final = 1_000_000
MAX_DATASET_FILE_NAME_LENGTH: Final = 255

_TIMEFRAME_INTERVALS: Final[dict[Timeframe, timedelta]] = {
    Timeframe.MINUTES_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.HOURS_4: timedelta(hours=4),
    Timeframe.DAY_1: timedelta(days=1),
}
_AWARE_DATETIME = TypeAdapter(AwareDatetime)
_DECIMAL = TypeAdapter(Decimal)


class DatasetFileFormat(StrEnum):
    """Supported historical dataset file containers."""

    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"


class DatasetFileField(StrEnum):
    """Canonical OHLCV fields accepted by the file importer."""

    OPEN_TIME = "open_time"
    CLOSE_TIME = "close_time"
    OPEN_PRICE = "open_price"
    HIGH_PRICE = "high_price"
    LOW_PRICE = "low_price"
    CLOSE_PRICE = "close_price"
    VOLUME = "volume"
    IS_CLOSED = "is_closed"


REQUIRED_DATASET_FILE_FIELDS: Final = (
    DatasetFileField.OPEN_TIME,
    DatasetFileField.OPEN_PRICE,
    DatasetFileField.HIGH_PRICE,
    DatasetFileField.LOW_PRICE,
    DatasetFileField.CLOSE_PRICE,
    DatasetFileField.VOLUME,
)

_FIELD_ALIASES: Final[dict[DatasetFileField, tuple[str, ...]]] = {
    DatasetFileField.OPEN_TIME: (
        "open_time",
        "opentime",
        "open_timestamp",
        "timestamp",
        "time",
        "date",
        "datetime",
    ),
    DatasetFileField.CLOSE_TIME: ("close_time", "closetime", "close_timestamp"),
    DatasetFileField.OPEN_PRICE: ("open_price", "openprice", "open", "o"),
    DatasetFileField.HIGH_PRICE: ("high_price", "highprice", "high", "h"),
    DatasetFileField.LOW_PRICE: ("low_price", "lowprice", "low", "l"),
    DatasetFileField.CLOSE_PRICE: ("close_price", "closeprice", "close", "c"),
    DatasetFileField.VOLUME: ("volume", "vol", "base_volume", "v"),
    DatasetFileField.IS_CLOSED: ("is_closed", "closed", "isclosed"),
}


class DatasetFileImportErrorCode(StrEnum):
    """Stable machine-readable failure reasons for file ingestion."""

    EMPTY_FILE = "empty_file"
    FILE_TOO_LARGE = "file_too_large"
    UNSUPPORTED_FORMAT = "unsupported_format"
    INVALID_ENCODING = "invalid_encoding"
    INVALID_FILE_NAME = "invalid_file_name"
    MALFORMED_FILE = "malformed_file"
    EMPTY_DATASET = "empty_dataset"
    TOO_MANY_ROWS = "too_many_rows"
    TOO_MANY_COLUMNS = "too_many_columns"
    TOO_MANY_CELLS = "too_many_cells"
    DUPLICATE_COLUMN = "duplicate_column"
    INVALID_COLUMN = "invalid_column"
    INVALID_REQUEST = "invalid_request"
    INVALID_MAPPING = "invalid_mapping"
    INVALID_ROW = "invalid_row"
    PREVIEW_MISMATCH = "preview_mismatch"
    QUALITY_REJECTED = "quality_rejected"


class DatasetFileImportError(ValueError):
    """Expected validation failure suitable for a stable API response."""

    def __init__(
        self,
        code: DatasetFileImportErrorCode,
        message: str,
        *,
        row_number: int | None = None,
        column: str | None = None,
        quality_report: DataQualityReport | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.row_number = row_number
        self.column = column
        self.quality_report = quality_report

    def detail(self) -> dict[str, object]:
        detail: dict[str, object] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.row_number is not None:
            detail["row_number"] = self.row_number
        if self.column is not None:
            detail["column"] = self.column
        if self.quality_report is not None:
            detail["quality_report"] = self.quality_report.model_dump(mode="json")
        return detail


class DatasetColumnMapping(BaseModel):
    """Explicit mapping from canonical OHLCV fields to source columns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    open_time: str = Field(min_length=1, max_length=200)
    open_price: str = Field(min_length=1, max_length=200)
    high_price: str = Field(min_length=1, max_length=200)
    low_price: str = Field(min_length=1, max_length=200)
    close_price: str = Field(min_length=1, max_length=200)
    volume: str = Field(min_length=1, max_length=200)
    close_time: str | None = Field(default=None, min_length=1, max_length=200)
    is_closed: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_column_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def reject_duplicate_source_columns(self) -> Self:
        selected = [value for value in self.model_dump().values() if value is not None]
        if len(selected) != len(set(selected)):
            raise ValueError("one source column cannot map to multiple canonical fields")
        return self

    def source_columns(self) -> tuple[str, ...]:
        return tuple(value for value in self.model_dump().values() if value is not None)


class DatasetFileInspection(BaseModel):
    """Safe structural inspection returned before a file is interpreted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_name: str
    file_format: DatasetFileFormat
    file_size_bytes: int = Field(ge=1, le=MAX_DATASET_FILE_BYTES)
    file_checksum: str = Field(min_length=64, max_length=64)
    row_count: int = Field(ge=0, le=MAX_DATASET_FILE_ROWS)
    columns: tuple[str, ...]
    suggested_mapping: dict[DatasetFileField, str]
    missing_required_fields: tuple[DatasetFileField, ...]
    can_preview: bool


class DatasetFilePreviewRequest(BaseModel):
    """Dataset identity and explicit interpretation selected by the operator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    column_mapping: DatasetColumnMapping

    @field_validator("name", "source")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized


class DatasetFileCommitRequest(DatasetFilePreviewRequest):
    """Preview-bound request used to create an immutable snapshot."""

    preview_checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class DatasetFileImportPreview(BaseModel):
    """Canonical interpretation and quality evidence produced before commit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    inspection: DatasetFileInspection
    column_mapping: DatasetColumnMapping
    candle_count: int = Field(gt=0, le=MAX_DATASET_FILE_ROWS)
    first_open_time: datetime
    last_close_time: datetime
    preview_checksum: str = Field(min_length=64, max_length=64)
    quality_report: DataQualityReport
    ready_to_import: bool


class _ParsedFile(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    inspection: DatasetFileInspection
    rows: tuple[Mapping[str, object], ...]


def _safe_file_name(file_name: str) -> str:
    normalized = PurePath(file_name.replace("\\", "/")).name.strip()
    safe_name = normalized or "dataset"
    if len(safe_name) > MAX_DATASET_FILE_NAME_LENGTH:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.INVALID_FILE_NAME,
            f"dataset file name cannot exceed {MAX_DATASET_FILE_NAME_LENGTH} characters",
        )
    return safe_name


def _detect_format(file_name: str) -> DatasetFileFormat:
    suffix = PurePath(file_name).suffix.lower()
    formats = {
        ".csv": DatasetFileFormat.CSV,
        ".json": DatasetFileFormat.JSON,
        ".parquet": DatasetFileFormat.PARQUET,
    }
    try:
        return formats[suffix]
    except KeyError as error:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.UNSUPPORTED_FORMAT,
            "only .csv, .json, and .parquet dataset files are supported",
        ) from error


def _validate_content(content: bytes) -> None:
    if not content:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.EMPTY_FILE,
            "dataset file cannot be empty",
        )
    if len(content) > MAX_DATASET_FILE_BYTES:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.FILE_TOO_LARGE,
            f"dataset file cannot exceed {MAX_DATASET_FILE_BYTES} bytes",
        )


def _validate_columns(columns: Sequence[object]) -> tuple[str, ...]:
    if len(columns) > MAX_DATASET_FILE_COLUMNS:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.TOO_MANY_COLUMNS,
            f"dataset file cannot contain more than {MAX_DATASET_FILE_COLUMNS} columns",
        )

    normalized: list[str] = []
    for raw_column in columns:
        column = str(raw_column).strip()
        if not column:
            raise DatasetFileImportError(
                DatasetFileImportErrorCode.INVALID_COLUMN,
                "dataset file contains an empty column name",
            )
        if column in normalized:
            raise DatasetFileImportError(
                DatasetFileImportErrorCode.DUPLICATE_COLUMN,
                f'dataset file contains duplicate column "{column}"',
                column=column,
            )
        normalized.append(column)

    if not normalized:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.EMPTY_DATASET,
            "dataset file does not contain columns",
        )
    return tuple(normalized)


def _validate_row_count(row_count: int) -> None:
    if row_count == 0:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.EMPTY_DATASET,
            "dataset file does not contain data rows",
        )
    if row_count > MAX_DATASET_FILE_ROWS:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.TOO_MANY_ROWS,
            f"dataset file cannot contain more than {MAX_DATASET_FILE_ROWS} rows",
        )


def _validate_cell_count(row_count: int, column_count: int) -> None:
    if row_count * column_count > MAX_DATASET_FILE_CELLS:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.TOO_MANY_CELLS,
            f"dataset file cannot contain more than {MAX_DATASET_FILE_CELLS} cells",
        )


def _parse_csv(content: bytes) -> tuple[tuple[str, ...], tuple[Mapping[str, object], ...]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.INVALID_ENCODING,
            "CSV files must use UTF-8 encoding",
        ) from error

    try:
        reader = csv.reader(StringIO(text, newline=""), strict=True)
        raw_rows = list(reader)
    except csv.Error as error:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.MALFORMED_FILE,
            "CSV structure is malformed",
        ) from error

    nonempty_rows = [row for row in raw_rows if any(cell.strip() for cell in row)]
    if not nonempty_rows:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.EMPTY_DATASET,
            "CSV file does not contain a header or data rows",
        )

    columns = _validate_columns(nonempty_rows[0])
    data_rows = nonempty_rows[1:]
    _validate_row_count(len(data_rows))
    _validate_cell_count(len(data_rows), len(columns))

    rows: list[Mapping[str, object]] = []
    for row_number, raw_row in enumerate(data_rows, start=2):
        if len(raw_row) != len(columns):
            raise DatasetFileImportError(
                DatasetFileImportErrorCode.MALFORMED_FILE,
                "CSV row has a different number of values than the header",
                row_number=row_number,
            )
        rows.append(dict(zip(columns, raw_row, strict=True)))
    return columns, tuple(rows)


def _parse_json(content: bytes) -> tuple[tuple[str, ...], tuple[Mapping[str, object], ...]]:
    try:
        payload = json.loads(content.decode("utf-8-sig"), parse_float=Decimal)
    except UnicodeDecodeError as error:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.INVALID_ENCODING,
            "JSON files must use UTF-8 encoding",
        ) from error
    except (json.JSONDecodeError, UnicodeError) as error:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.MALFORMED_FILE,
            "JSON structure is malformed",
        ) from error

    if isinstance(payload, dict) and set(payload) == {"candles"}:
        payload = payload["candles"]
    if not isinstance(payload, list):
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.MALFORMED_FILE,
            'JSON must be an array of objects or an object containing only a "candles" array',
        )

    _validate_row_count(len(payload))
    if not all(isinstance(row, dict) for row in payload):
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.MALFORMED_FILE,
            "every JSON dataset row must be an object",
        )

    first_row = payload[0]
    assert isinstance(first_row, dict)
    columns = _validate_columns(tuple(first_row))
    _validate_cell_count(len(payload), len(columns))
    expected_columns = set(columns)
    rows: list[Mapping[str, object]] = []
    for row_number, raw_row in enumerate(payload, start=1):
        assert isinstance(raw_row, dict)
        if set(raw_row) != expected_columns:
            raise DatasetFileImportError(
                DatasetFileImportErrorCode.MALFORMED_FILE,
                "JSON rows must all contain the same columns",
                row_number=row_number,
            )
        rows.append(raw_row)
    return columns, tuple(rows)


def _parse_parquet(content: bytes) -> tuple[tuple[str, ...], tuple[Mapping[str, object], ...]]:
    if not content.startswith(b"PAR1") or not content.endswith(b"PAR1"):
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.MALFORMED_FILE,
            "Parquet file signature is invalid",
        )

    try:
        parquet_file = parquet.ParquetFile(BytesIO(content))
        columns = _validate_columns(parquet_file.schema_arrow.names)
        row_count = parquet_file.metadata.num_rows
        _validate_row_count(row_count)
        _validate_cell_count(row_count, len(columns))
        decoded_rows = parquet_file.read().to_pylist()
    except DatasetFileImportError:
        raise
    except Exception as error:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.MALFORMED_FILE,
            "Parquet structure is malformed or unsupported",
        ) from error

    if len(decoded_rows) != row_count:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.MALFORMED_FILE,
            "Parquet metadata row count does not match decoded rows",
        )
    rows: list[Mapping[str, object]] = []
    expected_columns = set(columns)
    for row_number, raw_row in enumerate(decoded_rows, start=1):
        if not isinstance(raw_row, dict) or set(raw_row) != expected_columns:
            raise DatasetFileImportError(
                DatasetFileImportErrorCode.MALFORMED_FILE,
                "Parquet rows must all contain the declared columns",
                row_number=row_number,
            )
        rows.append(raw_row)
    return columns, tuple(rows)


def _suggest_mapping(columns: Sequence[str]) -> dict[DatasetFileField, str]:
    normalized = {column.lower().replace(" ", "_").replace("-", "_"): column for column in columns}
    suggestions: dict[DatasetFileField, str] = {}
    for field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                suggestions[field] = normalized[alias]
                break
    return suggestions


def _parse_file(file_name: str, content: bytes) -> _ParsedFile:
    safe_name = _safe_file_name(file_name)
    file_format = _detect_format(safe_name)
    _validate_content(content)

    if file_format is DatasetFileFormat.CSV:
        columns, rows = _parse_csv(content)
    elif file_format is DatasetFileFormat.JSON:
        columns, rows = _parse_json(content)
    else:
        columns, rows = _parse_parquet(content)

    suggestions = _suggest_mapping(columns)
    missing = tuple(field for field in REQUIRED_DATASET_FILE_FIELDS if field not in suggestions)
    inspection = DatasetFileInspection(
        file_name=safe_name,
        file_format=file_format,
        file_size_bytes=len(content),
        file_checksum=hashlib.sha256(content).hexdigest(),
        row_count=len(rows),
        columns=columns,
        suggested_mapping=suggestions,
        missing_required_fields=missing,
        can_preview=not missing,
    )
    return _ParsedFile(inspection=inspection, rows=rows)


def _mapping_error(error: ValidationError) -> DatasetFileImportError:
    first_error = error.errors(include_url=False)[0]
    location = first_error.get("loc", ())
    column = str(location[0]) if location else None
    return DatasetFileImportError(
        DatasetFileImportErrorCode.INVALID_ROW,
        str(first_error.get("msg", "dataset row is invalid")),
        column=column,
    )


def _require_value(row: Mapping[str, object], source_column: str, row_number: int) -> object:
    value = row.get(source_column)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.INVALID_ROW,
            "required dataset value cannot be empty",
            row_number=row_number,
            column=source_column,
        )
    return value.strip() if isinstance(value, str) else value


def _require_decimal(
    row: Mapping[str, object],
    source_column: str,
    row_number: int,
) -> Decimal:
    value = _require_value(row, source_column, row_number)
    try:
        return _DECIMAL.validate_python(value)
    except ValidationError as error:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.INVALID_ROW,
            "dataset price or volume must be a valid decimal number",
            row_number=row_number,
            column=source_column,
        ) from error


def _parse_bool(value: object, source_column: str, row_number: int) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
    raise DatasetFileImportError(
        DatasetFileImportErrorCode.INVALID_ROW,
        "closed-state value must be true, false, 1, or 0",
        row_number=row_number,
        column=source_column,
    )


def _build_candles(
    parsed: _ParsedFile,
    request: DatasetFilePreviewRequest,
) -> tuple[OHLCVCandle, ...]:
    available = set(parsed.inspection.columns)
    selected = request.column_mapping.source_columns()
    missing_columns = [column for column in selected if column not in available]
    if missing_columns:
        raise DatasetFileImportError(
            DatasetFileImportErrorCode.INVALID_MAPPING,
            f'mapped source column "{missing_columns[0]}" does not exist in the file',
            column=missing_columns[0],
        )

    received_at = datetime.now(UTC)
    mapping = request.column_mapping
    candles: list[OHLCVCandle] = []
    for row_number, row in enumerate(parsed.rows, start=1):
        try:
            open_time_value = _require_value(row, mapping.open_time, row_number)
            open_time = _AWARE_DATETIME.validate_python(open_time_value).astimezone(UTC)
            close_time = open_time + _TIMEFRAME_INTERVALS[request.timeframe]
            if mapping.close_time is not None:
                close_time_value = _require_value(row, mapping.close_time, row_number)
                close_time = _AWARE_DATETIME.validate_python(close_time_value).astimezone(UTC)
                if close_time != open_time + _TIMEFRAME_INTERVALS[request.timeframe]:
                    raise DatasetFileImportError(
                        DatasetFileImportErrorCode.INVALID_ROW,
                        "candle close time does not match the selected timeframe",
                        row_number=row_number,
                        column=mapping.close_time,
                    )

            is_closed = True
            if mapping.is_closed is not None:
                closed_value = _require_value(row, mapping.is_closed, row_number)
                is_closed = _parse_bool(closed_value, mapping.is_closed, row_number)

            candle = OHLCVCandle(
                source=request.source,
                pair=request.pair,
                timeframe=request.timeframe,
                open_time=open_time,
                close_time=close_time,
                received_at=received_at,
                open_price=_require_decimal(row, mapping.open_price, row_number),
                high_price=_require_decimal(row, mapping.high_price, row_number),
                low_price=_require_decimal(row, mapping.low_price, row_number),
                close_price=_require_decimal(row, mapping.close_price, row_number),
                volume=_require_decimal(row, mapping.volume, row_number),
                is_closed=is_closed,
            )
        except DatasetFileImportError:
            raise
        except ValidationError as error:
            mapped_error = _mapping_error(error)
            mapped_error.row_number = row_number
            raise mapped_error from error
        except (TypeError, ValueError) as error:
            raise DatasetFileImportError(
                DatasetFileImportErrorCode.INVALID_ROW,
                "dataset row contains an invalid value",
                row_number=row_number,
            ) from error
        candles.append(candle)
    return tuple(candles)


class DatasetFileImportService:
    """Inspect, preview, and commit uploaded datasets through one canonical path."""

    def __init__(self, quality_checker: MarketDataQualityChecker | None = None) -> None:
        self._quality_checker = quality_checker or MarketDataQualityChecker()

    def inspect(self, *, file_name: str, content: bytes) -> DatasetFileInspection:
        return _parse_file(file_name, content).inspection

    def _check_quality(
        self,
        candles: Sequence[OHLCVCandle],
        *,
        timeframe: Timeframe,
    ) -> DataQualityReport:
        first_open_time = min(candle.open_time for candle in candles)
        last_close_time = max(candle.close_time for candle in candles)
        return self._quality_checker.check(
            candles,
            requested_start_time=first_open_time,
            requested_end_time=last_close_time,
            requested_timeframe=timeframe,
        )

    def preview(
        self,
        *,
        file_name: str,
        content: bytes,
        request: DatasetFilePreviewRequest,
    ) -> DatasetFileImportPreview:
        parsed = _parse_file(file_name, content)
        candles = _build_candles(parsed, request)
        quality_report = self._check_quality(candles, timeframe=request.timeframe)
        first_open_time = min(candle.open_time for candle in candles)
        last_close_time = max(candle.close_time for candle in candles)
        return DatasetFileImportPreview(
            inspection=parsed.inspection,
            column_mapping=request.column_mapping,
            candle_count=len(candles),
            first_open_time=first_open_time,
            last_close_time=last_close_time,
            preview_checksum=calculate_dataset_checksum(candles),
            quality_report=quality_report,
            ready_to_import=quality_report.is_valid,
        )

    def build_dataset(
        self,
        *,
        file_name: str,
        content: bytes,
        request: DatasetFileCommitRequest,
    ) -> DatasetSnapshot:
        preview_request = DatasetFilePreviewRequest.model_validate(
            request.model_dump(exclude={"preview_checksum"})
        )
        parsed = _parse_file(file_name, content)
        candles = _build_candles(parsed, preview_request)
        actual_checksum = calculate_dataset_checksum(candles)
        if actual_checksum != request.preview_checksum:
            raise DatasetFileImportError(
                DatasetFileImportErrorCode.PREVIEW_MISMATCH,
                "file interpretation changed after preview; preview the file again",
            )

        report = self._check_quality(candles, timeframe=request.timeframe)
        if not report.is_valid:
            raise DatasetFileImportError(
                DatasetFileImportErrorCode.QUALITY_REJECTED,
                "dataset failed the strict quality policy",
                quality_report=report,
            )

        return DatasetBuilder(quality_checker=self._quality_checker).build(
            name=request.name,
            candles=candles,
            provenance=DatasetProvenance(
                kind=DatasetProvenanceKind.MANUAL_UPLOAD,
                original_filename=parsed.inspection.file_name,
                original_file_format=parsed.inspection.file_format.value,
                original_file_checksum=parsed.inspection.file_checksum,
                column_mapping=request.column_mapping.model_dump(exclude_none=True),
            ),
        )
