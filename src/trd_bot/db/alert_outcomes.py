from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.alerts.outcomes import (
    AlertOutcomeClassification,
    AlertOutcomeRecord,
    AlertOutcomeSummary,
    build_alert_outcome_id,
)
from trd_bot.alerts.simulations import AlertSimulationRecord
from trd_bot.db.models import AlertOutcomeRow, AlertSimulationRow
from trd_bot.market_context import MarketTrendRegime


class AlertOutcomeConflictError(ValueError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SqlAlchemyAlertOutcomeRepository:
    """Store immutable manual outcome evidence for offline observations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        simulation_id: str,
        reference_price: Decimal,
        end_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        observed_trend: MarketTrendRegime,
        observed_at: datetime,
        recorded_at: datetime,
        recorded_by: str,
    ) -> tuple[AlertOutcomeRecord, bool] | None:
        outcome_id = build_alert_outcome_id(simulation_id)
        existing = self.get(outcome_id)
        if existing is not None:
            return existing, False

        simulation_row = self._session.get(AlertSimulationRow, simulation_id)
        if simulation_row is None:
            return None
        simulation = AlertSimulationRecord.model_validate_json(simulation_row.payload_json)
        try:
            outcome = AlertOutcomeRecord.build(
                simulation=simulation,
                reference_price=reference_price,
                end_price=end_price,
                high_price=high_price,
                low_price=low_price,
                observed_trend=observed_trend,
                observed_at=observed_at,
                recorded_at=recorded_at,
                recorded_by=recorded_by,
            )
        except ValueError as error:
            if "before simulation horizon" in str(error):
                raise AlertOutcomeConflictError(
                    code="simulation_horizon_incomplete",
                    message="alert outcome cannot be recorded before simulation horizon",
                ) from error
            raise

        self._session.add(self._row(outcome))
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            concurrent = self.get(outcome_id)
            if concurrent is None:
                raise
            return concurrent, False
        return outcome, True

    def get(self, outcome_id: str) -> AlertOutcomeRecord | None:
        row = self._session.get(AlertOutcomeRow, outcome_id)
        return None if row is None else self._record(row)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        alert_id: str | None = None,
        simulation_id: str | None = None,
        classification: AlertOutcomeClassification | None = None,
    ) -> tuple[tuple[AlertOutcomeRecord, ...], int]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        statement = select(AlertOutcomeRow)
        if alert_id is not None:
            statement = statement.where(AlertOutcomeRow.alert_id == alert_id)
        if simulation_id is not None:
            statement = statement.where(AlertOutcomeRow.simulation_id == simulation_id)
        if classification is not None:
            statement = statement.where(AlertOutcomeRow.classification == classification.value)
        rows = self._session.scalars(
            statement.order_by(
                AlertOutcomeRow.recorded_at.desc(), AlertOutcomeRow.outcome_id.desc()
            )
        ).all()
        return tuple(self._record(row) for row in rows[offset : offset + limit]), len(rows)

    def summary(self, *, evaluated_at: datetime) -> AlertOutcomeSummary:
        rows = self._session.scalars(select(AlertOutcomeRow)).all()
        outcomes = tuple(self._record(row) for row in rows)
        completed = len(outcomes)
        awaiting = int(
            self._session.scalar(
                select(func.count())
                .select_from(AlertSimulationRow)
                .outerjoin(
                    AlertOutcomeRow,
                    AlertOutcomeRow.simulation_id == AlertSimulationRow.simulation_id,
                )
                .where(
                    AlertSimulationRow.ends_at <= evaluated_at, AlertOutcomeRow.outcome_id.is_(None)
                )
            )
            or 0
        )
        denominator = Decimal(completed) if completed else Decimal(1)
        false_positive = sum(outcome.false_positive for outcome in outcomes)
        drifted = sum(outcome.drifted for outcome in outcomes)
        average = (
            sum((outcome.directional_return for outcome in outcomes), Decimal(0)) / denominator
            if completed
            else Decimal(0)
        )
        return AlertOutcomeSummary(
            evaluated_at=evaluated_at,
            completed=completed,
            awaiting_outcome=awaiting,
            confirmed=sum(
                outcome.classification is AlertOutcomeClassification.CONFIRMED
                for outcome in outcomes
            ),
            neutral=sum(
                outcome.classification is AlertOutcomeClassification.NEUTRAL for outcome in outcomes
            ),
            false_positive=false_positive,
            drifted=drifted,
            paper=sum(outcome.mode == "paper" for outcome in outcomes),
            shadow=sum(outcome.mode == "shadow" for outcome in outcomes),
            false_positive_rate=Decimal(false_positive) / denominator if completed else Decimal(0),
            drift_rate=Decimal(drifted) / denominator if completed else Decimal(0),
            average_directional_return=average.quantize(Decimal("0.00000001")),
        )

    @staticmethod
    def _record(row: AlertOutcomeRow) -> AlertOutcomeRecord:
        return AlertOutcomeRecord.model_validate_json(row.payload_json)

    @staticmethod
    def _row(outcome: AlertOutcomeRecord) -> AlertOutcomeRow:
        return AlertOutcomeRow(
            outcome_id=outcome.outcome_id,
            schema_version=outcome.schema_version,
            simulation_id=outcome.simulation_id,
            simulation_checksum=outcome.simulation_checksum,
            alert_id=outcome.alert_id,
            alert_checksum=outcome.alert_checksum,
            mode=outcome.mode,
            expected_trend=outcome.expected_trend.value,
            observed_trend=outcome.observed_trend.value,
            reference_price=outcome.reference_price,
            end_price=outcome.end_price,
            high_price=outcome.high_price,
            low_price=outcome.low_price,
            raw_return=outcome.raw_return,
            directional_return=outcome.directional_return,
            max_favorable_excursion=outcome.max_favorable_excursion,
            max_adverse_excursion=outcome.max_adverse_excursion,
            classification=outcome.classification.value,
            false_positive=outcome.false_positive,
            drifted=outcome.drifted,
            policy_version=outcome.policy_version,
            policy_checksum=outcome.policy_checksum,
            classification_threshold=outcome.classification_threshold,
            observed_at=outcome.observed_at,
            recorded_at=outcome.recorded_at,
            recorded_by=outcome.recorded_by,
            offline_only=outcome.offline_only,
            external_order_submission_allowed=outcome.external_order_submission_allowed,
            record_checksum=outcome.record_checksum,
            payload_json=outcome.model_dump_json(),
        )
