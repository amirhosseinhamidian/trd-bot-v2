from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.test_candidate_projection_repository import build_storage
from tests.test_candidate_skipped_lineage import build_skipping_lifecycle
from trd_bot.api.dependencies import get_candidate_projection_repository
from trd_bot.api.routes.candidates import router
from trd_bot.db import CandidateProjectionRow, SqlAlchemyCandidateProjectionRepository
from trd_bot.research.candidate_journal import CandidateJournalBuilder
from trd_bot.research.candidate_projection import (
    CandidateJournalProjectionReader,
    CandidateOccurrenceType,
    CandidateProjection,
)
from trd_bot.research.dataset_replay_orchestration import CandidateReplaySkipReason


def build_skipped_projection() -> CandidateProjection:
    lifecycle, entries = build_skipping_lifecycle()
    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)
    projections = CandidateJournalProjectionReader.build((journal,))
    skipped_candidate_id = entries[2].candidate.candidate_id
    projection = CandidateJournalProjectionReader.get(
        projections,
        skipped_candidate_id,
    )
    assert projection is not None
    return projection


def test_projection_catalogs_skipped_candidate_without_replay_or_risk_outcomes() -> None:
    projection = build_skipped_projection()

    assert projection.latest.occurrence_type is CandidateOccurrenceType.SKIPPED
    assert projection.latest.replay_status is None
    assert projection.latest.risk_decision is None
    assert projection.latest.skip_reason is CandidateReplaySkipReason.POSITION_OPENED
    assert projection.latest.selected is False
    assert projection.latest.position_id is None
    assert projection.latest.exit_reason is None


def test_projection_reader_catalogs_every_candidate_with_skipped_snapshot() -> None:
    lifecycle, entries = build_skipping_lifecycle()
    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)

    projections = CandidateJournalProjectionReader.build((journal,))

    assert {item.candidate.candidate_id for item in projections} == {
        entry.candidate.candidate_id for entry in entries
    }


def test_skipped_projection_round_trips_through_repository_with_null_outcomes() -> None:
    engine, factory = build_storage()
    projection = build_skipped_projection()

    try:
        with factory() as session:
            repository = SqlAlchemyCandidateProjectionRepository(session)
            repository.save(projection)

            stored = repository.get(projection.candidate.candidate_id)
            assert stored == projection

            row = session.scalar(
                select(CandidateProjectionRow).where(
                    CandidateProjectionRow.candidate_id == projection.candidate.candidate_id
                )
            )
            assert row is not None
            assert row.latest_replay_status is None
            assert row.latest_risk_decision is None
            assert row.selected == 0
    finally:
        engine.dispose()


class InMemoryProjectionRepository:
    def __init__(self, projections: tuple[CandidateProjection, ...]) -> None:
        self._projections = projections

    def get(self, candidate_id: str) -> CandidateProjection | None:
        return next(
            (
                projection
                for projection in self._projections
                if projection.candidate.candidate_id == candidate_id
            ),
            None,
        )

    def count(self) -> int:
        return len(self._projections)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[CandidateProjection, ...]:
        return self._projections[offset : offset + limit]


def test_candidate_api_exposes_skipped_semantics_without_fabricated_outcomes() -> None:
    lifecycle, entries = build_skipping_lifecycle()
    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)
    projections = CandidateJournalProjectionReader.build((journal,))
    repository = InMemoryProjectionRepository(projections)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_candidate_projection_repository] = lambda: repository
    client = TestClient(app)

    response = client.get("/research/candidates")
    assert response.status_code == 200

    payload = response.json()
    skipped_candidate_id = entries[2].candidate.candidate_id
    skipped = next(
        item for item in payload["items"] if item["candidate_id"] == skipped_candidate_id
    )

    assert skipped["latest_occurrence_type"] == "skipped"
    assert skipped["latest_replay_status"] is None
    assert skipped["latest_risk_decision"] is None
    assert skipped["latest_skip_reason"] == "position_opened"
    assert skipped["selected"] is False
