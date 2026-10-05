import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.test_candidate_application import build_execution_parameters
from tests.test_experiment_replay import build_experiment
from trd_bot.db import (
    DatabaseBase,
    create_database_engine,
    create_session_factory,
)
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
from trd_bot.research.candidate_application import (
    CandidateApplicationOrchestrator,
)
from trd_bot.research.candidate_journal import CandidateJournalEntry
from trd_bot.research.candidate_projection import (
    CandidateJournalProjectionReader,
)
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleResult,
)


def build_storage() -> tuple[Engine, sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    return engine, create_session_factory(engine)


def test_retrying_candidate_application_is_persistence_idempotent() -> None:
    engine, factory = build_storage()

    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()

    try:
        with factory() as session:
            first = CandidateApplicationOrchestrator(
                recorder=SqlAlchemyCandidateLifecycleRecorder(session),
            ).run(
                experiment=experiment,
                dataset=dataset,
                parameters=parameters,
            )

        with factory() as session:
            second = CandidateApplicationOrchestrator(
                recorder=SqlAlchemyCandidateLifecycleRecorder(session),
            ).run(
                experiment=experiment,
                dataset=dataset,
                parameters=parameters,
            )

            assert first.lifecycle is not None
            assert second.lifecycle is not None
            assert first.journal is not None
            assert second.journal is not None

            # Application replay itself must be deterministic.
            assert second.lifecycle == first.lifecycle
            assert second.journal == first.journal

            assert second.lifecycle.portfolio.portfolio_id == first.lifecycle.portfolio.portfolio_id
            assert second.journal.journal_id == first.journal.journal_id

            # Retrying must not create duplicate persistence artifacts.
            journals = SqlAlchemyCandidateJournalRepository(session)
            portfolios = SqlAlchemySimulatedPortfolioRepository(session)
            projections = SqlAlchemyCandidateProjectionRepository(session)

            assert journals.count() == 1
            assert portfolios.count() == 1

            expected_projections = CandidateJournalProjectionReader.build((first.journal,))

            assert projections.count() == len(expected_projections)
            assert projections.list_page(limit=100, offset=0) == expected_projections
    finally:
        engine.dispose()


class CommitThenFailRecorder:
    """Simulate a process failure immediately after a successful DB commit."""

    def __init__(self, session: Session) -> None:
        self._delegate = SqlAlchemyCandidateLifecycleRecorder(session)
        self.lifecycle: CandidateReplayLifecycleResult | None = None
        self.committed_journal: CandidateJournalEntry | None = None

    def record(
        self,
        lifecycle: CandidateReplayLifecycleResult,
    ) -> CandidateJournalEntry:
        self.lifecycle = lifecycle
        self.committed_journal = self._delegate.record(lifecycle)
        raise RuntimeError("synthetic post-commit failure")


def test_retry_after_post_commit_failure_does_not_duplicate_artifacts() -> None:
    engine, factory = build_storage()

    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()

    try:
        with factory() as session:
            failing_recorder = CommitThenFailRecorder(session)

            with pytest.raises(
                RuntimeError,
                match="synthetic post-commit failure",
            ):
                CandidateApplicationOrchestrator(
                    recorder=failing_recorder,
                ).run(
                    experiment=experiment,
                    dataset=dataset,
                    parameters=parameters,
                )

            assert failing_recorder.lifecycle is not None
            assert failing_recorder.committed_journal is not None

            # Commit already happened even though the caller observed failure.
            assert SqlAlchemyCandidateJournalRepository(session).count() == 1
            assert SqlAlchemySimulatedPortfolioRepository(session).count() == 1

        # Simulate worker retry in a fresh DB session.
        with factory() as session:
            retried = CandidateApplicationOrchestrator(
                recorder=SqlAlchemyCandidateLifecycleRecorder(session),
            ).run(
                experiment=experiment,
                dataset=dataset,
                parameters=parameters,
            )

            assert retried.lifecycle == failing_recorder.lifecycle
            assert retried.journal == failing_recorder.committed_journal

            journals = SqlAlchemyCandidateJournalRepository(session)
            portfolios = SqlAlchemySimulatedPortfolioRepository(session)
            projections = SqlAlchemyCandidateProjectionRepository(session)

            assert journals.count() == 1
            assert portfolios.count() == 1

            assert failing_recorder.committed_journal is not None

            expected_projections = CandidateJournalProjectionReader.build(
                (failing_recorder.committed_journal,)
            )

            assert projections.count() == len(expected_projections)
            assert projections.list_page(limit=100, offset=0) == expected_projections
    finally:
        engine.dispose()


def test_retry_after_pre_commit_failure_recovers_without_partial_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = build_storage()

    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()

    try:
        with factory() as session:
            failing_recorder = SqlAlchemyCandidateLifecycleRecorder(session)

            def fail_projection_refresh() -> None:
                raise RuntimeError("synthetic pre-commit failure")

            monkeypatch.setattr(
                failing_recorder,
                "_refresh_candidate_projections",
                fail_projection_refresh,
            )

            with pytest.raises(
                RuntimeError,
                match="synthetic pre-commit failure",
            ):
                CandidateApplicationOrchestrator(
                    recorder=failing_recorder,
                ).run(
                    experiment=experiment,
                    dataset=dataset,
                    parameters=parameters,
                )

            # Portfolio and journal were flushed, but transaction must be rolled back.
            assert SqlAlchemyCandidateJournalRepository(session).count() == 0
            assert SqlAlchemySimulatedPortfolioRepository(session).count() == 0
            assert SqlAlchemyCandidateProjectionRepository(session).count() == 0

        # Retry in a new session must succeed from a clean persistence state.
        with factory() as session:
            retried = CandidateApplicationOrchestrator(
                recorder=SqlAlchemyCandidateLifecycleRecorder(session),
            ).run(
                experiment=experiment,
                dataset=dataset,
                parameters=parameters,
            )

            assert retried.lifecycle is not None
            assert retried.journal is not None

            journals = SqlAlchemyCandidateJournalRepository(session)
            portfolios = SqlAlchemySimulatedPortfolioRepository(session)
            projections = SqlAlchemyCandidateProjectionRepository(session)

            assert journals.count() == 1
            assert portfolios.count() == 1

            expected_projections = CandidateJournalProjectionReader.build((retried.journal,))

            assert projections.count() == len(expected_projections)
            assert projections.list_page(limit=100, offset=0) == expected_projections
    finally:
        engine.dispose()
