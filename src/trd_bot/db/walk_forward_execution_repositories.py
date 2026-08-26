from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import WalkForwardExecutionRow
from trd_bot.research.walk_forward_executions import WalkForwardExecution


class SqlAlchemyWalkForwardExecutionRepository:
    """Persist walk-forward execution lifecycle state with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        execution: WalkForwardExecution,
    ) -> WalkForwardExecution:
        row = self._session.get(
            WalkForwardExecutionRow,
            execution.execution_id,
        )

        if row is None:
            row = WalkForwardExecutionRow(
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
                total_folds=execution.total_folds,
                completed_folds=execution.completed_folds,
                walk_forward_run_id=execution.walk_forward_run_id,
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

            raise ValueError("walk-forward execution could not be persisted") from error

        return execution

    def get(
        self,
        execution_id: str,
    ) -> WalkForwardExecution | None:
        row = self._session.get(
            WalkForwardExecutionRow,
            execution_id,
        )

        if row is None:
            return None

        return WalkForwardExecution.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(WalkForwardExecutionRow))

        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardExecution, ...]:
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        rows = self._session.scalars(
            select(WalkForwardExecutionRow)
            .order_by(
                WalkForwardExecutionRow.created_at.desc(),
                WalkForwardExecutionRow.execution_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(WalkForwardExecution.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _update_row(
        *,
        row: WalkForwardExecutionRow,
        execution: WalkForwardExecution,
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
        row.total_folds = execution.total_folds
        row.completed_folds = execution.completed_folds
        row.walk_forward_run_id = execution.walk_forward_run_id
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
