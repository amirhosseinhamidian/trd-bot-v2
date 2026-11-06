from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from trd_bot.db.models import NexoraSnapshotCursorRow, NexoraSnapshotScanRow
from trd_bot.integration.nexora.snapshots import (
    SNAPSHOT_SCAN_SCHEMA_VERSION,
    SnapshotCursor,
    SnapshotProtocolError,
    SnapshotScan,
    normalize_database_timestamp,
)


def _cursor_token(*, scan_id: str, after_sort_key: str) -> str:
    identity = f"{scan_id}\x00{after_sort_key}".encode()
    return f"snp_{hashlib.sha256(identity).hexdigest()}"


def _scan_from_row(row: NexoraSnapshotScanRow) -> SnapshotScan:
    return SnapshotScan(
        scan_id=row.scan_id,
        resource_type=row.resource_type,
        boundary_key=row.boundary_key,
        boundary_at=normalize_database_timestamp(row.boundary_at),
        page_limit=row.page_limit,
        opened_at=normalize_database_timestamp(row.opened_at),
        expires_at=normalize_database_timestamp(row.expires_at),
    )


def _cursor_from_row(row: NexoraSnapshotCursorRow) -> SnapshotCursor:
    return SnapshotCursor(
        cursor=row.cursor,
        scan_id=row.scan_id,
        after_sort_key=row.after_sort_key,
        created_at=normalize_database_timestamp(row.created_at),
        expires_at=normalize_database_timestamp(row.expires_at),
    )


class SqlAlchemyNexoraSnapshotScanStore:
    """Persist stable scan boundaries and opaque continuation positions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_scan(
        self,
        *,
        resource_type: str,
        boundary_key: str,
        boundary_at: datetime,
        page_limit: int,
        opened_at: datetime,
        expires_at: datetime,
    ) -> SnapshotScan:
        scan = SnapshotScan(
            scan_id=f"nexora-scan-{uuid4().hex}",
            resource_type=resource_type,
            boundary_key=boundary_key,
            boundary_at=boundary_at,
            page_limit=page_limit,
            opened_at=opened_at,
            expires_at=expires_at,
        )
        self._session.add(
            NexoraSnapshotScanRow(
                scan_id=scan.scan_id,
                schema_version=SNAPSHOT_SCAN_SCHEMA_VERSION,
                resource_type=scan.resource_type,
                boundary_key=scan.boundary_key,
                boundary_at=scan.boundary_at,
                page_limit=scan.page_limit,
                opened_at=scan.opened_at,
                expires_at=scan.expires_at,
            )
        )
        self._session.flush()
        return scan

    def resolve_cursor(self, cursor: str) -> tuple[SnapshotScan, SnapshotCursor] | None:
        cursor_row = self._session.get(NexoraSnapshotCursorRow, cursor)
        if cursor_row is None:
            return None
        scan_row = self._session.get(NexoraSnapshotScanRow, cursor_row.scan_id)
        if scan_row is None:
            raise SnapshotProtocolError("snapshot cursor has no scan boundary")
        return _scan_from_row(scan_row), _cursor_from_row(cursor_row)

    def get_or_create_cursor(
        self, *, scan: SnapshotScan, after_sort_key: str, created_at: datetime
    ) -> SnapshotCursor:
        existing = self._session.scalar(
            select(NexoraSnapshotCursorRow).where(
                NexoraSnapshotCursorRow.scan_id == scan.scan_id,
                NexoraSnapshotCursorRow.after_sort_key == after_sort_key,
            )
        )
        if existing is not None:
            return _cursor_from_row(existing)
        cursor = SnapshotCursor(
            cursor=_cursor_token(scan_id=scan.scan_id, after_sort_key=after_sort_key),
            scan_id=scan.scan_id,
            after_sort_key=after_sort_key,
            created_at=created_at,
            expires_at=scan.expires_at,
        )
        self._session.add(
            NexoraSnapshotCursorRow(
                cursor=cursor.cursor,
                scan_id=cursor.scan_id,
                after_sort_key=cursor.after_sort_key,
                created_at=cursor.created_at,
                expires_at=cursor.expires_at,
            )
        )
        self._session.flush()
        return cursor
