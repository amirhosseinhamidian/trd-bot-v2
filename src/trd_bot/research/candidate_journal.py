import hashlib
import json
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.research.candidates import normalize_candidate_timestamp
from trd_bot.research.dataset_replay import CandidateReplayStatus
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleResult,
    CandidateReplayLifecycleStatus,
)
from trd_bot.research.position_monitoring import CandidateExitReason


def build_candidate_journal_id(
    lifecycle: CandidateReplayLifecycleResult,
) -> str:
    """Build a deterministic journal identity from the complete lifecycle payload."""

    serialized = json.dumps(
        lifecycle.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    return f"journal-{digest[:16]}"


class CandidateJournalEntry(BaseModel):
    """Immutable audit record for one complete offline candidate lifecycle."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    journal_id: str = Field(pattern=r"^journal-[a-f0-9]{16}$")
    schema_version: int = Field(default=1, ge=1)

    recorded_at: datetime
    evaluated_at: datetime
    status: CandidateReplayLifecycleStatus

    dataset_id: str = Field(min_length=1, max_length=100)
    portfolio_id: str = Field(pattern=r"^portfolio-[a-f0-9]{16}$")

    attempted_candidate_ids: tuple[str, ...]
    skipped_candidate_ids: tuple[str, ...]

    selected_candidate_id: str | None = Field(
        default=None,
        pattern=r"^candidate-[a-f0-9]{16}$",
    )
    signal_id: str | None = Field(
        default=None,
        pattern=r"^signal-[a-f0-9]{16}$",
    )
    experiment_id: str | None = Field(
        default=None,
        pattern=r"^experiment-[a-f0-9]{16}$",
    )
    position_id: str | None = Field(
        default=None,
        pattern=r"^position-[a-f0-9]{16}$",
    )
    exit_reason: CandidateExitReason | None = None

    lifecycle: CandidateReplayLifecycleResult

    @field_validator(
        "recorded_at",
        "evaluated_at",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        lifecycle = self.lifecycle
        replay = lifecycle.replay

        expected_journal_id = build_candidate_journal_id(lifecycle)
        if self.journal_id != expected_journal_id:
            raise ValueError("journal ID does not match lifecycle payload")

        if self.status is not lifecycle.status:
            raise ValueError("journal status does not match lifecycle")

        if self.dataset_id != lifecycle.dataset_id:
            raise ValueError("journal dataset does not match lifecycle")

        if self.portfolio_id != lifecycle.portfolio.portfolio_id:
            raise ValueError("journal portfolio does not match lifecycle")

        if self.evaluated_at != lifecycle.evaluated_at:
            raise ValueError("journal evaluation time does not match lifecycle")

        expected_attempted = tuple(
            attempt.ranking_entry.candidate.candidate_id for attempt in replay.attempted
        )
        if self.attempted_candidate_ids != expected_attempted:
            raise ValueError("journal attempted candidates do not match replay")

        if self.skipped_candidate_ids != replay.skipped_candidate_ids:
            raise ValueError("journal skipped candidates do not match replay")

        if self.selected_candidate_id != replay.selected_candidate_id:
            raise ValueError("journal selection does not match replay")

        if self.status is CandidateReplayLifecycleStatus.NO_POSITION:
            self._validate_no_position()
            return self

        self._validate_closed()
        return self

    def _validate_no_position(self) -> None:
        if self.lifecycle.monitoring is not None:
            raise ValueError("no-position journal cannot contain monitoring")

        if any(
            value is not None
            for value in (
                self.signal_id,
                self.experiment_id,
                self.position_id,
                self.exit_reason,
            )
        ):
            raise ValueError("no-position journal cannot contain selected lineage")

        if self.recorded_at != self.evaluated_at:
            raise ValueError("no-position journal must be recorded at evaluation time")

    def _validate_closed(self) -> None:
        monitoring = self.lifecycle.monitoring
        if monitoring is None:
            raise ValueError("closed journal requires monitoring")

        opened = tuple(
            attempt
            for attempt in self.lifecycle.replay.attempted
            if attempt.status is CandidateReplayStatus.OPENED
        )
        if len(opened) != 1:
            raise ValueError("closed journal requires exactly one opened replay")

        simulation = opened[0].simulation
        if simulation is None:
            raise ValueError("opened replay requires simulation details")

        candidate = simulation.selected_candidate

        if self.signal_id != candidate.signal_id:
            raise ValueError("journal signal does not match selected candidate")

        if self.experiment_id != candidate.experiment_id:
            raise ValueError("journal experiment does not match selected candidate")

        if self.position_id != monitoring.position_id:
            raise ValueError("journal position does not match monitoring")

        if self.exit_reason is not monitoring.trigger.reason:
            raise ValueError("journal exit reason does not match monitoring")

        if self.recorded_at != monitoring.closed_at:
            raise ValueError("closed journal must be recorded at position close")


class CandidateJournalBuilder:
    """Create immutable journal records from completed offline lifecycles."""

    @staticmethod
    def from_lifecycle(
        lifecycle: CandidateReplayLifecycleResult,
    ) -> CandidateJournalEntry:
        replay = lifecycle.replay
        attempted_candidate_ids = tuple(
            attempt.ranking_entry.candidate.candidate_id for attempt in replay.attempted
        )
        journal_id = build_candidate_journal_id(lifecycle)
        portfolio_id = lifecycle.portfolio.portfolio_id

        if lifecycle.status is CandidateReplayLifecycleStatus.NO_POSITION:
            return CandidateJournalEntry(
                journal_id=journal_id,
                recorded_at=lifecycle.evaluated_at,
                evaluated_at=lifecycle.evaluated_at,
                status=lifecycle.status,
                dataset_id=lifecycle.dataset_id,
                portfolio_id=portfolio_id,
                attempted_candidate_ids=attempted_candidate_ids,
                skipped_candidate_ids=replay.skipped_candidate_ids,
                selected_candidate_id=replay.selected_candidate_id,
                lifecycle=lifecycle,
            )

        monitoring = lifecycle.monitoring
        if monitoring is None:
            raise ValueError("closed lifecycle requires monitoring")

        opened = tuple(
            attempt
            for attempt in replay.attempted
            if attempt.status is CandidateReplayStatus.OPENED
        )
        if len(opened) != 1 or opened[0].simulation is None:
            raise ValueError("closed lifecycle requires one opened simulation")

        selected_candidate = opened[0].simulation.selected_candidate

        return CandidateJournalEntry(
            journal_id=journal_id,
            recorded_at=monitoring.closed_at,
            evaluated_at=lifecycle.evaluated_at,
            status=lifecycle.status,
            dataset_id=lifecycle.dataset_id,
            portfolio_id=portfolio_id,
            attempted_candidate_ids=attempted_candidate_ids,
            skipped_candidate_ids=replay.skipped_candidate_ids,
            selected_candidate_id=replay.selected_candidate_id,
            signal_id=selected_candidate.signal_id,
            experiment_id=selected_candidate.experiment_id,
            position_id=monitoring.position_id,
            exit_reason=monitoring.trigger.reason,
            lifecycle=lifecycle,
        )
