from sqlalchemy.orm import Session

from trd_bot.db.candidate_journal_repositories import (
    SqlAlchemyCandidateJournalRepository,
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
    """Atomically persist a completed offline lifecycle and its journal."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._portfolio_repository = SqlAlchemySimulatedPortfolioRepository(session)
        self._journal_repository = SqlAlchemyCandidateJournalRepository(session)

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
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return persisted_journal
