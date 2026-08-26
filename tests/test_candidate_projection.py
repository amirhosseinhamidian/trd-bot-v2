from tests.test_candidate_journal import (
    build_closed_lifecycle,
    build_no_position_lifecycle,
)
from trd_bot.research.candidate_journal import CandidateJournalBuilder
from trd_bot.research.candidate_projection import CandidateJournalProjectionReader
from trd_bot.research.candidates import CandidateStatus
from trd_bot.research.dataset_replay import CandidateReplayStatus


def test_projection_builds_selected_and_unselected_candidate_views() -> None:
    closed = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    no_position = CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle())

    projections = CandidateJournalProjectionReader.build((closed, no_position))

    assert len(projections) >= 2

    selected = CandidateJournalProjectionReader.get(
        projections,
        closed.selected_candidate_id,
    )
    assert selected is not None
    assert selected.candidate.status is CandidateStatus.SELECTED
    assert selected.latest.selected is True
    assert selected.latest.replay_status is CandidateReplayStatus.OPENED
    assert selected.latest.position_id == closed.position_id
    assert selected.latest.exit_reason == closed.exit_reason

    unselected_id = no_position.attempted_candidate_ids[0]
    unselected = CandidateJournalProjectionReader.get(
        projections,
        unselected_id,
    )
    assert unselected is not None
    assert unselected.candidate.status is CandidateStatus.CANDIDATE
    assert unselected.latest.selected is False
    assert unselected.latest.position_id is None
    assert unselected.latest.exit_reason is None


def test_projection_returns_none_for_unknown_candidate() -> None:
    projections = CandidateJournalProjectionReader.build(())

    assert (
        CandidateJournalProjectionReader.get(
            projections,
            "candidate-0000000000000000",
        )
        is None
    )
