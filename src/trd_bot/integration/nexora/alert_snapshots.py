from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, TypeVar, cast

from pydantic import JsonValue
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from trd_bot.db.models import AlertOutcomeRow, AlertRow
from trd_bot.integration.nexora.snapshots import (
    SnapshotProtocolError,
    SnapshotRecord,
    normalize_database_timestamp,
)

ALERT: Final = "alert"
ALERT_OUTCOME: Final = "alert_outcome"
ALERT_SNAPSHOT_RESOURCE_TYPES: Final = (ALERT, ALERT_OUTCOME)
RESOURCE_SCHEMA_VERSIONS: Final = {
    ALERT: "trd-bot-alert-v1",
    ALERT_OUTCOME: "trd-bot-alert-outcome-v1",
}
_RowT = TypeVar("_RowT")


def _canonical_timestamp(value: datetime) -> str:
    normalized = normalize_database_timestamp(value)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sort_key(observed_at: datetime, resource_id: str) -> str:
    return f"{_canonical_timestamp(observed_at)}|{resource_id}"


def _parse_boundary(value: str) -> datetime:
    try:
        boundary = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SnapshotProtocolError("alert snapshot boundary is invalid") from error
    normalized = boundary.astimezone(UTC)
    if _canonical_timestamp(normalized) != value:
        raise SnapshotProtocolError("alert snapshot boundary is not canonical")
    return normalized


def _parse_after_sort_key(value: str) -> tuple[datetime, str]:
    timestamp, separator, resource_id = value.partition("|")
    if not separator or not resource_id:
        raise SnapshotProtocolError("alert snapshot sort key is invalid")
    return _parse_boundary(timestamp), resource_id


def _loaded_payload(payload_json: str) -> dict[str, JsonValue]:
    loaded = json.loads(payload_json)
    if not isinstance(loaded, dict):
        raise SnapshotProtocolError("alert snapshot payload must be an object")
    return cast(dict[str, JsonValue], loaded)


def _decimal(value: Decimal) -> str:
    return format(value, "f")


class AlertSnapshotResourceReader:
    """Read immutable alert publications and offline outcome evidence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def capture_boundary(self, *, resource_type: str, captured_at: datetime) -> str:
        self._require_resource_type(resource_type)
        return _canonical_timestamp(captured_at)

    def list_records(
        self,
        *,
        resource_type: str,
        boundary_key: str,
        after_sort_key: str | None,
        limit: int,
    ) -> Sequence[SnapshotRecord]:
        self._require_resource_type(resource_type)
        if limit < 1:
            raise SnapshotProtocolError("alert snapshot read limit must be positive")
        boundary = _parse_boundary(boundary_key)
        after = None if after_sort_key is None else _parse_after_sort_key(after_sort_key)
        if resource_type == ALERT:
            rows = self._page_rows(
                AlertRow,
                timestamp=AlertRow.created_at,
                identity=AlertRow.alert_id,
                boundary=boundary,
                after=after,
                limit=limit,
            )
            return tuple(
                self._record(
                    resource_type=resource_type,
                    resource_id=row.alert_id,
                    observed_at=row.created_at,
                    payload=self._alert_payload(row),
                )
                for row in rows
            )
        outcomes = self._page_rows(
            AlertOutcomeRow,
            timestamp=AlertOutcomeRow.recorded_at,
            identity=AlertOutcomeRow.outcome_id,
            boundary=boundary,
            after=after,
            limit=limit,
        )
        return tuple(
            self._record(
                resource_type=resource_type,
                resource_id=row.outcome_id,
                observed_at=row.recorded_at,
                payload=self._outcome_payload(row),
            )
            for row in outcomes
        )

    @staticmethod
    def _alert_payload(row: AlertRow) -> dict[str, JsonValue]:
        return {
            "alert_id": row.alert_id,
            "record_schema_version": row.schema_version,
            "evaluation_id": row.evaluation_id,
            "deduplication_key": row.deduplication_key,
            "rule_id": row.rule_id,
            "rule_version": row.rule_version,
            "source_kind": row.source_kind,
            "source_event_id": row.source_event_id,
            "delivery_channel": row.delivery_channel,
            "severity": row.severity,
            "draft_checksum": row.draft_checksum,
            "created_at": _canonical_timestamp(row.created_at),
            "expires_at": _canonical_timestamp(row.expires_at),
            "record": _loaded_payload(row.payload_json),
            "offline_only": True,
            "external_order_submission_allowed": False,
        }

    @staticmethod
    def _outcome_payload(row: AlertOutcomeRow) -> dict[str, JsonValue]:
        return {
            "outcome_id": row.outcome_id,
            "record_schema_version": row.schema_version,
            "simulation_id": row.simulation_id,
            "simulation_checksum": row.simulation_checksum,
            "alert_id": row.alert_id,
            "alert_checksum": row.alert_checksum,
            "mode": row.mode,
            "expected_trend": row.expected_trend,
            "observed_trend": row.observed_trend,
            "reference_price": _decimal(row.reference_price),
            "end_price": _decimal(row.end_price),
            "high_price": _decimal(row.high_price),
            "low_price": _decimal(row.low_price),
            "raw_return": _decimal(row.raw_return),
            "directional_return": _decimal(row.directional_return),
            "max_favorable_excursion": _decimal(row.max_favorable_excursion),
            "max_adverse_excursion": _decimal(row.max_adverse_excursion),
            "classification": row.classification,
            "false_positive": row.false_positive,
            "drifted": row.drifted,
            "policy_version": row.policy_version,
            "policy_checksum": row.policy_checksum,
            "classification_threshold": _decimal(row.classification_threshold),
            "observed_at": _canonical_timestamp(row.observed_at),
            "recorded_at": _canonical_timestamp(row.recorded_at),
            "recorded_by": row.recorded_by,
            "offline_only": row.offline_only,
            "external_order_submission_allowed": row.external_order_submission_allowed,
            "record_checksum": row.record_checksum,
            "record": _loaded_payload(row.payload_json),
        }

    def _record(
        self,
        *,
        resource_type: str,
        resource_id: str,
        observed_at: datetime,
        payload: dict[str, JsonValue],
    ) -> SnapshotRecord:
        normalized = normalize_database_timestamp(observed_at)
        schema_version = RESOURCE_SCHEMA_VERSIONS[resource_type]
        return SnapshotRecord(
            resource_type=resource_type,
            resource_id=resource_id,
            resource_schema_version=schema_version,
            observed_at=normalized,
            sort_key=_sort_key(normalized, resource_id),
            payload={"resource_schema_version": schema_version, **payload},
        )

    def _page_rows(
        self,
        model: type[_RowT],
        *,
        timestamp: InstrumentedAttribute[datetime],
        identity: InstrumentedAttribute[str],
        boundary: datetime,
        after: tuple[datetime, str] | None,
        limit: int,
    ) -> Sequence[_RowT]:
        statement = select(model).where(timestamp <= boundary)
        if after is not None:
            after_timestamp, after_identity = after
            statement = statement.where(
                or_(
                    timestamp > after_timestamp,
                    and_(timestamp == after_timestamp, identity > after_identity),
                )
            )
        return self._session.scalars(
            statement.order_by(timestamp.asc(), identity.asc()).limit(limit)
        ).all()

    @staticmethod
    def _require_resource_type(resource_type: str) -> None:
        if resource_type not in ALERT_SNAPSHOT_RESOURCE_TYPES:
            raise SnapshotProtocolError("snapshot resource type is not available in this stage")
