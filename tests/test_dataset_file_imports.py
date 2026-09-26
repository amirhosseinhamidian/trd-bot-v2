import json
from datetime import UTC, datetime
from io import BytesIO

import pyarrow as arrow  # type: ignore[import-untyped]
import pyarrow.parquet as parquet  # type: ignore[import-untyped]
import pytest

from trd_bot.research import (
    DatasetColumnMapping,
    DatasetFileCommitRequest,
    DatasetFileField,
    DatasetFileImportError,
    DatasetFileImportErrorCode,
    DatasetFileImportService,
    DatasetFilePreviewRequest,
)

ROWS = [
    {
        "timestamp": "2026-08-20T10:00:00+00:00",
        "end": "2026-08-20T11:00:00+00:00",
        "open": "100",
        "high": "102",
        "low": "99",
        "close": "101",
        "vol": "1500",
        "closed": True,
    },
    {
        "timestamp": "2026-08-20T11:00:00+00:00",
        "end": "2026-08-20T12:00:00+00:00",
        "open": "101",
        "high": "103",
        "low": "100",
        "close": "102",
        "vol": "1600",
        "closed": True,
    },
]


def request() -> DatasetFilePreviewRequest:
    return DatasetFilePreviewRequest.model_validate(
        {
            "name": "BTC file import",
            "source": "manual-file",
            "pair": {"base_asset": "BTC", "quote_asset": "USDT"},
            "timeframe": "1h",
            "column_mapping": {
                "open_time": "timestamp",
                "close_time": "end",
                "open_price": "open",
                "high_price": "high",
                "low_price": "low",
                "close_price": "close",
                "volume": "vol",
                "is_closed": "closed",
            },
        }
    )


def csv_content(rows: list[dict[str, object]] = ROWS) -> bytes:
    header = "timestamp,end,open,high,low,close,vol,closed"
    data = [
        ",".join(
            str(row[column]).lower() if isinstance(row[column], bool) else str(row[column])
            for column in ("timestamp", "end", "open", "high", "low", "close", "vol", "closed")
        )
        for row in rows
    ]
    return "\n".join([header, *data]).encode()


def parquet_content(rows: list[dict[str, object]] = ROWS) -> bytes:
    table = arrow.Table.from_pylist(rows)
    output = BytesIO()
    parquet.write_table(table, output)
    return output.getvalue()


@pytest.mark.parametrize(
    ("file_name", "content"),
    [
        ("candles.csv", csv_content()),
        ("candles.json", json.dumps(ROWS).encode()),
        ("candles.parquet", parquet_content()),
    ],
)
def test_supported_files_produce_identical_canonical_preview(
    file_name: str,
    content: bytes,
) -> None:
    preview = DatasetFileImportService().preview(
        file_name=file_name,
        content=content,
        request=request(),
    )

    assert preview.candle_count == 2
    assert preview.first_open_time == datetime(2026, 8, 20, 10, tzinfo=UTC)
    assert preview.last_close_time == datetime(2026, 8, 20, 12, tzinfo=UTC)
    assert preview.ready_to_import is True
    assert preview.quality_report.issues == ()
    assert preview.quality_report.coverage is not None
    assert preview.quality_report.coverage.complete is True
    assert preview.quality_report.score is not None
    assert preview.quality_report.score.score_percent == 100.0
    assert len(preview.preview_checksum) == 64


def test_supported_formats_have_the_same_checksum_and_quality_report() -> None:
    files = (
        ("candles.csv", csv_content()),
        ("candles.json", json.dumps(ROWS).encode()),
        ("candles.parquet", parquet_content()),
    )
    previews = [
        DatasetFileImportService().preview(file_name=name, content=content, request=request())
        for name, content in files
    ]

    assert len({preview.preview_checksum for preview in previews}) == 1
    assert len({preview.quality_report.model_dump_json() for preview in previews}) == 1


def test_inspection_suggests_aliases_and_reports_missing_required_fields() -> None:
    inspection = DatasetFileImportService().inspect(
        file_name="candles.json",
        content=json.dumps(ROWS).encode(),
    )

    assert inspection.row_count == 2
    assert inspection.suggested_mapping[DatasetFileField.OPEN_TIME] == "timestamp"
    assert inspection.suggested_mapping[DatasetFileField.OPEN_PRICE] == "open"
    assert inspection.suggested_mapping[DatasetFileField.VOLUME] == "vol"
    assert inspection.missing_required_fields == ()
    assert inspection.can_preview is True


def test_preview_can_derive_close_time_and_default_closed_state() -> None:
    reduced_rows = [
        {key: value for key, value in row.items() if key not in {"end", "closed"}} for row in ROWS
    ]
    reduced_request = request().model_copy(
        update={
            "column_mapping": DatasetColumnMapping(
                open_time="timestamp",
                open_price="open",
                high_price="high",
                low_price="low",
                close_price="close",
                volume="vol",
            )
        }
    )

    preview = DatasetFileImportService().preview(
        file_name="candles.json",
        content=json.dumps(reduced_rows).encode(),
        request=reduced_request,
    )

    assert preview.last_close_time == datetime(2026, 8, 20, 12, tzinfo=UTC)
    assert preview.ready_to_import is True


def test_preview_rejects_a_mapping_to_an_unknown_column() -> None:
    invalid_request = request().model_copy(
        update={
            "column_mapping": request().column_mapping.model_copy(
                update={"volume": "missing-volume"}
            )
        }
    )

    with pytest.raises(DatasetFileImportError) as error:
        DatasetFileImportService().preview(
            file_name="candles.csv",
            content=csv_content(),
            request=invalid_request,
        )

    assert error.value.code is DatasetFileImportErrorCode.INVALID_MAPPING
    assert error.value.column == "missing-volume"


def test_preview_rejects_close_time_that_does_not_match_timeframe() -> None:
    rows = [{**ROWS[0], "end": "2026-08-20T11:30:00+00:00"}, ROWS[1]]

    with pytest.raises(DatasetFileImportError) as error:
        DatasetFileImportService().preview(
            file_name="candles.json",
            content=json.dumps(rows).encode(),
            request=request(),
        )

    assert error.value.code is DatasetFileImportErrorCode.INVALID_ROW
    assert error.value.row_number == 1
    assert error.value.column == "end"


def test_preview_quality_rejects_candles_off_the_utc_timeframe_grid() -> None:
    rows = [
        {
            **row,
            "timestamp": datetime.fromisoformat(str(row["timestamp"]))
            .replace(minute=5)
            .isoformat(),
            "end": datetime.fromisoformat(str(row["end"])).replace(minute=5).isoformat(),
        }
        for row in ROWS
    ]

    preview = DatasetFileImportService().preview(
        file_name="candles.json",
        content=json.dumps(rows).encode(),
        request=request(),
    )

    assert preview.ready_to_import is False
    assert preview.quality_report.coverage is not None
    assert {issue.code.value for issue in preview.quality_report.issues} >= {"unaligned_candle"}


def test_preview_reports_out_of_order_rows_without_failing_range_validation() -> None:
    preview = DatasetFileImportService().preview(
        file_name="candles.json",
        content=json.dumps(list(reversed(ROWS))).encode(),
        request=request(),
    )

    assert preview.first_open_time == datetime(2026, 8, 20, 10, tzinfo=UTC)
    assert preview.last_close_time == datetime(2026, 8, 20, 12, tzinfo=UTC)
    assert preview.ready_to_import is False
    assert {issue.code.value for issue in preview.quality_report.issues} >= {"out_of_order"}


def test_inspection_rejects_an_overlong_sanitized_file_name() -> None:
    with pytest.raises(DatasetFileImportError) as error:
        DatasetFileImportService().inspect(
            file_name=f"{'a' * 256}.csv",
            content=csv_content(),
        )

    assert error.value.code is DatasetFileImportErrorCode.INVALID_FILE_NAME


def test_preview_rejects_corrupt_parquet_before_decoding() -> None:
    with pytest.raises(DatasetFileImportError) as error:
        DatasetFileImportService().inspect(
            file_name="candles.parquet",
            content=b"not parquet",
        )

    assert error.value.code is DatasetFileImportErrorCode.MALFORMED_FILE


def test_commit_is_bound_to_preview_checksum_and_records_file_provenance() -> None:
    service = DatasetFileImportService()
    content = csv_content()
    preview = service.preview(file_name="folder/candles.csv", content=content, request=request())
    commit_request = DatasetFileCommitRequest.model_validate(
        {
            **request().model_dump(),
            "preview_checksum": preview.preview_checksum,
        }
    )

    dataset = service.build_dataset(
        file_name="folder/candles.csv",
        content=content,
        request=commit_request,
    )

    assert dataset.checksum == preview.preview_checksum
    assert dataset.provenance.original_filename == "candles.csv"
    assert dataset.provenance.original_file_format == "csv"
    assert dataset.provenance.original_file_checksum is not None
    assert dataset.provenance.column_mapping == request().column_mapping.model_dump(
        exclude_none=True
    )

    changed_request = commit_request.model_copy(update={"preview_checksum": "0" * 64})
    with pytest.raises(DatasetFileImportError) as error:
        service.build_dataset(
            file_name="candles.csv",
            content=content,
            request=changed_request,
        )
    assert error.value.code is DatasetFileImportErrorCode.PREVIEW_MISMATCH


def test_quality_rejection_is_visible_in_preview_and_blocks_commit() -> None:
    rows = [
        ROWS[0],
        {
            **ROWS[1],
            "timestamp": "2026-08-20T12:00:00+00:00",
            "end": "2026-08-20T13:00:00+00:00",
        },
    ]
    content = json.dumps(rows).encode()
    service = DatasetFileImportService()
    preview = service.preview(file_name="candles.json", content=content, request=request())

    assert preview.ready_to_import is False
    assert {issue.code.value for issue in preview.quality_report.issues} == {"missing_candle"}

    commit_request = DatasetFileCommitRequest.model_validate(
        {**request().model_dump(), "preview_checksum": preview.preview_checksum}
    )
    with pytest.raises(DatasetFileImportError) as error:
        service.build_dataset(
            file_name="candles.json",
            content=content,
            request=commit_request,
        )
    assert error.value.code is DatasetFileImportErrorCode.QUALITY_REJECTED
    assert error.value.quality_report == preview.quality_report
