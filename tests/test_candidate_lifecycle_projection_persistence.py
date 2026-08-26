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
from trd_bot.db.candidate_projection_repositories import (
    SqlAlchemyCandidateProjectionRepository,
)
from trd_bot.db.simulated_portfolio_repositories import (
    SqlAlchemySimulatedPortfolioRepository,
)
from trd_bot.research.candidate_projection import CandidateJournalProjectionReader


def build_storage():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    return engine, factory


def test_recorder_persists_candidate_projections_with_journal() -> None:
    engine, factory = build_storage()
    lifecycle = build_closed_lifecycle()

    try:
        with factory() as session:
            journal = SqlAlchemyCandidateLifecycleRecorder(session).record(lifecycle)
            expected = CandidateJournalProjectionReader.build((journal,))
            projections = SqlAlchemyCandidateProjectionRepository(session)

            assert projections.count() == len(expected)
            for projection in expected:
                assert projections.get(projection.candidate.candidate_id) == projection
    finally:
        engine.dispose()


def test_recorder_persists_no_position_candidate_projection() -> None:
    engine, factory = build_storage()
    lifecycle = build_no_position_lifecycle()

    try:
        with factory() as session:
            journal = SqlAlchemyCandidateLifecycleRecorder(session).record(lifecycle)
            expected = CandidateJournalProjectionReader.build((journal,))
            projections = SqlAlchemyCandidateProjectionRepository(session)

            assert projections.list_page(limit=100, offset=0) == expected
    finally:
        engine.dispose()


def test_recorder_projection_refresh_is_idempotent() -> None:
    engine, factory = build_storage()
    lifecycle = build_closed_lifecycle()

    try:
        with factory() as session:
            recorder = SqlAlchemyCandidateLifecycleRecorder(session)

            first_journal = recorder.record(lifecycle)
            second_journal = recorder.record(lifecycle)

            assert second_journal == first_journal

            expected = CandidateJournalProjectionReader.build((first_journal,))
            projections = SqlAlchemyCandidateProjectionRepository(session)

            assert projections.count() == len(expected)
            assert projections.list_page(limit=100, offset=0) == expected
    finally:
        engine.dispose()


def test_projection_failure_rolls_back_portfolio_and_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = build_storage()
    lifecycle = build_closed_lifecycle()

    try:
        with factory() as session:
            recorder = SqlAlchemyCandidateLifecycleRecorder(session)

            def fail_projection_save(*args, **kwargs):
                raise ValueError("projection write failed")

            monkeypatch.setattr(
                recorder._projection_repository,
                "save",
                fail_projection_save,
            )

            with pytest.raises(
                ValueError,
                match="projection write failed",
            ):
                recorder.record(lifecycle)

            assert (
                SqlAlchemySimulatedPortfolioRepository(session).get(
                    lifecycle.portfolio.portfolio_id
                )
                is None
            )
            assert SqlAlchemyCandidateJournalRepository(session).count() == 0
            assert SqlAlchemyCandidateProjectionRepository(session).count() == 0
    finally:
        engine.dispose()
