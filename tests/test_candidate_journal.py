import pytest
from pydantic import ValidationError

from tests.test_candidate_replay_lifecycle import (
    EVALUATED_AT,
    candidate,
    lifecycle_dataset,
    ranked_entries,
    simulated_portfolio,
)
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
    build_candidate_journal_id,
)
from trd_bot.research.candidate_ranking import CandidateRanker
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleRunner,
    CandidateReplayLifecycleStatus,
)
from trd_bot.research.position_monitoring import CandidateExitReason


def build_closed_lifecycle():
    dataset = lifecycle_dataset()

    return CandidateReplayLifecycleRunner().run(
        entries=ranked_entries(
            dataset_id=dataset.dataset_id,
        ),
        portfolio=simulated_portfolio(
            dataset_id=dataset.dataset_id,
        ),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )


def build_no_position_lifecycle():
    dataset = lifecycle_dataset()
    ranked = (
        CandidateRanker()
        .rank(
            candidates=(
                candidate(
                    dataset_id=dataset.dataset_id,
                    experiment_id="experiment-4444444444444444",
                    confidence="0.90",
                    entry_low="130",
                    entry_high="132",
                    invalidation="127",
                    target="142",
                ),
            ),
            at=EVALUATED_AT,
        )
        .entries
    )

    return CandidateReplayLifecycleRunner().run(
        entries=ranked,
        portfolio=simulated_portfolio(
            dataset_id=dataset.dataset_id,
        ),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )


def test_closed_lifecycle_builds_complete_selected_lineage() -> None:
    lifecycle = build_closed_lifecycle()

    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)

    assert journal.status is CandidateReplayLifecycleStatus.CLOSED
    assert journal.journal_id == build_candidate_journal_id(lifecycle)
    assert journal.selected_candidate_id == lifecycle.replay.selected_candidate_id
    assert journal.signal_id is not None
    assert journal.experiment_id is not None
    assert lifecycle.monitoring is not None
    assert journal.position_id == lifecycle.monitoring.position_id
    assert journal.exit_reason is CandidateExitReason.TARGET
    assert journal.recorded_at == lifecycle.monitoring.closed_at
    assert journal.lifecycle == lifecycle


def test_journal_id_is_deterministic_for_same_lifecycle() -> None:
    lifecycle = build_closed_lifecycle()

    first = CandidateJournalBuilder.from_lifecycle(lifecycle)
    second = CandidateJournalBuilder.from_lifecycle(lifecycle)

    assert first.journal_id == second.journal_id
    assert first == second


def test_no_position_lifecycle_keeps_attempts_without_selected_lineage() -> None:
    lifecycle = build_no_position_lifecycle()

    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)

    assert journal.status is CandidateReplayLifecycleStatus.NO_POSITION
    assert len(journal.attempted_candidate_ids) == 1
    assert journal.selected_candidate_id is None
    assert journal.signal_id is None
    assert journal.experiment_id is None
    assert journal.position_id is None
    assert journal.exit_reason is None
    assert journal.recorded_at == EVALUATED_AT


def test_journal_rejects_tampered_selected_candidate_lineage() -> None:
    lifecycle = build_closed_lifecycle()
    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)
    payload = journal.model_dump(mode="python")
    payload["selected_candidate_id"] = "candidate-0000000000000000"

    with pytest.raises(
        ValidationError,
        match="journal selection does not match replay",
    ):
        CandidateJournalEntry.model_validate(payload)
