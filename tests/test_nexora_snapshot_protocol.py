from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from trd_bot.integration.nexora.snapshots import (
    SnapshotCursor,
    SnapshotCursorConflictError,
    SnapshotCursorExpiredError,
    SnapshotCursorNotFoundError,
    SnapshotItem,
    SnapshotProtocolError,
    SnapshotRecord,
    SnapshotScan,
    StableSnapshotPager,
)

NOW = datetime(2026, 11, 6, 8, tzinfo=UTC)


class MemoryScanStore:
    def __init__(self) -> None:
        self.scans: dict[str, SnapshotScan] = {}
        self.cursors: dict[str, SnapshotCursor] = {}

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
            f"scan-{len(self.scans) + 1}",
            resource_type,
            boundary_key,
            boundary_at,
            page_limit,
            opened_at,
            expires_at,
        )
        self.scans[scan.scan_id] = scan
        return scan

    def resolve_cursor(self, cursor: str) -> tuple[SnapshotScan, SnapshotCursor] | None:
        state = self.cursors.get(cursor)
        return None if state is None else (self.scans[state.scan_id], state)

    def get_or_create_cursor(
        self, *, scan: SnapshotScan, after_sort_key: str, created_at: datetime
    ) -> SnapshotCursor:
        token = f"cursor:{scan.scan_id}:{after_sort_key}"
        if token not in self.cursors:
            self.cursors[token] = SnapshotCursor(
                token, scan.scan_id, after_sort_key, created_at, scan.expires_at
            )
        return self.cursors[token]


class MemoryResourceReader:
    def __init__(self, records: Sequence[tuple[int, SnapshotRecord]]) -> None:
        self.records = list(records)

    def capture_boundary(self, *, resource_type: str, captured_at: datetime) -> str:
        del resource_type, captured_at
        return str(max((sequence for sequence, _ in self.records), default=0))

    def list_records(
        self, *, resource_type: str, boundary_key: str, after_sort_key: str | None, limit: int
    ) -> Sequence[SnapshotRecord]:
        return [
            record
            for sequence, record in sorted(self.records, key=lambda item: item[1].sort_key)
            if sequence <= int(boundary_key)
            and record.resource_type == resource_type
            and (after_sort_key is None or record.sort_key > after_sort_key)
        ][:limit]


def record(number: int, *, observed_at: datetime = NOW) -> SnapshotRecord:
    return SnapshotRecord(
        "paper_shadow_portfolio",
        f"portfolio-{number}",
        "paper-shadow-portfolio-v1",
        observed_at,
        f"{number:04d}",
        {"portfolio_id": f"portfolio-{number}", "sequence": number},
    )


def build_pager(
    records: Sequence[tuple[int, SnapshotRecord]],
) -> tuple[StableSnapshotPager, MemoryResourceReader]:
    reader = MemoryResourceReader(records)
    return StableSnapshotPager(
        reader=reader, store=MemoryScanStore(), source_version="0.3.0"
    ), reader


def test_stable_scan_excludes_late_publication() -> None:
    pager, reader = build_pager([(1, record(1)), (2, record(2)), (3, record(3))])
    first = pager.page(resource_type="paper_shadow_portfolio", now=NOW, limit=2)
    assert first.next_cursor is not None
    reader.records.append((4, record(4)))
    second = pager.page(
        resource_type="paper_shadow_portfolio",
        now=NOW + timedelta(minutes=1),
        cursor=first.next_cursor,
    )
    assert [item.payload["sequence"] for item in second.items] == [3]
    assert second.has_more is False


def test_cursor_retry_is_idempotent() -> None:
    pager, _ = build_pager([(index, record(index)) for index in range(1, 6)])
    first = pager.page(resource_type="paper_shadow_portfolio", now=NOW, limit=2)
    assert first.next_cursor is not None
    second = pager.page(
        resource_type="paper_shadow_portfolio",
        now=NOW + timedelta(minutes=1),
        cursor=first.next_cursor,
    )
    retried = pager.page(
        resource_type="paper_shadow_portfolio",
        now=NOW + timedelta(minutes=2),
        cursor=first.next_cursor,
    )
    assert retried == second


def test_source_checksum_detects_tampering() -> None:
    item = record(1).to_item(source_version="0.3.0")
    with pytest.raises(ValidationError, match="checksum"):
        SnapshotItem(
            source_reference=item.source_reference,
            payload={"portfolio_id": "portfolio-1", "sequence": 999},
        )


def test_cursor_failures_are_closed() -> None:
    pager, _ = build_pager([(1, record(1)), (2, record(2))])
    with pytest.raises(SnapshotCursorNotFoundError):
        pager.page(resource_type="paper_shadow_portfolio", now=NOW, cursor="missing")
    first = pager.page(resource_type="paper_shadow_portfolio", now=NOW, limit=1)
    assert first.next_cursor is not None
    with pytest.raises(SnapshotCursorConflictError):
        pager.page(resource_type="candidate", now=NOW, cursor=first.next_cursor)
    with pytest.raises(SnapshotCursorConflictError):
        pager.page(
            resource_type="paper_shadow_portfolio", now=NOW, cursor=first.next_cursor, limit=2
        )
    with pytest.raises(SnapshotCursorExpiredError):
        pager.page(
            resource_type="paper_shadow_portfolio",
            now=NOW + timedelta(hours=1),
            cursor=first.next_cursor,
        )


@pytest.mark.parametrize("limit", [0, 501])
def test_page_limit_is_bounded(limit: int) -> None:
    pager, _ = build_pager([])
    with pytest.raises(SnapshotProtocolError):
        pager.page(resource_type="candidate", now=NOW, limit=limit)


def test_reader_cannot_cross_time_boundary() -> None:
    pager, _ = build_pager([(1, record(1, observed_at=NOW + timedelta(seconds=1)))])
    with pytest.raises(SnapshotProtocolError, match="time boundary"):
        pager.page(resource_type="paper_shadow_portfolio", now=NOW)
