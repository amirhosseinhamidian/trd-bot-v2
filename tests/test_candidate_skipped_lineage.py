import hashlib
import json

from tests.test_candidate_dataset_replay_orchestration import (
    EVALUATED_AT,
    portfolio,
    ranked_entries,
    replay_dataset,
)
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    build_candidate_journal_id,
)
from trd_bot.research.candidate_ranking import CandidateRankingEntry
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleResult,
    CandidateReplayLifecycleRunner,
)
from trd_bot.research.dataset_replay_orchestration import (
    CandidateDatasetReplayOrchestrator,
    CandidateReplayBatchResult,
    CandidateReplaySkipReason,
)


def build_skipping_lifecycle() -> tuple[
    CandidateReplayLifecycleResult,
    tuple[CandidateRankingEntry, ...],
]:
    dataset = replay_dataset()
    entries = ranked_entries(dataset_id=dataset.dataset_id)

    lifecycle = CandidateReplayLifecycleRunner().run(
        entries=entries,
        portfolio=portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    return lifecycle, entries


def test_orchestrator_preserves_skipped_candidate_snapshot_and_reason() -> None:
    dataset = replay_dataset()
    entries = ranked_entries(dataset_id=dataset.dataset_id)

    result = CandidateDatasetReplayOrchestrator().run(
        entries=entries,
        portfolio=portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert result.skipped_count == 1
    assert len(result.skipped) == 1
    assert result.skipped[0].ranking_entry == entries[2]
    assert result.skipped[0].reason is CandidateReplaySkipReason.POSITION_OPENED
    assert result.skipped_candidate_ids == (result.skipped[0].ranking_entry.candidate.candidate_id,)


def test_skipped_snapshot_is_independent_of_input_order() -> None:
    dataset = replay_dataset()
    entries = ranked_entries(dataset_id=dataset.dataset_id)
    initial_portfolio = portfolio(dataset_id=dataset.dataset_id)

    forward = CandidateDatasetReplayOrchestrator().run(
        entries=entries,
        portfolio=initial_portfolio,
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )
    reverse = CandidateDatasetReplayOrchestrator().run(
        entries=tuple(reversed(entries)),
        portfolio=initial_portfolio,
        dataset=dataset,
        evaluated_at=EVALUATED_AT,
    )

    assert forward.skipped == reverse.skipped


def test_closed_journal_retains_skipped_candidate_snapshot() -> None:
    lifecycle, entries = build_skipping_lifecycle()

    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)

    assert journal.skipped_candidate_ids == (entries[2].candidate.candidate_id,)
    assert len(journal.lifecycle.replay.skipped) == 1
    assert journal.lifecycle.replay.skipped[0].ranking_entry == entries[2]


def test_legacy_batch_without_skipped_snapshots_remains_valid() -> None:
    lifecycle, _ = build_skipping_lifecycle()
    payload = lifecycle.replay.model_dump(mode="python")
    payload.pop("skipped")

    legacy = CandidateReplayBatchResult.model_validate(payload)

    assert legacy.skipped == ()
    assert legacy.skipped_candidate_ids == lifecycle.replay.skipped_candidate_ids
    assert legacy.skipped_count == lifecycle.replay.skipped_count


def test_legacy_journal_identity_ignores_empty_skipped_default() -> None:
    lifecycle, _ = build_skipping_lifecycle()
    replay_payload = lifecycle.replay.model_dump(mode="python")
    replay_payload.pop("skipped")
    legacy_replay = CandidateReplayBatchResult.model_validate(replay_payload)
    legacy_lifecycle = lifecycle.model_copy(update={"replay": legacy_replay})

    expected_payload = legacy_lifecycle.model_dump(mode="json")
    expected_payload["replay"].pop("skipped", None)
    serialized = json.dumps(
        expected_payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected_id = f"journal-{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:16]}"

    assert build_candidate_journal_id(legacy_lifecycle) == expected_id
