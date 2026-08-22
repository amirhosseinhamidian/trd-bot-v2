from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import (
    DatasetSnapshotRow,
    ResearchExperimentRow,
    WalkForwardRunRow,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.experiments import ResearchExperiment
from trd_bot.research.walk_forward_runs import WalkForwardResearchRun


def _validate_pagination(*, limit: int, offset: int) -> None:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if offset < 0:
        raise ValueError("offset cannot be negative")


def _commit_or_resolve[StoredModel: (DatasetSnapshot, ResearchExperiment, WalkForwardResearchRun)](
    *,
    session: Session,
    model: StoredModel,
    identity: str,
    conflict_message: str,
    get_existing: Callable[[str], StoredModel | None],
    same_content: Callable[[StoredModel, StoredModel], bool],
) -> StoredModel:
    try:
        session.commit()
        return model
    except IntegrityError as error:
        session.rollback()
        existing = get_existing(identity)
        if existing is not None and same_content(existing, model):
            return existing
        raise ValueError(conflict_message) from error


class SqlAlchemyDatasetRepository:
    """Persist immutable dataset snapshots with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, dataset: DatasetSnapshot) -> DatasetSnapshot:
        existing = self.get(dataset.dataset_id)
        if existing is not None:
            if not self._same_dataset(existing, dataset):
                raise ValueError("dataset ID already exists with different content")
            return existing

        self._session.add(
            DatasetSnapshotRow(
                dataset_id=dataset.dataset_id,
                created_at=dataset.created_at,
                source=dataset.source,
                base_asset=dataset.pair.base_asset,
                quote_asset=dataset.pair.quote_asset,
                market_type=dataset.pair.market_type.value,
                timeframe=dataset.timeframe.value,
                start_time=dataset.start_time,
                end_time=dataset.end_time,
                candle_count=dataset.candle_count,
                checksum=dataset.checksum,
                payload_json=dataset.model_dump_json(),
            )
        )
        return _commit_or_resolve(
            session=self._session,
            model=dataset,
            identity=dataset.dataset_id,
            conflict_message="dataset ID already exists with different content",
            get_existing=self.get,
            same_content=self._same_dataset,
        )

    def get(self, dataset_id: str) -> DatasetSnapshot | None:
        row = self._session.get(DatasetSnapshotRow, dataset_id)
        if row is None:
            return None
        return DatasetSnapshot.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(DatasetSnapshotRow))
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[DatasetSnapshot, ...]:
        _validate_pagination(limit=limit, offset=offset)
        rows = self._session.scalars(
            select(DatasetSnapshotRow)
            .order_by(DatasetSnapshotRow.created_at, DatasetSnapshotRow.dataset_id)
            .offset(offset)
            .limit(limit)
        ).all()
        return tuple(DatasetSnapshot.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _same_dataset(first: DatasetSnapshot, second: DatasetSnapshot) -> bool:
        return first.checksum == second.checksum and first.candles == second.candles


class SqlAlchemyExperimentRegistry:
    """Persist standard research experiments with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, experiment: ResearchExperiment) -> ResearchExperiment:
        existing = self.get(experiment.experiment_id)
        if existing is not None:
            if not self._same_experiment(existing, experiment):
                raise ValueError("experiment ID already exists with different content")
            return existing

        self._session.add(
            ResearchExperimentRow(
                experiment_id=experiment.experiment_id,
                created_at=experiment.created_at,
                dataset_id=experiment.dataset_id,
                strategy_name=experiment.strategy_name,
                strategy_version=experiment.strategy_version,
                horizon_candles=experiment.horizon_candles,
                payload_json=experiment.model_dump_json(),
            )
        )
        return _commit_or_resolve(
            session=self._session,
            model=experiment,
            identity=experiment.experiment_id,
            conflict_message="experiment ID already exists with different content",
            get_existing=self.get,
            same_content=self._same_experiment,
        )

    def get(self, experiment_id: str) -> ResearchExperiment | None:
        row = self._session.get(ResearchExperimentRow, experiment_id)
        if row is None:
            return None
        return ResearchExperiment.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(ResearchExperimentRow))
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[ResearchExperiment, ...]:
        _validate_pagination(limit=limit, offset=offset)
        rows = self._session.scalars(
            select(ResearchExperimentRow)
            .order_by(ResearchExperimentRow.created_at, ResearchExperimentRow.experiment_id)
            .offset(offset)
            .limit(limit)
        ).all()
        return tuple(ResearchExperiment.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _same_experiment(
        first: ResearchExperiment,
        second: ResearchExperiment,
    ) -> bool:
        return (
            first.dataset_id == second.dataset_id
            and first.strategy_name == second.strategy_name
            and first.strategy_version == second.strategy_version
            and first.horizon_candles == second.horizon_candles
            and first.parameters == second.parameters
            and first.result == second.result
        )


class SqlAlchemyWalkForwardRunRegistry:
    """Persist offline walk-forward research runs with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, run: WalkForwardResearchRun) -> WalkForwardResearchRun:
        existing = self.get(run.execution_id)
        if existing is not None:
            if not self._same_run(existing, run):
                raise ValueError("walk-forward execution ID already has different content")
            return existing

        result = run.result
        self._session.add(
            WalkForwardRunRow(
                execution_id=run.execution_id,
                created_at=run.created_at,
                source_dataset_id=result.source_dataset_id,
                plan_id=result.plan_id,
                strategy_name=result.strategy_name,
                strategy_version=result.strategy_version,
                horizon_candles=result.horizon_candles,
                payload_json=run.model_dump_json(),
            )
        )
        return _commit_or_resolve(
            session=self._session,
            model=run,
            identity=run.execution_id,
            conflict_message="walk-forward execution ID already has different content",
            get_existing=self.get,
            same_content=self._same_run,
        )

    def get(self, execution_id: str) -> WalkForwardResearchRun | None:
        row = self._session.get(WalkForwardRunRow, execution_id)
        if row is None:
            return None
        return WalkForwardResearchRun.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(WalkForwardRunRow))
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardResearchRun, ...]:
        _validate_pagination(limit=limit, offset=offset)
        rows = self._session.scalars(
            select(WalkForwardRunRow)
            .order_by(WalkForwardRunRow.created_at, WalkForwardRunRow.execution_id)
            .offset(offset)
            .limit(limit)
        ).all()
        return tuple(WalkForwardResearchRun.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _same_run(
        first: WalkForwardResearchRun,
        second: WalkForwardResearchRun,
    ) -> bool:
        return (
            first.walk_forward_config == second.walk_forward_config
            and first.result == second.result
        )
