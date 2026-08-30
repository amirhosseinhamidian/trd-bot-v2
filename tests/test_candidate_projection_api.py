from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_candidate_journal import (
    build_closed_lifecycle,
    build_no_position_lifecycle,
)
from trd_bot.api.dependencies import get_candidate_projection_repository
from trd_bot.api.routes.candidates import router
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
)
from trd_bot.research.candidate_projection import (
    CandidateJournalProjectionReader,
    CandidateProjection,
)


class InMemoryCandidateProjectionRepository:
    def __init__(
        self,
        projections: tuple[CandidateProjection, ...],
    ) -> None:
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


def build_client() -> tuple[
    TestClient,
    tuple[CandidateJournalEntry, ...],
]:
    closed = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    no_position = CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle())
    entries = (closed, no_position)
    projections = CandidateJournalProjectionReader.build(entries)
    repository = InMemoryCandidateProjectionRepository(projections)

    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_candidate_projection_repository] = lambda: repository

    return TestClient(application), entries


def test_list_candidate_projections_returns_attempted_candidates() -> None:
    client, entries = build_client()

    response = client.get("/research/candidates")

    assert response.status_code == 200
    payload = response.json()
    expected_ids = {
        candidate_id for entry in entries for candidate_id in entry.attempted_candidate_ids
    }
    returned_ids = {item["candidate_id"] for item in payload["items"]}

    assert payload["total"] == len(expected_ids)
    assert returned_ids == expected_ids
    assert all("trade_plan" not in item for item in payload["items"])
    assert all(item["strategy_name"] for item in payload["items"])
    assert all(item["strategy_version"] for item in payload["items"])


def test_list_candidate_projections_uses_repository_pagination() -> None:
    client, _ = build_client()

    response = client.get(
        "/research/candidates",
        params={"limit": 1, "offset": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 2
    assert payload["count"] == 1
    assert payload["limit"] == 1
    assert payload["offset"] == 1


def test_get_candidate_projection_returns_complete_candidate_snapshot() -> None:
    client, entries = build_client()
    candidate_id = entries[0].selected_candidate_id
    assert candidate_id is not None

    response = client.get(f"/research/candidates/{candidate_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["candidate_id"] == candidate_id
    assert payload["candidate"]["status"] == "selected"
    assert payload["candidate"]["strategy_name"]
    assert payload["candidate"]["strategy_version"]
    assert payload["latest"]["candidate"]["strategy_name"] == payload["candidate"]["strategy_name"]
    assert (
        payload["latest"]["candidate"]["strategy_version"]
        == payload["candidate"]["strategy_version"]
    )
    assert payload["latest"]["selected"] is True
    assert payload["latest"]["position_id"] == entries[0].position_id


def test_candidate_lineage_returns_persisted_occurrences() -> None:
    client, entries = build_client()
    candidate_id = entries[0].selected_candidate_id
    assert candidate_id is not None

    response = client.get(
        f"/research/candidates/{candidate_id}/lineage",
        params={"limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["count"] == 1
    assert payload["items"][0]["candidate"]["candidate_id"] == candidate_id
    assert payload["items"][0]["candidate"]["strategy_name"]
    assert payload["items"][0]["candidate"]["strategy_version"]


def test_candidate_projection_returns_404_for_unknown_id() -> None:
    client, _ = build_client()

    response = client.get("/research/candidates/candidate-0000000000000000")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "candidate projection not found",
    }


def test_candidate_projection_rejects_invalid_pagination() -> None:
    client, _ = build_client()

    response = client.get(
        "/research/candidates",
        params={"limit": 0},
    )

    assert response.status_code == 422
