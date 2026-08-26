from datetime import timedelta

from sqlalchemy import select

from tests.test_candidate_journal import (
    build_closed_lifecycle,
    build_no_position_lifecycle,
)
from trd_bot.db import (
    CandidateProjectionRow,
    DatabaseBase,
    SqlAlchemyCandidateProjectionRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.research.candidate_journal import CandidateJournalBuilder
from trd_bot.research.candidate_projection import (
    CandidateJournalOccurrence,
    CandidateJournalProjectionReader,
    CandidateProjection,
)


def build_storage():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    return engine, factory


def build_projections() -> tuple[CandidateProjection, ...]:
    closed = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    no_position = CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle())
    return CandidateJournalProjectionReader.build((closed, no_position))


def test_repository_round_trips_projection_and_query_columns() -> None:
    engine, factory = build_storage()
    projection = build_projections()[0]

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateProjectionRepository(session)

            assert repository.save(projection) == projection
            assert repository.get(projection.candidate.candidate_id) == projection

            row = session.scalar(
                select(CandidateProjectionRow).where(
                    CandidateProjectionRow.candidate_id == projection.candidate.candidate_id
                )
            )
            assert row is not None
            assert row.dataset_id == projection.candidate.dataset_id
            assert row.latest_journal_id == projection.latest.journal_id
            assert row.occurrence_count == len(projection.history)
            assert row.latest_rank == projection.latest.rank
            assert row.selected == int(projection.latest.selected)
    finally:
        engine.dispose()


def test_repository_updates_existing_projection_history() -> None:
    engine, factory = build_storage()
    projection = build_projections()[0]
    previous = projection.latest
    newer = CandidateJournalOccurrence(
        **previous.model_dump(
            exclude={
                "journal_id",
                "recorded_at",
            }
        ),
        journal_id="journal-ffffffffffffffff",
        recorded_at=previous.recorded_at + timedelta(minutes=1),
    )
    updated = CandidateProjection(
        candidate=newer.candidate,
        latest=newer,
        history=(newer, *projection.history),
    )

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateProjectionRepository(session)

            repository.save(projection)
            repository.save(updated)

            stored = repository.get(projection.candidate.candidate_id)
            assert stored == updated
            assert stored is not None
            assert len(stored.history) == len(projection.history) + 1
            assert repository.count() == 1
    finally:
        engine.dispose()


def test_repository_lists_newest_projection_first() -> None:
    engine, factory = build_storage()
    projections = build_projections()

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateProjectionRepository(session)
            for projection in projections:
                repository.save(projection)

            items = repository.list_page(
                limit=100,
                offset=0,
            )
            expected = tuple(
                sorted(
                    projections,
                    key=lambda item: (
                        item.latest.recorded_at,
                        item.latest.journal_id,
                        item.candidate.candidate_id,
                    ),
                    reverse=True,
                )
            )

            assert items == expected
            assert repository.count() == len(projections)
    finally:
        engine.dispose()


def test_repository_supports_external_transaction_rollback() -> None:
    engine, factory = build_storage()
    projection = build_projections()[0]

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateProjectionRepository(session)

            repository.save(projection, commit=False)
            assert repository.count() == 1

            session.rollback()

            assert repository.count() == 0
    finally:
        engine.dispose()


def test_repository_rejects_invalid_pagination() -> None:
    engine, factory = build_storage()

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateProjectionRepository(session)

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
