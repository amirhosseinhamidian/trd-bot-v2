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
    CandidateJournalOccurrence,
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
    assert all(item["latest_rank"] >= 1 for item in payload["items"])
    assert all(item["latest_ranking_score"] for item in payload["items"])
    assert all(item["latest_decision_evidence"] for item in payload["items"])


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
    assert payload["latest"]["decision_evidence"]["evidence_version"] == (
        "candidate-decision-evidence-v1"
    )
    assert payload["rank_history"] == [
        {
            "journal_id": entries[0].journal_id,
            "recorded_at": payload["latest"]["recorded_at"],
            "rank": payload["latest"]["rank"],
            "ranking_score": payload["latest"]["ranking_score"],
            "selected": True,
            "evidence_available": True,
        }
    ]
    assert payload["decision_lineage"]["lineage_version"] == ("candidate-decision-lineage-v1")
    nodes = {node["kind"]: node for node in payload["decision_lineage"]["nodes"]}
    assert nodes["dataset"]["resource_id"] == payload["candidate"]["dataset_id"]
    assert nodes["experiment"]["resource_id"] == payload["candidate"]["experiment_id"]
    assert nodes["signal"]["resource_id"] == payload["candidate"]["signal_id"]
    assert nodes["position"]["resource_id"] == entries[0].position_id
    assert nodes["exit"]["outcome"] == "target"


def test_compare_candidate_projections_returns_same_journal_breakdowns() -> None:
    client, entries = build_client()
    cohort_ids = entries[0].attempted_candidate_ids + entries[0].skipped_candidate_ids
    assert len(cohort_ids) >= 2

    response = client.post(
        "/research/candidates/compare",
        json={"candidate_ids": list(cohort_ids[:2])},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["journal_id"] == entries[0].journal_id
    assert payload["compared_candidates"] == 2
    assert [item["occurrence"]["rank"] for item in payload["entries"]] == sorted(
        item["occurrence"]["rank"] for item in payload["entries"]
    )
    assert all(item["occurrence"]["decision_evidence"] is not None for item in payload["entries"])


def test_compare_candidate_projections_rejects_mixed_latest_journals() -> None:
    client, entries = build_client()
    first_id = (entries[0].attempted_candidate_ids + entries[0].skipped_candidate_ids)[0]
    second_id = entries[1].attempted_candidate_ids[0]

    response = client.post(
        "/research/candidates/compare",
        json={"candidate_ids": [first_id, second_id]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "candidates must use the same latest journal"


def test_compare_candidate_projections_reports_missing_ids() -> None:
    client, entries = build_client()
    candidate_id = entries[0].attempted_candidate_ids[0]
    missing_id = "candidate-0000000000000000"

    response = client.post(
        "/research/candidates/compare",
        json={"candidate_ids": [candidate_id, missing_id]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "message": "candidate projections not found",
        "candidate_ids": [missing_id],
    }


def test_compare_candidate_projections_rejects_duplicate_ids() -> None:
    client, entries = build_client()
    candidate_id = entries[0].attempted_candidate_ids[0]

    response = client.post(
        "/research/candidates/compare",
        json={"candidate_ids": [candidate_id, candidate_id]},
    )

    assert response.status_code == 422


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


def test_candidate_api_marks_legacy_missing_breakdown_without_fabricating_evidence() -> None:
    journal = CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle())
    projection = CandidateJournalProjectionReader.build((journal,))[0]
    occurrence_payload = projection.latest.model_dump(mode="python")
    occurrence_payload.pop("decision_evidence")
    legacy_occurrence = CandidateJournalOccurrence.model_validate(occurrence_payload)
    legacy_projection = CandidateProjection(
        candidate=legacy_occurrence.candidate,
        latest=legacy_occurrence,
        history=(legacy_occurrence,),
    )
    repository = InMemoryCandidateProjectionRepository((legacy_projection,))
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_candidate_projection_repository] = lambda: repository
    client = TestClient(application)

    response = client.get("/research/candidates")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["latest_rank"] == legacy_occurrence.rank
    assert item["latest_ranking_score"] == str(legacy_occurrence.ranking_score)
    assert item["latest_decision_evidence"] is None

    detail_response = client.get(f"/research/candidates/{legacy_occurrence.candidate.candidate_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    risk_node = next(node for node in detail["decision_lineage"]["nodes"] if node["kind"] == "risk")
    assert legacy_occurrence.risk_decision is not None
    assert risk_node["status"] == "unavailable"
    assert risk_node["outcome"] == legacy_occurrence.risk_decision.value
    assert detail["rank_history"][0]["evidence_available"] is False
