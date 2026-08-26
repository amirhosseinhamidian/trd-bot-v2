from sqlalchemy import select

from tests.test_candidate_journal import (
    build_closed_lifecycle,
    build_no_position_lifecycle,
)
from trd_bot.db import (
    CandidateJournalRow,
    DatabaseBase,
    SqlAlchemyCandidateJournalRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.research.candidate_journal import CandidateJournalBuilder


def build_repository():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    return engine, factory


def test_repository_round_trips_closed_candidate_journal() -> None:
    engine, factory = build_repository()
    journal = CandidateJournalBuilder.from_lifecycle(
        build_closed_lifecycle(),
    )

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateJournalRepository(session)
            saved = repository.save(journal)

            assert saved == journal
            assert repository.count() == 1
            assert repository.get(journal.journal_id) == journal

            row = session.scalar(
                select(CandidateJournalRow).where(
                    CandidateJournalRow.journal_id == journal.journal_id
                )
            )
            assert row is not None
            assert row.dataset_id == journal.dataset_id
            assert row.selected_candidate_id == journal.selected_candidate_id
            assert row.position_id == journal.position_id
            assert journal.exit_reason is not None
            assert row.exit_reason == journal.exit_reason.value
    finally:
        engine.dispose()


def test_repository_save_is_idempotent_for_same_journal() -> None:
    engine, factory = build_repository()
    journal = CandidateJournalBuilder.from_lifecycle(
        build_closed_lifecycle(),
    )

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateJournalRepository(session)

            repository.save(journal)
            repository.save(journal)

            assert repository.count() == 1
    finally:
        engine.dispose()


def test_repository_lists_by_dataset_and_selected_candidate() -> None:
    engine, factory = build_repository()
    closed = CandidateJournalBuilder.from_lifecycle(
        build_closed_lifecycle(),
    )
    no_position = CandidateJournalBuilder.from_lifecycle(
        build_no_position_lifecycle(),
    )

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateJournalRepository(session)
            repository.save(no_position)
            repository.save(closed)

            by_dataset = repository.list_by_dataset(
                dataset_id=closed.dataset_id,
                limit=10,
                offset=0,
            )
            assert set(by_dataset) == {closed, no_position}

            assert closed.selected_candidate_id is not None
            by_candidate = repository.list_by_selected_candidate(
                candidate_id=closed.selected_candidate_id,
                limit=10,
                offset=0,
            )
            assert by_candidate == (closed,)

            assert repository.list_page(limit=1, offset=0) == (closed,)
    finally:
        engine.dispose()


def test_repository_rejects_invalid_pagination() -> None:
    engine, factory = build_repository()

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateJournalRepository(session)

            for limit, offset in ((0, 0), (10, -1)):
                try:
                    repository.list_page(
                        limit=limit,
                        offset=offset,
                    )
                except ValueError:
                    pass
                else:
                    raise AssertionError("invalid pagination must fail")
    finally:
        engine.dispose()
