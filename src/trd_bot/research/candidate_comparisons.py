from collections.abc import Sequence
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.research.candidate_projection import (
    CandidateJournalOccurrence,
    CandidateProjection,
)

CandidateId = Annotated[
    str,
    Field(pattern=r"^candidate-[a-f0-9]{16}$"),
]


class CandidateComparisonRequest(BaseModel):
    """Candidate identities selected from one persisted decision cohort."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_ids: tuple[CandidateId, ...] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def candidate_ids_must_be_unique(self) -> Self:
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        return self


class CandidateComparisonEntry(BaseModel):
    """One persisted occurrence in a side-by-side candidate comparison."""

    model_config = ConfigDict(frozen=True)

    comparison_position: int = Field(ge=1, le=4)
    occurrence: CandidateJournalOccurrence


class CandidateComparisonResult(BaseModel):
    """Rank-ordered candidates from one immutable journal decision cohort."""

    model_config = ConfigDict(frozen=True)

    journal_id: str = Field(pattern=r"^journal-[a-f0-9]{16}$")
    compared_candidates: int = Field(ge=2, le=4)
    entries: tuple[CandidateComparisonEntry, ...]
    interpretation: Literal["historical_research_only"] = "historical_research_only"

    @model_validator(mode="after")
    def validate_entries(self) -> Self:
        if len(self.entries) != self.compared_candidates:
            raise ValueError("candidate comparison count does not match entries")
        if tuple(item.comparison_position for item in self.entries) != tuple(
            range(1, self.compared_candidates + 1)
        ):
            raise ValueError("candidate comparison positions must be contiguous")
        if any(item.occurrence.journal_id != self.journal_id for item in self.entries):
            raise ValueError("candidate comparison entries must share the result journal")
        return self


class CandidateComparator:
    """Compare persisted latest occurrences without mixing ranking cohorts."""

    def compare(
        self,
        projections: Sequence[CandidateProjection],
    ) -> CandidateComparisonResult:
        selected = tuple(projections)
        self._validate(selected)

        ordered = tuple(
            sorted(
                (projection.latest for projection in selected),
                key=lambda occurrence: (
                    occurrence.rank,
                    occurrence.candidate.candidate_id,
                ),
            )
        )

        return CandidateComparisonResult(
            journal_id=ordered[0].journal_id,
            compared_candidates=len(ordered),
            entries=tuple(
                CandidateComparisonEntry(
                    comparison_position=position,
                    occurrence=occurrence,
                )
                for position, occurrence in enumerate(ordered, start=1)
            ),
        )

    @staticmethod
    def _validate(projections: tuple[CandidateProjection, ...]) -> None:
        if len(projections) < 2:
            raise ValueError("at least two candidates are required")
        if len(projections) > 4:
            raise ValueError("at most four candidates can be compared")

        candidate_ids = {projection.candidate.candidate_id for projection in projections}
        if len(candidate_ids) != len(projections):
            raise ValueError("candidate IDs must be unique")

        journal_ids = {projection.latest.journal_id for projection in projections}
        if len(journal_ids) != 1:
            raise ValueError("candidates must use the same latest journal")
