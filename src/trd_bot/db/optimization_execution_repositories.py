from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import OptimizationExecutionRow
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionRepository,
)


class SqlAlchemyOptimizationExecutionRepository:
    """Persist optimization execution lifecycle state with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, execution: OptimizationExecution) -> OptimizationExecution:
        row = self._session.get(
            OptimizationExecutionRow,
            execution.execution_id,
        )

        if row is None:
            row = OptimizationExecutionRow(
                execution_id=execution.execution_id,
                created_at=execution.created_at,
                updated_at=execution.updated_at,
                started_at=execution.started_at,
                finished_at=execution.finished_at,
                status=execution.status.value,
                dataset_id=execution.dataset_id,
                strategy_name=execution.strategy_name,
                strategy_version=execution.strategy_version,
                objective=execution.objective.value,
                total_trials=execution.total_trials,
                completed_trials=execution.completed_trials,
                best_experiment_id=execution.best_experiment_id,
                payload_json=execution.model_dump_json(),
            )
            self._session.add(row)
        else:
            row.updated_at = execution.updated_at
            row.started_at = execution.started_at
            row.finished_at = execution.finished_at
            row.status = execution.status.value
            row.completed_trials = execution.completed_trials
            row.best_experiment_id = execution.best_experiment_id
            row.payload_json = execution.model_dump_json()

        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValueError(
                "optimization execution could not be persisted"
            ) from error

        return execution

    def get(self, execution_id: str) -> OptimizationExecution | None:
        row = self._session.get(OptimizationExecutionRow, execution_id)
        if row is None:
            return None
        return OptimizationExecution.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(
            select(func.count()).select_from(OptimizationExecutionRow)
        )
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[OptimizationExecution, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        rows = self._session.scalars(
            select(OptimizationExecutionRow)
            .order_by(
                OptimizationExecutionRow.created_at.desc(),
                OptimizationExecutionRow.execution_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(
            OptimizationExecution.model_validate_json(row.payload_json)
            for row in rows
        )


def assert_optimization_repository_contract(
    repository: OptimizationExecutionRepository,
) -> OptimizationExecutionRepository:
    return repository
