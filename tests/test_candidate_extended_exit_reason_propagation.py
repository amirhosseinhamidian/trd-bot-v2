from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from tests.test_candidate_journal import build_closed_lifecycle
from tests.test_candidate_replay_lifecycle import (
    EVALUATED_AT,
    lifecycle_dataset,
    ranked_entries,
    simulated_portfolio,
)
from trd_bot.db import (
    CandidateJournalRow,
    CandidateProjectionRow,
    DatabaseBase,
    SqlAlchemyCandidateJournalRepository,
    SqlAlchemyCandidateProjectionRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.research.candidate_journal import CandidateJournalBuilder
from trd_bot.research.candidate_projection import CandidateJournalProjectionReader
from trd_bot.research.candidate_simulation_runner import CandidateSimulationResult
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleResult,
    CandidateReplayLifecycleRunner,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.position_monitoring import (
    CandidateExitDirective,
    CandidateExitReason,
    CandidateExitTrigger,
    CandidatePositionMonitor,
    CandidatePositionMonitoringResult,
)


class RecordingPositionMonitor(CandidatePositionMonitor):
    def __init__(self) -> None:
        super().__init__()
        self.received_exit_directives: tuple[CandidateExitDirective, ...] = ()

    def run(
        self,
        *,
        simulation: CandidateSimulationResult,
        dataset: DatasetSnapshot,
        exit_directives: Sequence[CandidateExitDirective] = (),
    ) -> CandidatePositionMonitoringResult:
        self.received_exit_directives = tuple(exit_directives)
        return super().run(
            simulation=simulation,
            dataset=dataset,
        )


def test_lifecycle_forwards_exit_directives_to_position_monitor() -> None:
    dataset = lifecycle_dataset()
    monitor = RecordingPositionMonitor()
    directive = CandidateExitDirective(
        reason=CandidateExitReason.TREND_REVERSAL,
        occurred_at=datetime(2026, 8, 26, 23, tzinfo=UTC),
    )

    CandidateReplayLifecycleRunner(position_monitor=monitor).run(
        entries=ranked_entries(dataset_id=dataset.dataset_id),
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
        exit_directives=(directive,),
    )

    assert monitor.received_exit_directives == (directive,)


def lifecycle_with_exit_reason(
    reason: CandidateExitReason,
) -> CandidateReplayLifecycleResult:
    lifecycle = build_closed_lifecycle()
    monitoring = lifecycle.monitoring
    assert monitoring is not None

    trigger_payload = monitoring.trigger.model_dump()
    trigger_payload["reason"] = reason
    trigger_payload["target_label"] = None
    trigger = CandidateExitTrigger.model_validate(trigger_payload)

    monitoring_payload = monitoring.model_dump()
    monitoring_payload["trigger"] = trigger.model_dump()
    updated_monitoring = CandidatePositionMonitoringResult.model_validate(monitoring_payload)

    lifecycle_payload = lifecycle.model_dump()
    lifecycle_payload["monitoring"] = updated_monitoring.model_dump()

    return CandidateReplayLifecycleResult.model_validate(lifecycle_payload)


@pytest.mark.parametrize(
    "reason",
    (
        CandidateExitReason.TREND_REVERSAL,
        CandidateExitReason.PORTFOLIO_RISK,
        CandidateExitReason.DATA_UNRELIABLE,
    ),
)
def test_extended_exit_reason_round_trips_journal_projection_and_storage(
    reason: CandidateExitReason,
) -> None:
    lifecycle = lifecycle_with_exit_reason(reason)
    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)

    assert journal.exit_reason is reason
    assert journal.selected_candidate_id is not None

    projections = CandidateJournalProjectionReader.build((journal,))
    projection = CandidateJournalProjectionReader.get(
        projections,
        journal.selected_candidate_id,
    )
    assert projection is not None
    assert projection.latest.exit_reason is reason

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with factory() as session:
            journal_repository = SqlAlchemyCandidateJournalRepository(session)
            projection_repository = SqlAlchemyCandidateProjectionRepository(session)

            journal_repository.save(journal)
            projection_repository.save(projection)

            journal_row = session.scalar(
                select(CandidateJournalRow).where(
                    CandidateJournalRow.journal_id == journal.journal_id
                )
            )
            projection_row = session.scalar(
                select(CandidateProjectionRow).where(
                    CandidateProjectionRow.candidate_id == projection.candidate.candidate_id
                )
            )

            assert journal_row is not None
            assert projection_row is not None
            assert journal_row.exit_reason == reason.value
            assert projection_row.exit_reason == reason.value

            stored_journal = journal_repository.get(journal.journal_id)
            stored_projection = projection_repository.get(projection.candidate.candidate_id)

            assert stored_journal is not None
            assert stored_journal.exit_reason is reason
            assert stored_projection is not None
            assert stored_projection.latest.exit_reason is reason
    finally:
        engine.dispose()
