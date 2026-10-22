from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from trd_bot.db.market_data_import_repositories import (
    SqlAlchemyMarketDataImportRepository,
)
from trd_bot.db.repositories import SqlAlchemyDatasetRepository
from trd_bot.market_data.import_history import (
    MarketDataImportOperation,
    MarketDataImportRecord,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.historical_dataset_commits import (
    HistoricalDatasetCommitError,
    HistoricalDatasetCommitResult,
    HistoricalDatasetRefreshConflictError,
    finalize_initial_import_lineage,
    validate_commit_request,
)


class SqlAlchemyHistoricalDatasetCommitter:
    """Commit a dataset snapshot and successful audit record in one transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._datasets = SqlAlchemyDatasetRepository(session)
        self._history = SqlAlchemyMarketDataImportRepository(session)

    def commit(
        self,
        *,
        dataset: DatasetSnapshot,
        record: MarketDataImportRecord,
        expected_parent_import_id: str | None = None,
    ) -> HistoricalDatasetCommitResult:
        validate_commit_request(
            dataset=dataset,
            record=record,
            expected_parent_import_id=expected_parent_import_id,
        )

        for attempt in range(2):
            try:
                self._validate_refresh_parent(
                    record=record,
                    expected_parent_import_id=expected_parent_import_id,
                    for_update=True,
                )
                stored_dataset, created_snapshot = self._datasets.stage(dataset)
                committed_record = finalize_initial_import_lineage(
                    record,
                    created_snapshot=created_snapshot,
                )
                stored_record, _ = self._history.stage(committed_record)
                self._session.commit()
                return HistoricalDatasetCommitResult(
                    dataset=stored_dataset,
                    record=stored_record,
                    created_snapshot=created_snapshot,
                )
            except HistoricalDatasetRefreshConflictError:
                self._session.rollback()
                raise
            except IntegrityError as error:
                self._session.rollback()
                if record.operation is MarketDataImportOperation.REFRESH:
                    try:
                        self._validate_refresh_parent(
                            record=record,
                            expected_parent_import_id=expected_parent_import_id,
                            for_update=False,
                        )
                    except HistoricalDatasetRefreshConflictError:
                        self._session.rollback()
                        raise

                existing = self._datasets.get(dataset.dataset_id)
                can_retry_shared_snapshot = (
                    attempt == 0 and existing is not None and existing.has_same_content(dataset)
                )
                if can_retry_shared_snapshot:
                    continue
                raise HistoricalDatasetCommitError(
                    "historical dataset and import history could not be committed"
                ) from error
            except SQLAlchemyError as error:
                self._session.rollback()
                raise HistoricalDatasetCommitError(
                    "historical dataset and import history could not be committed"
                ) from error
            except Exception:
                self._session.rollback()
                raise

        raise HistoricalDatasetCommitError(
            "historical dataset and import history could not be committed"
        )

    def _validate_refresh_parent(
        self,
        *,
        record: MarketDataImportRecord,
        expected_parent_import_id: str | None,
        for_update: bool,
    ) -> None:
        if record.operation is not MarketDataImportOperation.REFRESH:
            return

        assert record.root_import_id is not None
        assert record.version_number is not None
        assert expected_parent_import_id is not None
        latest = self._history.get_latest_successful_version(
            record.root_import_id,
            for_update=for_update,
        )
        expected_version = (
            latest.version_number + 1
            if latest is not None and latest.version_number is not None
            else None
        )
        if (
            latest is None
            or latest.import_id != expected_parent_import_id
            or record.version_number != expected_version
        ):
            raise HistoricalDatasetRefreshConflictError(
                "dataset refresh lost a concurrency race; reload version history"
            )
