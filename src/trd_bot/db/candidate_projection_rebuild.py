from sqlalchemy import delete
from sqlalchemy.orm import Session

from trd_bot.db.candidate_journal_repositories import (
    SqlAlchemyCandidateJournalRepository,
)
from trd_bot.db.candidate_projection_repositories import (
    SqlAlchemyCandidateProjectionRepository,
)
from trd_bot.db.models import CandidateProjectionRow
from trd_bot.research.candidate_journal import CandidateJournalEntry
from trd_bot.research.candidate_projection import (
    CandidateJournalProjectionReader,
    CandidateProjection,
)


class SqlAlchemyCandidateProjectionRebuilder:
    """Rebuild candidate projections atomically from persisted journals."""

    def __init__(
        self,
        session: Session,
        *,
        journal_repository: SqlAlchemyCandidateJournalRepository | None = None,
        projection_repository: SqlAlchemyCandidateProjectionRepository | None = None,
    ) -> None:
        self._session = session
        self._journal_repository = journal_repository or SqlAlchemyCandidateJournalRepository(
            session
        )
        self._projection_repository = (
            projection_repository or SqlAlchemyCandidateProjectionRepository(session)
        )

    def rebuild(
        self,
        *,
        commit: bool = True,
    ) -> tuple[CandidateProjection, ...]:
        journals = self._load_journals()
        projections = CandidateJournalProjectionReader.build(journals)

        try:
            self._session.execute(delete(CandidateProjectionRow))

            for projection in projections:
                self._projection_repository.save(
                    projection,
                    commit=False,
                )

            if commit:
                self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return projections

    def _load_journals(self) -> tuple[CandidateJournalEntry, ...]:
        journal_count = self._journal_repository.count()
        if journal_count == 0:
            return ()

        return self._journal_repository.list_page(
            limit=journal_count,
            offset=0,
        )
