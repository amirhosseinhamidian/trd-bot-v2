from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import CandidateJournalRow
from trd_bot.research.candidate_journal import CandidateJournalEntry


class SqlAlchemyCandidateJournalRepository:
    """Persist immutable candidate lifecycle journal entries with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        journal: CandidateJournalEntry,
        *,
        commit: bool = True,
    ) -> CandidateJournalEntry:
        existing = self._session.get(CandidateJournalRow, journal.journal_id)

        if existing is not None:
            stored = CandidateJournalEntry.model_validate_json(existing.payload_json)
            if stored != journal:
                raise ValueError("candidate journal ID already exists with different payload")
            return stored

        self._session.add(self._build_row(journal))

        try:
            self._session.flush()
            if commit:
                self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValueError("candidate journal could not be persisted") from error

        return journal

    def get(self, journal_id: str) -> CandidateJournalEntry | None:
        row = self._session.get(CandidateJournalRow, journal_id)

        if row is None:
            return None

        return CandidateJournalEntry.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(CandidateJournalRow))
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[CandidateJournalEntry, ...]:
        self._validate_pagination(limit=limit, offset=offset)

        rows = self._session.scalars(
            select(CandidateJournalRow)
            .order_by(
                CandidateJournalRow.recorded_at.desc(),
                CandidateJournalRow.journal_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(CandidateJournalEntry.model_validate_json(row.payload_json) for row in rows)

    def list_by_dataset(
        self,
        *,
        dataset_id: str,
        limit: int,
        offset: int,
    ) -> tuple[CandidateJournalEntry, ...]:
        self._validate_pagination(limit=limit, offset=offset)

        rows = self._session.scalars(
            select(CandidateJournalRow)
            .where(CandidateJournalRow.dataset_id == dataset_id)
            .order_by(
                CandidateJournalRow.recorded_at.desc(),
                CandidateJournalRow.journal_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(CandidateJournalEntry.model_validate_json(row.payload_json) for row in rows)

    def list_by_selected_candidate(
        self,
        *,
        candidate_id: str,
        limit: int,
        offset: int,
    ) -> tuple[CandidateJournalEntry, ...]:
        self._validate_pagination(limit=limit, offset=offset)

        rows = self._session.scalars(
            select(CandidateJournalRow)
            .where(CandidateJournalRow.selected_candidate_id == candidate_id)
            .order_by(
                CandidateJournalRow.recorded_at.desc(),
                CandidateJournalRow.journal_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(CandidateJournalEntry.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _build_row(journal: CandidateJournalEntry) -> CandidateJournalRow:
        return CandidateJournalRow(
            journal_id=journal.journal_id,
            schema_version=journal.schema_version,
            recorded_at=journal.recorded_at,
            evaluated_at=journal.evaluated_at,
            status=journal.status.value,
            dataset_id=journal.dataset_id,
            portfolio_id=journal.portfolio_id,
            attempted_count=len(journal.attempted_candidate_ids),
            selected_candidate_id=journal.selected_candidate_id,
            signal_id=journal.signal_id,
            experiment_id=journal.experiment_id,
            position_id=journal.position_id,
            exit_reason=(journal.exit_reason.value if journal.exit_reason is not None else None),
            payload_json=journal.model_dump_json(),
        )

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")
