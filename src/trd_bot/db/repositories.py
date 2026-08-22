from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

from trd_bot.db.models import (
    DatasetSnapshotRow,
    ResearchExperimentRow,
    WalkForwardRunRow,
)
from trd_bot.research.datasets import (
    DatasetCatalogQuery,
    DatasetSnapshot,
    DatasetSortDirection,
    DatasetSortField,
)
from trd_bot.research.experiments import (
    ExperimentCatalogQuery,
    ExperimentSortDirection,
    ExperimentSortField,
    ResearchExperiment,
)
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
            conflict_message=("dataset ID already exists with different content"),
            get_existing=self.get,
            same_content=self._same_dataset,
        )

    def get(
        self,
        dataset_id: str,
    ) -> DatasetSnapshot | None:
        row = self._session.get(
            DatasetSnapshotRow,
            dataset_id,
        )

        if row is None:
            return None

        return DatasetSnapshot.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(DatasetSnapshotRow))

        return int(value or 0)

    def count_matching(
        self,
        query: DatasetCatalogQuery,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(DatasetSnapshotRow)
            .where(*self._dataset_conditions(query))
        )

        value = self._session.scalar(statement)

        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[DatasetSnapshot, ...]:
        return self.search_page(
            query=DatasetCatalogQuery(),
            limit=limit,
            offset=offset,
        )

    def search_page(
        self,
        *,
        query: DatasetCatalogQuery,
        limit: int,
        offset: int,
    ) -> tuple[DatasetSnapshot, ...]:
        _validate_pagination(
            limit=limit,
            offset=offset,
        )

        sort_column: InstrumentedAttribute[Any]

        if query.sort_by is DatasetSortField.START_TIME:
            sort_column = DatasetSnapshotRow.start_time

        elif query.sort_by is DatasetSortField.CANDLE_COUNT:
            sort_column = DatasetSnapshotRow.candle_count

        else:
            sort_column = DatasetSnapshotRow.created_at

        if query.sort_direction is DatasetSortDirection.DESCENDING:
            ordering = (
                sort_column.desc(),
                DatasetSnapshotRow.dataset_id.desc(),
            )

        else:
            ordering = (
                sort_column.asc(),
                DatasetSnapshotRow.dataset_id.asc(),
            )

        rows = self._session.scalars(
            select(DatasetSnapshotRow)
            .where(*self._dataset_conditions(query))
            .order_by(*ordering)
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(DatasetSnapshot.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _dataset_conditions(
        query: DatasetCatalogQuery,
    ) -> tuple[ColumnElement[bool], ...]:
        conditions: list[ColumnElement[bool]] = []

        if query.source is not None:
            conditions.append(DatasetSnapshotRow.source == query.source)

        if query.base_asset is not None:
            conditions.append(DatasetSnapshotRow.base_asset == query.base_asset)

        if query.quote_asset is not None:
            conditions.append(DatasetSnapshotRow.quote_asset == query.quote_asset)

        if query.timeframe is not None:
            conditions.append(DatasetSnapshotRow.timeframe == query.timeframe.value)

        return tuple(conditions)

    @staticmethod
    def _same_dataset(
        first: DatasetSnapshot,
        second: DatasetSnapshot,
    ) -> bool:
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

    def count_matching(
        self,
        query: ExperimentCatalogQuery,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(ResearchExperimentRow)
            .where(*self._experiment_conditions(query))
        )

        value = self._session.scalar(statement)

        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[ResearchExperiment, ...]:
        return self.search_page(
            query=ExperimentCatalogQuery(),
            limit=limit,
            offset=offset,
        )

    def search_page(
        self,
        *,
        query: ExperimentCatalogQuery,
        limit: int,
        offset: int,
    ) -> tuple[ResearchExperiment, ...]:
        _validate_pagination(
            limit=limit,
            offset=offset,
        )

        sort_column: InstrumentedAttribute[Any]

        if query.sort_by is ExperimentSortField.HORIZON_CANDLES:
            sort_column = ResearchExperimentRow.horizon_candles

        else:
            sort_column = ResearchExperimentRow.created_at

        if query.sort_direction is ExperimentSortDirection.DESCENDING:
            ordering = (
                sort_column.desc(),
                ResearchExperimentRow.experiment_id.desc(),
            )

        else:
            ordering = (
                sort_column.asc(),
                ResearchExperimentRow.experiment_id.asc(),
            )

        rows = self._session.scalars(
            select(ResearchExperimentRow)
            .where(*self._experiment_conditions(query))
            .order_by(*ordering)
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(ResearchExperiment.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _experiment_conditions(
        query: ExperimentCatalogQuery,
    ) -> tuple[ColumnElement[bool], ...]:
        conditions: list[ColumnElement[bool]] = []

        if query.dataset_id is not None:
            conditions.append(ResearchExperimentRow.dataset_id == query.dataset_id)

        if query.strategy_name is not None:
            conditions.append(ResearchExperimentRow.strategy_name == query.strategy_name)

        if query.strategy_version is not None:
            conditions.append(ResearchExperimentRow.strategy_version == query.strategy_version)

        if query.horizon_candles is not None:
            conditions.append(ResearchExperimentRow.horizon_candles == query.horizon_candles)

        return tuple(conditions)

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
