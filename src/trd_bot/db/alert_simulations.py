from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.alerts import AlertDraft
from trd_bot.alerts.simulations import (
    AlertSimulationMode,
    AlertSimulationRecord,
    AlertSimulationStatus,
    AlertSimulationSummary,
    AlertSimulationView,
    build_alert_simulation_id,
)
from trd_bot.db.models import AlertRow, AlertSimulationRow


class AlertSimulationConflictError(ValueError):
    """Safe conflict raised when an alert cannot enter offline observation."""

    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SqlAlchemyAlertSimulationRepository:
    """Persist immutable Paper/Shadow observation without any execution path."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def start(
        self,
        *,
        alert_id: str,
        mode: AlertSimulationMode,
        horizon_seconds: int,
        started_by: str,
        started_at: datetime,
    ) -> tuple[AlertSimulationView, bool] | None:
        simulation_id = build_alert_simulation_id(
            alert_id=alert_id,
            mode=mode,
            horizon_seconds=horizon_seconds,
        )
        existing = self.get(simulation_id, evaluated_at=started_at)
        if existing is not None:
            return existing, False

        alert_row = self._session.get(AlertRow, alert_id)
        if alert_row is None:
            return None
        alert = AlertDraft.model_validate_json(alert_row.payload_json)
        try:
            record = AlertSimulationRecord.build(
                alert=alert,
                mode=mode,
                horizon_seconds=horizon_seconds,
                started_at=started_at,
                started_by=started_by,
            )
        except ValueError as error:
            if "expired alert" in str(error):
                raise AlertSimulationConflictError(
                    code="alert_expired",
                    message="expired alert cannot start an offline simulation",
                ) from error
            raise

        self._session.add(self._row(record))
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            concurrent = self.get(simulation_id, evaluated_at=started_at)
            if concurrent is None:
                raise
            return concurrent, False
        return AlertSimulationView.from_record(record, evaluated_at=started_at), True

    def get(
        self,
        simulation_id: str,
        *,
        evaluated_at: datetime,
    ) -> AlertSimulationView | None:
        row = self._session.get(AlertSimulationRow, simulation_id)
        if row is None:
            return None
        return AlertSimulationView.from_record(
            self._record(row),
            evaluated_at=evaluated_at,
        )

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        evaluated_at: datetime,
        alert_id: str | None = None,
        mode: AlertSimulationMode | None = None,
        status: AlertSimulationStatus | None = None,
    ) -> tuple[tuple[AlertSimulationView, ...], int]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        statement = select(AlertSimulationRow)
        if alert_id is not None:
            statement = statement.where(AlertSimulationRow.alert_id == alert_id)
        if mode is not None:
            statement = statement.where(AlertSimulationRow.mode == mode.value)
        rows = self._session.scalars(
            statement.order_by(
                AlertSimulationRow.started_at.desc(),
                AlertSimulationRow.simulation_id.desc(),
            )
        ).all()
        views = tuple(
            AlertSimulationView.from_record(self._record(row), evaluated_at=evaluated_at)
            for row in rows
        )
        if status is not None:
            views = tuple(view for view in views if view.status is status)
        return views[offset : offset + limit], len(views)

    def summary(self, *, evaluated_at: datetime) -> AlertSimulationSummary:
        rows = self._session.scalars(select(AlertSimulationRow)).all()
        views = tuple(
            AlertSimulationView.from_record(self._record(row), evaluated_at=evaluated_at)
            for row in rows
        )
        return AlertSimulationSummary(
            evaluated_at=evaluated_at,
            total=len(views),
            paper=sum(view.simulation.mode is AlertSimulationMode.PAPER for view in views),
            shadow=sum(view.simulation.mode is AlertSimulationMode.SHADOW for view in views),
            observing=sum(view.status is AlertSimulationStatus.OBSERVING for view in views),
            awaiting_outcome=sum(
                view.status is AlertSimulationStatus.AWAITING_OUTCOME for view in views
            ),
        )

    @staticmethod
    def _record(row: AlertSimulationRow) -> AlertSimulationRecord:
        return AlertSimulationRecord.model_validate_json(row.payload_json)

    @staticmethod
    def _row(record: AlertSimulationRecord) -> AlertSimulationRow:
        return AlertSimulationRow(
            simulation_id=record.simulation_id,
            schema_version=record.schema_version,
            alert_id=record.alert_id,
            alert_checksum=record.alert_checksum,
            source_reference_id=record.source_reference_id,
            source_reference_checksum=record.source_reference_checksum,
            rule_id=record.rule_id,
            rule_version=record.rule_version,
            rule_definition_checksum=record.rule_definition_checksum,
            mode=record.mode.value,
            expected_trend=record.expected_trend.value,
            horizon_seconds=record.horizon_seconds,
            started_at=record.started_at,
            ends_at=record.ends_at,
            started_by=record.started_by,
            offline_only=record.offline_only,
            external_order_submission_allowed=record.external_order_submission_allowed,
            record_checksum=record.record_checksum,
            payload_json=record.model_dump_json(),
        )
