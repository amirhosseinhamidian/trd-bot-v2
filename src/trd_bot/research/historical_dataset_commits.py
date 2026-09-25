from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from trd_bot.market_data.import_history import (
    MarketDataImportOperation,
    MarketDataImportRecord,
    MarketDataImportRepository,
    MarketDataImportStatus,
)
from trd_bot.research.datasets import DatasetRepository, DatasetSnapshot


class HistoricalDatasetRefreshConflictError(RuntimeError):
    """Raised when another refresh advances a dataset lineage first."""


class HistoricalDatasetCommitError(RuntimeError):
    """Raised when an atomic dataset and import-history commit fails."""


@dataclass(frozen=True)
class HistoricalDatasetCommitResult:
    """The canonical snapshot and audit record committed together."""

    dataset: DatasetSnapshot
    record: MarketDataImportRecord
    created_snapshot: bool


class HistoricalDatasetCommitter(Protocol):
    """Atomically persist one successful historical dataset operation."""

    def commit(
        self,
        *,
        dataset: DatasetSnapshot,
        record: MarketDataImportRecord,
        expected_parent_import_id: str | None = None,
    ) -> HistoricalDatasetCommitResult: ...


def validate_commit_request(
    *,
    dataset: DatasetSnapshot,
    record: MarketDataImportRecord,
    expected_parent_import_id: str | None,
) -> None:
    """Validate invariants shared by persistent and in-memory committers."""

    if record.status is not MarketDataImportStatus.SUCCEEDED:
        raise ValueError("atomic historical dataset commits require a successful record")
    if record.dataset_id != dataset.dataset_id:
        raise ValueError("import history must reference the committed dataset")

    if record.operation is MarketDataImportOperation.REFRESH:
        if expected_parent_import_id is None:
            raise ValueError("refresh commits require an expected parent import")
        if record.parent_import_id != expected_parent_import_id:
            raise ValueError("refresh parent does not match the expected lineage parent")
        expected_content_changed = dataset.dataset_id != record.source_dataset_id
        if record.content_changed is not expected_content_changed:
            raise ValueError("refresh content-change flag does not match dataset identity")
    elif expected_parent_import_id is not None:
        raise ValueError("initial import commits cannot define an expected parent")


def finalize_initial_import_lineage(
    record: MarketDataImportRecord,
    *,
    created_snapshot: bool,
) -> MarketDataImportRecord:
    """Assign version one only to the import that creates canonical content."""

    if record.operation is not MarketDataImportOperation.IMPORT:
        return record

    payload = record.model_dump()
    payload.update(
        {
            "root_import_id": record.import_id if created_snapshot else None,
            "version_number": 1 if created_snapshot else None,
        }
    )
    return MarketDataImportRecord.model_validate(payload)


class InMemoryHistoricalDatasetCommitter:
    """Serialize atomic commits for tests and isolated in-memory workflows."""

    def __init__(
        self,
        *,
        datasets: DatasetRepository,
        history: MarketDataImportRepository,
    ) -> None:
        self._datasets = datasets
        self._history = history
        self._lock = RLock()

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

        with self._lock:
            if record.operation is MarketDataImportOperation.REFRESH:
                assert record.root_import_id is not None
                assert record.version_number is not None
                latest = self._history.get_latest_successful_version(record.root_import_id)
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

            existing_dataset = self._datasets.get(dataset.dataset_id)
            if existing_dataset is not None and not existing_dataset.has_same_content(dataset):
                raise ValueError("dataset ID already exists with different content")
            created_snapshot = existing_dataset is None
            committed_record = finalize_initial_import_lineage(
                record,
                created_snapshot=created_snapshot,
            )

            existing_record = self._history.get(committed_record.import_id)
            if existing_record is not None and existing_record != committed_record:
                raise ValueError("market-data import ID already exists with different content")

            stored_dataset = self._datasets.save(dataset)
            stored_record = self._history.save(committed_record)
            return HistoricalDatasetCommitResult(
                dataset=stored_dataset,
                record=stored_record,
                created_snapshot=created_snapshot,
            )
