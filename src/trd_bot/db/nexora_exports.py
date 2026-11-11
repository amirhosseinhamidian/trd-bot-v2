from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import JsonValue
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.models import NexoraExportArtifactRow, NexoraExportJobRow
from trd_bot.integration.nexora.alert_snapshots import (
    ALERT_SNAPSHOT_RESOURCE_TYPES,
    AlertSnapshotResourceReader,
)
from trd_bot.integration.nexora.decision_snapshots import (
    DECISION_SNAPSHOT_RESOURCE_TYPES,
    DecisionSnapshotResourceReader,
)
from trd_bot.integration.nexora.exports import (
    CurrencyUnitContext,
    ExportFile,
    ExportIdempotencyConflictError,
    ExportManifest,
    ExportNotCompleteError,
    ExportNotFoundError,
    ExportRequest,
    ExportStatus,
    NexoraExportJobPayload,
    export_id_for,
)
from trd_bot.integration.nexora.portfolio_snapshots import (
    PORTFOLIO_SNAPSHOT_RESOURCE_TYPES,
    PortfolioSnapshotResourceReader,
)
from trd_bot.integration.nexora.snapshots import SnapshotItem, SnapshotResourceReader
from trd_bot.jobs import BackgroundJobBuilder, BackgroundJobKind

_PAGE_LIMIT = 500
_AI_SENSITIVE_KEYS = frozenset(
    {
        "account_id",
        "account_key",
        "external_reference",
        "institution_name",
        "owner_id",
        "owner_key",
        "provider_account_id",
    }
)
_ALWAYS_SECRET_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "api_key",
    "cookie",
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _redact(value: JsonValue, *, ai_safe: bool) -> JsonValue:
    if isinstance(value, dict):
        redacted: dict[str, JsonValue] = {}
        for key, item in value.items():
            normalized = key.casefold()
            if any(fragment in normalized for fragment in _ALWAYS_SECRET_FRAGMENTS) or (
                ai_safe and normalized in _AI_SENSITIVE_KEYS
            ):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item, ai_safe=ai_safe)
        return redacted
    if isinstance(value, list):
        return [_redact(item, ai_safe=ai_safe) for item in value]
    return value


def _matches_filters(item: SnapshotItem, filters: Mapping[str, JsonValue]) -> bool:
    observed_at = item.source_reference.observed_at
    from_value = filters.get("from")
    through_value = filters.get("through")
    if isinstance(from_value, str) and observed_at < datetime.fromisoformat(
        from_value.replace("Z", "+00:00")
    ):
        return False
    if isinstance(through_value, str) and observed_at > datetime.fromisoformat(
        through_value.replace("Z", "+00:00")
    ):
        return False
    resource_ids = filters.get("resource_ids")
    if isinstance(resource_ids, list) and item.source_reference.resource_id not in resource_ids:
        return False
    portfolio_mode = filters.get("portfolio_mode")
    return not (
        isinstance(portfolio_mode, str) and item.payload.get("portfolio_mode") != portfolio_mode
    )


def _reader(session: Session, resource_type: str) -> SnapshotResourceReader:
    if resource_type in DECISION_SNAPSHOT_RESOURCE_TYPES:
        return DecisionSnapshotResourceReader(session)
    if resource_type in PORTFOLIO_SNAPSHOT_RESOURCE_TYPES:
        return PortfolioSnapshotResourceReader(session)
    if resource_type in ALERT_SNAPSHOT_RESOURCE_TYPES:
        return AlertSnapshotResourceReader(session)
    raise ValueError(f'unsupported export resource type "{resource_type}"')


def _collect_items(
    session: Session,
    request: ExportRequest,
    *,
    generated_at: datetime,
    provider_version: str,
) -> tuple[SnapshotItem, ...]:
    items: list[SnapshotItem] = []
    for resource in request.scope:
        resource_type = resource.value
        reader = _reader(session, resource_type)
        boundary = reader.capture_boundary(resource_type=resource_type, captured_at=generated_at)
        after: str | None = None
        while True:
            records = tuple(
                reader.list_records(
                    resource_type=resource_type,
                    boundary_key=boundary,
                    after_sort_key=after,
                    limit=_PAGE_LIMIT,
                )
            )
            for record in records:
                item = record.to_item(source_version=provider_version)
                if _matches_filters(item, request.filters):
                    items.append(item)
            if len(records) < _PAGE_LIMIT:
                break
            after = records[-1].sort_key
    return tuple(items)


def _flat_rows(items: Sequence[dict[str, JsonValue]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in items:
        reference = cast(dict[str, JsonValue], item["source_reference"])
        rows.append(
            {
                "resource_type": reference["resource_type"],
                "resource_id": reference["resource_id"],
                "resource_schema_version": reference["resource_schema_version"],
                "observed_at": reference["observed_at"],
                "checksum": reference["checksum"],
                "payload_json": _canonical_json(item["payload"]).decode("utf-8"),
            }
        )
    return rows


def render_export_artifacts(
    request: ExportRequest,
    items: Sequence[SnapshotItem],
) -> tuple[tuple[str, str, str, bytes, int], ...]:
    prepared = [
        cast(
            dict[str, JsonValue],
            _redact(item.model_dump(mode="json"), ai_safe=request.profile == "ai_safe"),
        )
        for item in items
    ]
    rows = _flat_rows(prepared)
    artifacts: list[tuple[str, str, str, bytes, int]] = []
    for output_format in request.formats:
        if output_format == "json":
            content = _canonical_json(prepared)
            artifacts.append(
                (
                    "data/export.json",
                    "application/json",
                    "nexora-export-data-v1",
                    content,
                    len(items),
                )
            )
        elif output_format == "jsonl":
            content = b"".join(_canonical_json(item) + b"\n" for item in prepared)
            artifacts.append(
                (
                    "data/export.jsonl",
                    "application/x-ndjson",
                    "nexora-export-data-v1",
                    content,
                    len(items),
                )
            )
        elif output_format == "csv":
            csv_stream = io.StringIO(newline="")
            fieldnames = (
                "resource_type",
                "resource_id",
                "resource_schema_version",
                "observed_at",
                "checksum",
                "payload_json",
            )
            writer = csv.DictWriter(csv_stream, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            artifacts.append(
                (
                    "data/export.csv",
                    "text/csv",
                    "nexora-export-tabular-v1",
                    csv_stream.getvalue().encode("utf-8"),
                    len(items),
                )
            )
        elif output_format == "parquet":
            table = pa.Table.from_pylist(rows)
            parquet_stream = io.BytesIO()
            pq.write_table(table, parquet_stream, compression="zstd")
            artifacts.append(
                (
                    "data/export.parquet",
                    "application/vnd.apache.parquet",
                    "nexora-export-tabular-v1",
                    parquet_stream.getvalue(),
                    len(items),
                )
            )
        else:
            zip_stream = io.BytesIO()
            with zipfile.ZipFile(zip_stream, "w", compression=zipfile.ZIP_STORED) as archive:
                for resource in request.scope:
                    resource_items = [
                        item
                        for item in prepared
                        if cast(dict[str, JsonValue], item["source_reference"])["resource_type"]
                        == resource.value
                    ]
                    info = zipfile.ZipInfo(f"data/{resource.value}.jsonl")
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.external_attr = 0o600 << 16
                    archive.writestr(
                        info,
                        b"".join(_canonical_json(item) + b"\n" for item in resource_items),
                    )
            artifacts.append(
                (
                    "data/export.zip",
                    "application/zip",
                    "nexora-export-bundle-v1",
                    zip_stream.getvalue(),
                    len(items),
                )
            )
    return tuple(artifacts)


class SqlAlchemyNexoraExportStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def submit(
        self,
        *,
        request: ExportRequest,
        idempotency_key: str,
        provider_version: str,
        requested_at: datetime,
    ) -> ExportStatus:
        existing = self._session.scalar(
            select(NexoraExportJobRow).where(NexoraExportJobRow.idempotency_key == idempotency_key)
        )
        checksum = request.checksum()
        if existing is not None:
            if existing.request_checksum != checksum:
                raise ExportIdempotencyConflictError("idempotency key belongs to another export")
            return self._status(existing)

        export_id = export_id_for(idempotency_key)
        payload = NexoraExportJobPayload(export_id=export_id, provider_version=provider_version)
        job = BackgroundJobBuilder().build(
            kind=BackgroundJobKind.NEXORA_EXPORT,
            payload=payload.model_dump(mode="json"),
            idempotency_key=f"nexora-export:{idempotency_key}",
            now=requested_at,
        )
        row = NexoraExportJobRow(
            export_id=export_id,
            idempotency_key=idempotency_key,
            background_job_id=job.job_id,
            request_checksum=checksum,
            request_schema_version=request.schema_version,
            mode=request.mode,
            profile=request.profile,
            provider_version=provider_version,
            request_json=request.canonical_json(),
            status="accepted",
            requested_at=requested_at,
            completed_at=None,
            manifest_json=None,
            error_code=None,
            contains_secrets=False,
        )
        try:
            with self._session.begin_nested():
                SqlAlchemyBackgroundJobRepository(self._session).stage(job)
                self._session.add(row)
                self._session.flush()
        except IntegrityError as error:
            concurrent = self._session.scalar(
                select(NexoraExportJobRow).where(
                    NexoraExportJobRow.idempotency_key == idempotency_key
                )
            )
            if concurrent is None:
                raise
            if concurrent.request_checksum != checksum:
                raise ExportIdempotencyConflictError(
                    "idempotency key belongs to another export"
                ) from error
            return self._status(concurrent)
        return self._status(row)

    def get_status(self, export_id: str) -> ExportStatus:
        row = self._get(export_id)
        return self._status(row)

    def get_manifest(self, export_id: str) -> ExportManifest:
        row = self._get(export_id)
        if row.status != "complete" or row.manifest_json is None:
            raise ExportNotCompleteError("export manifest is not complete")
        return ExportManifest.model_validate_json(row.manifest_json)

    def run(self, export_id: str, *, generated_at: datetime) -> ExportManifest:
        row = self._get(export_id, lock=True)
        if row.status == "complete" and row.manifest_json is not None:
            return ExportManifest.model_validate_json(row.manifest_json)
        row.status = "running"
        row.completed_at = None
        row.manifest_json = None
        row.error_code = None
        self._session.flush()

        request = ExportRequest.model_validate_json(row.request_json)
        items = _collect_items(
            self._session,
            request,
            generated_at=generated_at,
            provider_version=row.provider_version,
        )
        rendered = render_export_artifacts(request, items)
        self._session.execute(
            delete(NexoraExportArtifactRow).where(NexoraExportArtifactRow.export_id == export_id)
        )
        files: list[ExportFile] = []
        for path, media_type, schema_version, content, row_count in rendered:
            digest = hashlib.sha256(content).hexdigest()
            self._session.add(
                NexoraExportArtifactRow(
                    export_id=export_id,
                    path=path,
                    media_type=media_type,
                    row_count=row_count,
                    size_bytes=len(content),
                    sha256=digest,
                    schema_version=schema_version,
                    content=content,
                    created_at=generated_at,
                )
            )
            files.append(
                ExportFile(
                    path=path,
                    media_type=media_type,
                    row_count=row_count,
                    size_bytes=len(content),
                    sha256=digest,
                    schema_version=schema_version,
                )
            )
        manifest = ExportManifest(
            export_id=export_id,
            generated_at=generated_at,
            mode=request.mode,
            profile=request.profile,
            source_versions={
                "trd_bot": row.provider_version,
                "integration_contract": "1.0.0",
            },
            scope=tuple(resource.value for resource in request.scope),
            filters=request.filters,
            currency_unit_context=CurrencyUnitContext(
                base_currency=cast(str, request.filters.get("base_currency", "USDT"))
            ),
            lineage_references=tuple(item.source_reference for item in items),
            files=tuple(files),
            redaction_profile="ai-safe-v1" if request.profile == "ai_safe" else "private-v1",
        )
        row.status = "complete"
        row.completed_at = generated_at
        row.manifest_json = manifest.model_dump_json()
        self._session.flush()
        return manifest

    def mark_running(self, export_id: str) -> None:
        row = self._get(export_id, lock=True)
        if row.status != "complete":
            row.status = "running"
            row.completed_at = None
            row.manifest_json = None
            row.error_code = None

    def mark_failed(self, export_id: str, *, error_code: str, failed_at: datetime) -> None:
        row = self._get(export_id, lock=True)
        row.status = "failed"
        row.completed_at = failed_at
        row.manifest_json = None
        row.error_code = error_code
        self._session.execute(
            delete(NexoraExportArtifactRow).where(NexoraExportArtifactRow.export_id == export_id)
        )

    def reset_accepted(self, export_id: str) -> None:
        row = self._get(export_id, lock=True)
        row.status = "accepted"
        row.completed_at = None
        row.manifest_json = None
        row.error_code = None

    def list_artifacts(self, export_id: str) -> tuple[NexoraExportArtifactRow, ...]:
        self._get(export_id)
        return tuple(
            self._session.scalars(
                select(NexoraExportArtifactRow)
                .where(NexoraExportArtifactRow.export_id == export_id)
                .order_by(NexoraExportArtifactRow.path)
            ).all()
        )

    def _get(self, export_id: str, *, lock: bool = False) -> NexoraExportJobRow:
        statement = select(NexoraExportJobRow).where(NexoraExportJobRow.export_id == export_id)
        if lock:
            statement = statement.with_for_update()
        row = self._session.scalar(statement)
        if row is None:
            raise ExportNotFoundError("export was not found")
        return row

    @staticmethod
    def _status(row: NexoraExportJobRow) -> ExportStatus:
        requested_at = row.requested_at
        completed_at = row.completed_at
        if requested_at.tzinfo is None:
            requested_at = requested_at.replace(tzinfo=UTC)
        if completed_at is not None and completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=UTC)
        return ExportStatus(
            export_id=row.export_id,
            status=cast(Any, row.status),
            requested_at=requested_at,
            completed_at=completed_at,
        )
