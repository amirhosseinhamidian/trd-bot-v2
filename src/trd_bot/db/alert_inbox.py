from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from trd_bot.alerts import (
    AlertActionConflictError,
    AlertActionKind,
    AlertActionRecord,
    AlertDraft,
    AlertInboxItem,
    AlertInboxState,
    AlertInboxStatus,
    AlertInboxSummary,
    AlertSeverity,
)
from trd_bot.db.models import AlertActionRow, AlertInboxStateRow, AlertRow


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyAlertInboxRepository:
    """Query and mutate the operator-facing lifecycle of immutable alerts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        evaluated_at: datetime,
        status: AlertInboxStatus | None = None,
        severity: AlertSeverity | None = None,
    ) -> tuple[tuple[AlertInboxItem, ...], int]:
        if limit <= 0 or limit > 100:
            raise ValueError("alert inbox page limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("alert inbox page offset cannot be negative")
        evaluated = _utc(evaluated_at)
        filters = self._filters(status=status, severity=severity, evaluated_at=evaluated)
        statement = (
            select(AlertRow, AlertInboxStateRow)
            .outerjoin(AlertInboxStateRow, AlertInboxStateRow.alert_id == AlertRow.alert_id)
            .where(*filters)
            .order_by(AlertRow.created_at.desc(), AlertRow.alert_id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = self._session.execute(statement).all()
        count_statement = (
            select(func.count())
            .select_from(AlertRow)
            .outerjoin(AlertInboxStateRow, AlertInboxStateRow.alert_id == AlertRow.alert_id)
            .where(*filters)
        )
        total = int(self._session.scalar(count_statement) or 0)
        return (
            tuple(
                self._item(alert_row, state_row, evaluated_at=evaluated)
                for alert_row, state_row in rows
            ),
            total,
        )

    def get(
        self,
        alert_id: str,
        *,
        evaluated_at: datetime,
    ) -> AlertInboxItem | None:
        row = self._session.execute(
            select(AlertRow, AlertInboxStateRow)
            .outerjoin(AlertInboxStateRow, AlertInboxStateRow.alert_id == AlertRow.alert_id)
            .where(AlertRow.alert_id == alert_id)
        ).one_or_none()
        if row is None:
            return None
        return self._item(row[0], row[1], evaluated_at=_utc(evaluated_at))

    def summary(self, *, evaluated_at: datetime) -> AlertInboxSummary:
        evaluated = _utc(evaluated_at)
        counts = {
            status: self._count(status=status, evaluated_at=evaluated)
            for status in AlertInboxStatus
        }
        return AlertInboxSummary(
            evaluated_at=evaluated,
            total=sum(counts.values()),
            active=counts[AlertInboxStatus.ACTIVE],
            snoozed=counts[AlertInboxStatus.SNOOZED],
            acknowledged=counts[AlertInboxStatus.ACKNOWLEDGED],
            expired=counts[AlertInboxStatus.EXPIRED],
        )

    def acknowledge(
        self,
        alert_id: str,
        *,
        acted_by: str,
        occurred_at: datetime,
    ) -> tuple[AlertInboxItem | None, bool]:
        occurred = _utc(occurred_at)
        alert_row = self._locked_alert(alert_id)
        if alert_row is None:
            return None, False
        state_row, state = self._locked_state(alert_row)
        if state.acknowledged_at is not None:
            return self._item(alert_row, state_row, evaluated_at=occurred), False
        if _utc(alert_row.expires_at) <= occurred:
            raise AlertActionConflictError(
                code="alert_expired",
                message="Expired alert cannot be acknowledged.",
            )
        updated = state.acknowledge(acted_by=acted_by, occurred_at=occurred)
        action = AlertActionRecord.build(
            alert_id=alert_id,
            kind=AlertActionKind.ACKNOWLEDGED,
            acted_by=acted_by,
            occurred_at=occurred,
        )
        self._write_state(state_row, updated)
        self._stage_action(action)
        self._session.commit()
        return self._item(alert_row, state_row, evaluated_at=occurred), True

    def snooze(
        self,
        alert_id: str,
        *,
        acted_by: str,
        occurred_at: datetime,
        duration_seconds: int,
    ) -> tuple[AlertInboxItem | None, bool]:
        occurred = _utc(occurred_at)
        alert_row = self._locked_alert(alert_id)
        if alert_row is None:
            return None, False
        state_row, state = self._locked_state(alert_row)
        if _utc(alert_row.expires_at) <= occurred:
            raise AlertActionConflictError(
                code="alert_expired",
                message="Expired alert cannot be snoozed.",
            )
        if state.acknowledged_at is not None:
            raise AlertActionConflictError(
                code="alert_acknowledged",
                message="Acknowledged alert cannot be snoozed.",
            )
        updated = state.snooze(
            acted_by=acted_by,
            occurred_at=occurred,
            duration_seconds=duration_seconds,
        )
        action = AlertActionRecord.build(
            alert_id=alert_id,
            kind=AlertActionKind.SNOOZED,
            acted_by=acted_by,
            occurred_at=occurred,
            snoozed_until=updated.snoozed_until,
        )
        self._write_state(state_row, updated)
        self._stage_action(action)
        self._session.commit()
        return self._item(alert_row, state_row, evaluated_at=occurred), True

    def list_actions(self, alert_id: str) -> tuple[AlertActionRecord, ...]:
        rows = self._session.scalars(
            select(AlertActionRow)
            .where(AlertActionRow.alert_id == alert_id)
            .order_by(AlertActionRow.occurred_at, AlertActionRow.action_id)
        ).all()
        return tuple(AlertActionRecord.model_validate_json(row.payload_json) for row in rows)

    def _count(self, *, status: AlertInboxStatus, evaluated_at: datetime) -> int:
        statement = (
            select(func.count())
            .select_from(AlertRow)
            .outerjoin(AlertInboxStateRow, AlertInboxStateRow.alert_id == AlertRow.alert_id)
            .where(self._status_condition(status, evaluated_at))
        )
        return int(self._session.scalar(statement) or 0)

    @classmethod
    def _filters(
        cls,
        *,
        status: AlertInboxStatus | None,
        severity: AlertSeverity | None,
        evaluated_at: datetime,
    ) -> Sequence[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if status is not None:
            filters.append(cls._status_condition(status, evaluated_at))
        if severity is not None:
            filters.append(AlertRow.severity == severity.value)
        return filters

    @staticmethod
    def _status_condition(
        status: AlertInboxStatus,
        evaluated_at: datetime,
    ) -> ColumnElement[bool]:
        not_acknowledged = AlertInboxStateRow.acknowledged_at.is_(None)
        if status is AlertInboxStatus.ACKNOWLEDGED:
            return AlertInboxStateRow.acknowledged_at.is_not(None)
        if status is AlertInboxStatus.EXPIRED:
            return and_(not_acknowledged, AlertRow.expires_at <= evaluated_at)
        if status is AlertInboxStatus.SNOOZED:
            return and_(
                not_acknowledged,
                AlertRow.expires_at > evaluated_at,
                AlertInboxStateRow.snoozed_until > evaluated_at,
            )
        return and_(
            not_acknowledged,
            AlertRow.expires_at > evaluated_at,
            or_(
                AlertInboxStateRow.snoozed_until.is_(None),
                AlertInboxStateRow.snoozed_until <= evaluated_at,
            ),
        )

    def _locked_alert(self, alert_id: str) -> AlertRow | None:
        return self._session.scalar(
            select(AlertRow).where(AlertRow.alert_id == alert_id).with_for_update()
        )

    def _locked_state(self, alert: AlertRow) -> tuple[AlertInboxStateRow, AlertInboxState]:
        row = self._session.scalar(
            select(AlertInboxStateRow)
            .where(AlertInboxStateRow.alert_id == alert.alert_id)
            .with_for_update()
        )
        if row is None:
            initial = AlertInboxState.initial(
                alert_id=alert.alert_id,
                created_at=_utc(alert.created_at),
            )
            row = AlertInboxStateRow(
                alert_id=initial.alert_id,
                schema_version=initial.schema_version,
                acknowledged_at=None,
                acknowledged_by=None,
                snoozed_until=None,
                snoozed_by=None,
                updated_at=initial.updated_at,
            )
            self._session.add(row)
            self._session.flush()
            return row, initial
        return row, self._state_from_row(row)

    @staticmethod
    def _write_state(row: AlertInboxStateRow, state: AlertInboxState) -> None:
        row.schema_version = state.schema_version
        row.acknowledged_at = state.acknowledged_at
        row.acknowledged_by = state.acknowledged_by
        row.snoozed_until = state.snoozed_until
        row.snoozed_by = state.snoozed_by
        row.updated_at = state.updated_at

    def _stage_action(self, action: AlertActionRecord) -> None:
        self._session.add(
            AlertActionRow(
                action_id=action.action_id,
                schema_version=action.schema_version,
                alert_id=action.alert_id,
                kind=action.kind.value,
                acted_by=action.acted_by,
                occurred_at=action.occurred_at,
                snoozed_until=action.snoozed_until,
                action_checksum=action.action_checksum,
                payload_json=action.model_dump_json(),
            )
        )

    @classmethod
    def _item(
        cls,
        alert_row: AlertRow,
        state_row: AlertInboxStateRow | None,
        *,
        evaluated_at: datetime,
    ) -> AlertInboxItem:
        alert = AlertDraft.model_validate_json(alert_row.payload_json)
        state = (
            AlertInboxState.initial(alert_id=alert.alert_id, created_at=alert.created_at)
            if state_row is None
            else cls._state_from_row(state_row)
        )
        return AlertInboxItem.build(alert=alert, state=state, evaluated_at=evaluated_at)

    @staticmethod
    def _state_from_row(row: AlertInboxStateRow) -> AlertInboxState:
        return AlertInboxState(
            alert_id=row.alert_id,
            acknowledged_at=(None if row.acknowledged_at is None else _utc(row.acknowledged_at)),
            acknowledged_by=row.acknowledged_by,
            snoozed_until=(None if row.snoozed_until is None else _utc(row.snoozed_until)),
            snoozed_by=row.snoozed_by,
            updated_at=_utc(row.updated_at),
        )
