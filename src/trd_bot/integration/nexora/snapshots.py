from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

SNAPSHOT_PAGE_SCHEMA_VERSION: Final = "nexora-source-snapshot-page-v1"
SOURCE_REFERENCE_SCHEMA_VERSION: Final = "nexora-source-reference-v1"
SNAPSHOT_SCAN_SCHEMA_VERSION: Final = "nexora-snapshot-scan-v1"
DEFAULT_PAGE_LIMIT: Final = 100
MAXIMUM_PAGE_LIMIT: Final = 500
DEFAULT_CURSOR_TTL: Final = timedelta(hours=1)


class SnapshotProtocolError(ValueError):
    """Base error for a malformed or inconsistent snapshot scan."""


class SnapshotCursorNotFoundError(SnapshotProtocolError):
    """Raised when an opaque cursor is unknown."""


class SnapshotCursorExpiredError(SnapshotProtocolError):
    """Raised when a cursor can no longer continue its stable scan."""


class SnapshotCursorConflictError(SnapshotProtocolError):
    """Raised when continuation arguments do not match the cursor state."""


def _require_utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise SnapshotProtocolError(f"{field} must be timezone-aware UTC")
    return value


def _json_ready(value: JsonValue) -> JsonValue:
    return value


def canonical_snapshot_json(value: JsonValue) -> str:
    """Serialize snapshot evidence deterministically for SHA-256 checksums."""

    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def snapshot_checksum(value: JsonValue) -> str:
    encoded = canonical_snapshot_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class SnapshotContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceReference(SnapshotContractModel):
    schema_version: Literal["nexora-source-reference-v1"]
    source_product: Literal["trd_bot"]
    source_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=160)
    resource_schema_version: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_utc_timestamp(self) -> SourceReference:
        _require_utc(self.observed_at, field="observed_at")
        return self


class SnapshotItem(SnapshotContractModel):
    source_reference: SourceReference
    payload: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_checksum(self) -> SnapshotItem:
        expected = build_source_checksum(
            resource_type=self.source_reference.resource_type,
            resource_id=self.source_reference.resource_id,
            resource_schema_version=self.source_reference.resource_schema_version,
            observed_at=self.source_reference.observed_at,
            payload=self.payload,
        )
        if self.source_reference.checksum != expected:
            raise ValueError("source reference checksum does not match the snapshot item")
        return self


class SnapshotPage(SnapshotContractModel):
    schema_version: Literal["nexora-source-snapshot-page-v1"]
    items: tuple[SnapshotItem, ...]
    next_cursor: str | None
    has_more: bool

    @model_validator(mode="after")
    def validate_continuation(self) -> SnapshotPage:
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("next_cursor must be present exactly when has_more is true")
        return self


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    resource_type: str
    resource_id: str
    resource_schema_version: str
    observed_at: datetime
    sort_key: str
    payload: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        if not self.resource_type or len(self.resource_type) > 80:
            raise SnapshotProtocolError("resource_type must contain at most 80 characters")
        if not self.resource_id or len(self.resource_id) > 160:
            raise SnapshotProtocolError("resource_id must contain at most 160 characters")
        if not self.resource_schema_version or len(self.resource_schema_version) > 120:
            raise SnapshotProtocolError(
                "resource_schema_version must contain at most 120 characters"
            )
        if not self.sort_key or len(self.sort_key) > 512:
            raise SnapshotProtocolError("sort_key must contain at most 512 characters")
        _require_utc(self.observed_at, field="observed_at")

    def to_item(self, *, source_version: str) -> SnapshotItem:
        payload = dict(self.payload)
        return SnapshotItem(
            source_reference=SourceReference(
                schema_version=SOURCE_REFERENCE_SCHEMA_VERSION,
                source_product="trd_bot",
                source_version=source_version,
                resource_type=self.resource_type,
                resource_id=self.resource_id,
                resource_schema_version=self.resource_schema_version,
                observed_at=self.observed_at,
                checksum=build_source_checksum(
                    resource_type=self.resource_type,
                    resource_id=self.resource_id,
                    resource_schema_version=self.resource_schema_version,
                    observed_at=self.observed_at,
                    payload=payload,
                ),
            ),
            payload=payload,
        )


@dataclass(frozen=True, slots=True)
class SnapshotScan:
    scan_id: str
    resource_type: str
    boundary_key: str
    boundary_at: datetime
    page_limit: int
    opened_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class SnapshotCursor:
    cursor: str
    scan_id: str
    after_sort_key: str
    created_at: datetime
    expires_at: datetime


class SnapshotResourceReader(Protocol):
    def capture_boundary(self, *, resource_type: str, captured_at: datetime) -> str: ...

    def list_records(
        self,
        *,
        resource_type: str,
        boundary_key: str,
        after_sort_key: str | None,
        limit: int,
    ) -> Sequence[SnapshotRecord]: ...


class SnapshotScanStore(Protocol):
    def create_scan(
        self,
        *,
        resource_type: str,
        boundary_key: str,
        boundary_at: datetime,
        page_limit: int,
        opened_at: datetime,
        expires_at: datetime,
    ) -> SnapshotScan: ...

    def resolve_cursor(self, cursor: str) -> tuple[SnapshotScan, SnapshotCursor] | None: ...

    def get_or_create_cursor(
        self,
        *,
        scan: SnapshotScan,
        after_sort_key: str,
        created_at: datetime,
    ) -> SnapshotCursor: ...


def build_source_checksum(
    *,
    resource_type: str,
    resource_id: str,
    resource_schema_version: str,
    observed_at: datetime,
    payload: Mapping[str, JsonValue],
) -> str:
    _require_utc(observed_at, field="observed_at")
    evidence: dict[str, JsonValue] = {
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "payload": dict(payload),
        "resource_id": resource_id,
        "resource_schema_version": resource_schema_version,
        "resource_type": resource_type,
    }
    return snapshot_checksum(evidence)


class StableSnapshotPager:
    """Page immutable resources behind one durable, high-watermark scan boundary."""

    def __init__(
        self,
        *,
        reader: SnapshotResourceReader,
        store: SnapshotScanStore,
        source_version: str,
        cursor_ttl: timedelta = DEFAULT_CURSOR_TTL,
    ) -> None:
        if cursor_ttl <= timedelta(0):
            raise ValueError("cursor_ttl must be positive")
        self._reader = reader
        self._store = store
        self._source_version = source_version
        self._cursor_ttl = cursor_ttl

    def page(
        self,
        *,
        resource_type: str,
        now: datetime,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> SnapshotPage:
        _require_utc(now, field="now")
        if cursor is None:
            page_limit = DEFAULT_PAGE_LIMIT if limit is None else limit
            self._validate_limit(page_limit)
            boundary_key = self._reader.capture_boundary(
                resource_type=resource_type,
                captured_at=now,
            )
            if not boundary_key or len(boundary_key) > 512:
                raise SnapshotProtocolError("snapshot boundary key is invalid")
            scan = self._store.create_scan(
                resource_type=resource_type,
                boundary_key=boundary_key,
                boundary_at=now,
                page_limit=page_limit,
                opened_at=now,
                expires_at=now + self._cursor_ttl,
            )
            after_sort_key = None
        else:
            resolved = self._store.resolve_cursor(cursor)
            if resolved is None:
                raise SnapshotCursorNotFoundError("snapshot cursor is unknown")
            scan, cursor_state = resolved
            if now >= scan.expires_at or now >= cursor_state.expires_at:
                raise SnapshotCursorExpiredError("snapshot cursor expired; full resync is required")
            if scan.resource_type != resource_type:
                raise SnapshotCursorConflictError("snapshot cursor resource type does not match")
            if limit is not None and limit != scan.page_limit:
                raise SnapshotCursorConflictError("snapshot cursor page limit cannot change")
            page_limit = scan.page_limit
            after_sort_key = cursor_state.after_sort_key

        records = tuple(
            self._reader.list_records(
                resource_type=resource_type,
                boundary_key=scan.boundary_key,
                after_sort_key=after_sort_key,
                limit=page_limit + 1,
            )
        )
        if len(records) > page_limit + 1:
            raise SnapshotProtocolError("snapshot reader returned more rows than requested")
        self._validate_records(
            records,
            resource_type=resource_type,
            after_sort_key=after_sort_key,
            boundary_at=scan.boundary_at,
        )

        selected = records[:page_limit]
        has_more = len(records) > page_limit
        next_cursor: str | None = None
        if has_more:
            if not selected:
                raise SnapshotProtocolError("snapshot reader cannot advance the cursor")
            next_cursor = self._store.get_or_create_cursor(
                scan=scan,
                after_sort_key=selected[-1].sort_key,
                created_at=now,
            ).cursor

        return SnapshotPage(
            schema_version=SNAPSHOT_PAGE_SCHEMA_VERSION,
            items=tuple(record.to_item(source_version=self._source_version) for record in selected),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit < 1 or limit > MAXIMUM_PAGE_LIMIT:
            raise SnapshotProtocolError(
                f"snapshot page limit must be between 1 and {MAXIMUM_PAGE_LIMIT}"
            )

    @staticmethod
    def _validate_records(
        records: Sequence[SnapshotRecord],
        *,
        resource_type: str,
        after_sort_key: str | None,
        boundary_at: datetime,
    ) -> None:
        previous = after_sort_key
        for record in records:
            if record.resource_type != resource_type:
                raise SnapshotProtocolError("snapshot reader crossed a resource boundary")
            if record.observed_at > boundary_at:
                raise SnapshotProtocolError("snapshot reader crossed the scan time boundary")
            if previous is not None and record.sort_key <= previous:
                raise SnapshotProtocolError("snapshot reader order is not strictly deterministic")
            previous = record.sort_key


def normalize_database_timestamp(value: datetime) -> datetime:
    """Restore UTC tzinfo when SQLite returns a timezone-naive DateTime value."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
