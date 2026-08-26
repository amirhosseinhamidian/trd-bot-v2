import pytest

from tests.test_candidate_journal import (
    build_closed_lifecycle,
    build_no_position_lifecycle,
)
from trd_bot.db import DatabaseBase, create_database_engine, create_session_factory
from trd_bot.db.candidate_journal_repositories import (
    SqlAlchemyCandidateJournalRepository,
)
from trd_bot.db.candidate_lifecycle_persistence import (
    SqlAlchemyCandidateLifecycleRecorder,
)
from trd_bot.db.simulated_portfolio_repositories import (
    SqlAlchemySimulatedPortfolioRepository,
)
from trd_bot.research.candidate_journal import CandidateJournalBuilder


def build_storage():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    return engine, factory


def test_recorder_persists_final_portfolio_and_journal_atomically() -> None:
    engine, factory = build_storage()
    lifecycle = build_closed_lifecycle()

    try:
        with factory() as session:
            journal = SqlAlchemyCandidateLifecycleRecorder(session).record(lifecycle)

            portfolio_repository = SqlAlchemySimulatedPortfolioRepository(session)
            journal_repository = SqlAlchemyCandidateJournalRepository(session)

            stored_portfolio = portfolio_repository.get(lifecycle.portfolio.portfolio_id)
            assert stored_portfolio == lifecycle.portfolio
            assert stored_portfolio.positions == lifecycle.portfolio.positions

            assert journal_repository.get(journal.journal_id) == journal
            assert journal.position_id is not None
            assert (
                portfolio_repository.get_position(journal.position_id)
                == lifecycle.monitoring.closed_position
            )
    finally:
        engine.dispose()


def test_recorder_is_idempotent_for_same_lifecycle() -> None:
    engine, factory = build_storage()
    lifecycle = build_closed_lifecycle()

    try:
        with factory() as session:
            recorder = SqlAlchemyCandidateLifecycleRecorder(session)

            first = recorder.record(lifecycle)
            second = recorder.record(lifecycle)

            assert second == first
            assert SqlAlchemyCandidateJournalRepository(session).count() == 1
            assert SqlAlchemySimulatedPortfolioRepository(session).count() == 1
    finally:
        engine.dispose()


def test_recorder_persists_no_position_lifecycle() -> None:
    engine, factory = build_storage()
    lifecycle = build_no_position_lifecycle()

    try:
        with factory() as session:
            journal = SqlAlchemyCandidateLifecycleRecorder(session).record(lifecycle)

            assert journal.selected_candidate_id is None
            assert journal.position_id is None
            assert (
                SqlAlchemySimulatedPortfolioRepository(session).get(
                    lifecycle.portfolio.portfolio_id
                )
                == lifecycle.portfolio
            )
    finally:
        engine.dispose()


def test_recorder_rolls_back_portfolio_when_journal_conflicts() -> None:
    engine, factory = build_storage()
    lifecycle = build_closed_lifecycle()
    requested_journal = CandidateJournalBuilder.from_lifecycle(lifecycle)
    conflicting_journal = CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle())

    try:
        with factory() as session:
            conflicting_row = SqlAlchemyCandidateJournalRepository._build_row(conflicting_journal)
            conflicting_row.journal_id = requested_journal.journal_id
            session.add(conflicting_row)
            session.commit()

            with pytest.raises(
                ValueError,
                match="already exists with different payload",
            ):
                SqlAlchemyCandidateLifecycleRecorder(session).record(lifecycle)

            assert (
                SqlAlchemySimulatedPortfolioRepository(session).get(
                    lifecycle.portfolio.portfolio_id
                )
                is None
            )
            assert SqlAlchemyCandidateJournalRepository(session).count() == 1
    finally:
        engine.dispose()
