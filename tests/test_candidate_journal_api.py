from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_candidate_journal import (
    build_closed_lifecycle,
    build_no_position_lifecycle,
)
from trd_bot.api.dependencies import get_candidate_journal_repository
from trd_bot.api.routes.journals import router
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
)


class InMemoryCandidateJournalRepository:
    def __init__(
        self,
        entries: tuple[CandidateJournalEntry, ...],
    ) -> None:
        self._entries = entries

    def get(self, journal_id: str) -> CandidateJournalEntry | None:
        return next(
            (entry for entry in self._entries if entry.journal_id == journal_id),
            None,
        )

    def count(self) -> int:
        return len(self._entries)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[CandidateJournalEntry, ...]:
        return self._entries[offset : offset + limit]


def build_client() -> tuple[
    TestClient,
    tuple[CandidateJournalEntry, ...],
]:
    closed = CandidateJournalBuilder.from_lifecycle(
        build_closed_lifecycle(),
    )
    no_position = CandidateJournalBuilder.from_lifecycle(
        build_no_position_lifecycle(),
    )
    entries = (
        closed,
        no_position,
    )
    repository = InMemoryCandidateJournalRepository(entries)

    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_candidate_journal_repository] = lambda: repository

    return TestClient(application), entries


def test_list_candidate_journals_returns_lightweight_summaries() -> None:
    client, entries = build_client()

    response = client.get("/research/journals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["count"] == 2
    assert payload["items"][0]["journal_id"] == entries[0].journal_id
    assert payload["items"][0]["attempted_count"] == len(entries[0].attempted_candidate_ids)
    assert "lifecycle" not in payload["items"][0]


def test_list_candidate_journals_supports_pagination() -> None:
    client, entries = build_client()

    response = client.get(
        "/research/journals",
        params={
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["count"] == 1
    assert payload["has_next"] is False
    assert payload["has_previous"] is True
    assert payload["items"][0]["journal_id"] == entries[1].journal_id


def test_get_candidate_journal_returns_complete_lifecycle() -> None:
    client, entries = build_client()

    response = client.get(f"/research/journals/{entries[0].journal_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["journal_id"] == entries[0].journal_id
    assert payload["selected_candidate_id"] == entries[0].selected_candidate_id
    assert payload["position_id"] == entries[0].position_id
    assert payload["lifecycle"]["dataset_id"] == entries[0].dataset_id


def test_get_candidate_journal_returns_404_for_unknown_id() -> None:
    client, _ = build_client()

    response = client.get("/research/journals/journal-0000000000000000")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "candidate journal not found",
    }


def test_list_candidate_journals_rejects_invalid_pagination() -> None:
    client, _ = build_client()

    response = client.get(
        "/research/journals",
        params={"limit": 0},
    )

    assert response.status_code == 422
