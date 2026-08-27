import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.test_candidate_journal import (
    build_closed_lifecycle,
    build_no_position_lifecycle,
)
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyCandidateJournalRepository,
    SqlAlchemyCandidateProjectionRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.maintenance import (
    CandidateProjectionRebuildSummary,
    main,
    rebuild_candidate_projections,
)
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
)
from trd_bot.research.candidate_projection import CandidateJournalProjectionReader


def build_storage() -> tuple[Engine, sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    return engine, factory


def seed_journals(
    factory: sessionmaker[Session],
) -> tuple[CandidateJournalEntry, ...]:
    journals = (
        CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle()),
        CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle()),
    )

    with factory() as session:
        repository = SqlAlchemyCandidateJournalRepository(session)
        for journal in journals:
            repository.save(journal)

    return journals


def test_rebuild_candidate_projections_reports_counts_and_backfills() -> None:
    engine, factory = build_storage()
    journals = seed_journals(factory)
    expected = CandidateJournalProjectionReader.build(journals)

    try:
        summary = rebuild_candidate_projections(factory)

        assert summary == CandidateProjectionRebuildSummary(
            journal_count=len(journals),
            projection_count=len(expected),
        )

        with factory() as session:
            repository = SqlAlchemyCandidateProjectionRepository(session)
            assert repository.list_page(limit=100, offset=0) == expected
    finally:
        engine.dispose()


def test_maintenance_main_runs_candidate_projection_rebuild(
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine, factory = build_storage()
    journals = seed_journals(factory)
    expected = CandidateJournalProjectionReader.build(journals)

    try:
        exit_code = main(
            ["rebuild-candidate-projections"],
            session_factory=factory,
        )

        assert exit_code == 0
        assert capsys.readouterr().out == (
            "candidate projection rebuild complete: "
            f"journals={len(journals)} "
            f"projections={len(expected)}\n"
        )
    finally:
        engine.dispose()
