from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import ExperimentExecutionRow
from trd_bot.research.experiment_executions import ExperimentExecution


class SqlAlchemyExperimentExecutionRepository:
    """Persist experiment execution lifecycle state with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        execution: ExperimentExecution,
    ) -> ExperimentExecution:
        row = self._session.get(
            ExperimentExecutionRow,
            execution.execution_id,
        )

        if row is None:
            row = ExperimentExecutionRow(
                execution_id=execution.execution_id,
                created_at=execution.created_at,
                updated_at=execution.updated_at,
                started_at=execution.started_at,
                finished_at=execution.finished_at,
                status=execution.status.value,
                progress_percent=execution.progress_percent,
                dataset_id=execution.dataset_id,
                strategy_name=execution.strategy_name,
                strategy_version=execution.strategy_version,
                experiment_id=execution.experiment_id,
                payload_json=execution.model_dump_json(),
            )

            self._session.add(row)

        else:
            self._update_row(
                row=row,
                execution=execution,
            )

        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()

            raise ValueError("experiment execution could not be persisted") from error

        return execution

    def get(
        self,
        execution_id: str,
    ) -> ExperimentExecution | None:
        row = self._session.get(
            ExperimentExecutionRow,
            execution_id,
        )

        if row is None:
            return None

        return ExperimentExecution.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(ExperimentExecutionRow))

        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[ExperimentExecution, ...]:
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        rows = self._session.scalars(
            select(ExperimentExecutionRow)
            .order_by(
                ExperimentExecutionRow.created_at.desc(),
                ExperimentExecutionRow.execution_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(ExperimentExecution.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _update_row(
        *,
        row: ExperimentExecutionRow,
        execution: ExperimentExecution,
    ) -> None:
        row.created_at = execution.created_at
        row.updated_at = execution.updated_at
        row.started_at = execution.started_at
        row.finished_at = execution.finished_at
        row.status = execution.status.value
        row.progress_percent = execution.progress_percent
        row.dataset_id = execution.dataset_id
        row.strategy_name = execution.strategy_name
        row.strategy_version = execution.strategy_version
        row.experiment_id = execution.experiment_id
        row.payload_json = execution.model_dump_json()

    @staticmethod
    def _validate_pagination(
        *,
        limit: int,
        offset: int,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")
