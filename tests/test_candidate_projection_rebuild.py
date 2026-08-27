import pytest

from tests.test_candidate_journal import (
    build_closed_lifecycle,
    build_no_position_lifecycle,
)
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyCandidateJournalRepository,
    SqlAlchemyCandidateProjectionRebuilder,
    SqlAlchemyCandidateProjectionRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.research.candidate_journal import CandidateJournalBuilder
from trd_bot.research.candidate_projection import CandidateJournalProjectionReader


def build_storage():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    return engine, factory


def test_rebuilder_backfills_existing_journals_into_empty_read_model() -> None:
    engine, factory = build_storage()
    journals = (
        CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle()),
        CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle()),
    )
    expected = CandidateJournalProjectionReader.build(journals)

    try:
        with factory() as session:
            journal_repository = SqlAlchemyCandidateJournalRepository(session)
            projection_repository = SqlAlchemyCandidateProjectionRepository(session)

            for journal in journals:
                journal_repository.save(journal)

            assert projection_repository.count() == 0

            rebuilt = SqlAlchemyCandidateProjectionRebuilder(session).rebuild()

            assert rebuilt == expected
            assert projection_repository.count() == len(expected)
            assert projection_repository.list_page(limit=100, offset=0) == expected
    finally:
        engine.dispose()


def test_rebuilder_is_idempotent() -> None:
    engine, factory = build_storage()
    journal = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())

    try:
        with factory() as session:
            SqlAlchemyCandidateJournalRepository(session).save(journal)
            rebuilder = SqlAlchemyCandidateProjectionRebuilder(session)

            first = rebuilder.rebuild()
            second = rebuilder.rebuild()

            repository = SqlAlchemyCandidateProjectionRepository(session)
            assert second == first
            assert repository.count() == len(first)
            assert repository.list_page(limit=100, offset=0) == first
    finally:
        engine.dispose()


def test_rebuilder_removes_projection_without_persisted_journal() -> None:
    engine, factory = build_storage()
    orphan_journal = CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle())
    orphan_projection = CandidateJournalProjectionReader.build((orphan_journal,))[0]

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateProjectionRepository(session)
            repository.save(orphan_projection)

            assert repository.count() == 1

            rebuilt = SqlAlchemyCandidateProjectionRebuilder(session).rebuild()

            assert rebuilt == ()
            assert repository.count() == 0
    finally:
        engine.dispose()


def test_rebuilder_rolls_back_existing_read_model_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = build_storage()
    persisted_journal = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    orphan_journal = CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle())
    orphan_projection = CandidateJournalProjectionReader.build((orphan_journal,))[0]

    try:
        with factory() as session:
            SqlAlchemyCandidateJournalRepository(session).save(persisted_journal)
            projection_repository = SqlAlchemyCandidateProjectionRepository(session)
            projection_repository.save(orphan_projection)

            rebuilder = SqlAlchemyCandidateProjectionRebuilder(
                session,
                projection_repository=projection_repository,
            )

            def fail_projection_save(*args, **kwargs):
                raise ValueError("projection rebuild failed")

            monkeypatch.setattr(
                projection_repository,
                "save",
                fail_projection_save,
            )

            with pytest.raises(ValueError, match="projection rebuild failed"):
                rebuilder.rebuild()

            assert projection_repository.count() == 1
            assert (
                projection_repository.get(orphan_projection.candidate.candidate_id)
                == orphan_projection
            )
    finally:
        engine.dispose()
