from sqlalchemy.orm import Session

from trd_bot.db.candidate_journal_repositories import (
    SqlAlchemyCandidateJournalRepository,
)
from trd_bot.db.candidate_projection_rebuild import (
    SqlAlchemyCandidateProjectionRebuilder,
)
from trd_bot.db.candidate_projection_repositories import (
    SqlAlchemyCandidateProjectionRepository,
)
from trd_bot.db.simulated_portfolio_repositories import (
    SqlAlchemySimulatedPortfolioRepository,
)
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
)
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleResult,
)


class SqlAlchemyCandidateLifecycleRecorder:
    """Atomically persist lifecycle, journal, and derived candidate projections."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._portfolio_repository = SqlAlchemySimulatedPortfolioRepository(session)
        self._journal_repository = SqlAlchemyCandidateJournalRepository(session)
        self._projection_repository = SqlAlchemyCandidateProjectionRepository(session)
        self._projection_rebuilder = SqlAlchemyCandidateProjectionRebuilder(
            session,
            journal_repository=self._journal_repository,
            projection_repository=self._projection_repository,
        )

    def record(
        self,
        lifecycle: CandidateReplayLifecycleResult,
    ) -> CandidateJournalEntry:
        journal = CandidateJournalBuilder.from_lifecycle(lifecycle)

        try:
            self._portfolio_repository.save(
                lifecycle.portfolio,
                commit=False,
            )
            persisted_journal = self._journal_repository.save(
                journal,
                commit=False,
            )
            self._refresh_candidate_projections()
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return persisted_journal

    def _refresh_candidate_projections(self) -> None:
        self._projection_rebuilder.rebuild(commit=False)
