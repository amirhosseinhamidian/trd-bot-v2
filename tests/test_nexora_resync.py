from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from trd_bot.integration.nexora.events import IntegrationEventEnvelope, build_event_envelope
from trd_bot.integration.nexora.resync import (
    REQUIRED_SNAPSHOT_RESOURCE_TYPES,
    FullResyncPublicationError,
    FullResyncStateMachine,
    resync_required_details,
)
from trd_bot.integration.nexora.snapshots import SnapshotItem, SnapshotRecord

NOW = datetime(2026, 11, 11, 11, tzinfo=UTC)
EVENT_CURSOR = f"evc_{'a' * 64}"
CHECKSUM = f"sha256:{'b' * 64}"


def snapshot_item(resource_type: str, *, resource_id: str | None = None) -> SnapshotItem:
    return SnapshotRecord(
        resource_type=resource_type,
        resource_id=resource_id or f"{resource_type}-1",
        resource_schema_version=f"trd-bot-{resource_type}-v1",
        observed_at=NOW,
        sort_key="0001",
        payload={"offline_only": True, "resource_type": resource_type},
    ).to_item(source_version="0.3.0")


def add_complete_snapshot(machine: FullResyncStateMachine) -> None:
    for resource_type in REQUIRED_SNAPSHOT_RESOURCE_TYPES:
        machine.add_snapshot_resource(resource_type, (snapshot_item(resource_type),))


def event(version: int, *, payload_value: str | None = None) -> IntegrationEventEnvelope:
    return build_event_envelope(
        event_type="decision.evaluated.v1",
        aggregate_type="decision_evaluation",
        aggregate_id="decision-1",
        aggregate_version=version,
        idempotency_key=f"decision-1-v{version}",
        payload_schema_version="trd-bot-decision-evaluated-event-v1",
        occurred_at=NOW + timedelta(minutes=version),
        published_at=NOW + timedelta(minutes=version, seconds=1),
        payload={"decision": payload_value or f"version-{version}", "offline_only": True},
    )


def test_full_resync_reconciles_all_snapshots_and_deduplicates_replay() -> None:
    machine = FullResyncStateMachine(
        trigger="cursor_expired_response",
        started_at=NOW,
    )
    assert machine.projection_publication_paused is True
    add_complete_snapshot(machine)
    first = event(1)
    second = event(2)
    machine.replay_events((first, first, second), event_cursor=EVENT_CURSOR)

    report = machine.reconcile(reconciled_at=NOW + timedelta(minutes=10))

    assert report.state == "ready_to_publish"
    assert report.operator_intervention_required is False
    assert report.escalation_reason is None
    assert report.replayed_event_ids == (first.event_id, second.event_id)
    assert report.deduplicated_event_ids == (first.event_id,)
    assert report.aggregate_versions == {"decision_evaluation:decision-1": 2}
    assert report.publication_token is not None
    assert set(report.snapshot_resource_counts) == set(REQUIRED_SNAPSHOT_RESOURCE_TYPES)
    assert all(count == 1 for count in report.snapshot_resource_counts.values())

    forged = report.model_copy(update={"publication_token": f"rsy_{'f' * 64}"})
    with pytest.raises(FullResyncPublicationError, match="does not belong"):
        machine.publish_atomically(
            forged,
            projection_checksum=CHECKSUM,
            checkpoint_checksum=f"sha256:{'c' * 64}",
            published_at=NOW + timedelta(minutes=11),
        )
    publication = machine.publish_atomically(
        report,
        projection_checksum=CHECKSUM,
        checkpoint_checksum=f"sha256:{'c' * 64}",
        published_at=NOW + timedelta(minutes=11),
    )
    assert publication.state == "published"
    assert publication.checkpoint_and_projection_published_atomically is True
    assert machine.projection_publication_paused is False


def test_existing_snapshot_version_skips_older_events_and_replays_next_version() -> None:
    machine = FullResyncStateMachine(
        trigger="aggregate_version_gap",
        started_at=NOW,
        snapshot_aggregate_versions={"decision_evaluation:decision-1": 1},
    )
    add_complete_snapshot(machine)
    first = event(1)
    second = event(2)
    machine.replay_events((first, second), event_cursor=EVENT_CURSOR)
    report = machine.reconcile(reconciled_at=NOW + timedelta(minutes=10))

    assert report.replayed_event_ids == (second.event_id,)
    assert report.deduplicated_event_ids == (first.event_id,)
    assert report.aggregate_versions == {"decision_evaluation:decision-1": 2}


def test_unresolved_gap_requires_operator_and_cannot_publish() -> None:
    machine = FullResyncStateMachine(trigger="aggregate_version_gap", started_at=NOW)
    add_complete_snapshot(machine)
    machine.replay_events((event(2),), event_cursor=EVENT_CURSOR)
    report = machine.reconcile(reconciled_at=NOW + timedelta(minutes=10))

    assert report.state == "operator_intervention_required"
    assert report.operator_intervention_required is True
    assert report.escalation_reason == "aggregate_version_gap"
    assert report.publication_token is None
    assert report.partial_snapshot_publish_allowed is False
    with pytest.raises(FullResyncPublicationError, match="cannot publish"):
        machine.publish_atomically(
            report,
            projection_checksum=CHECKSUM,
            checkpoint_checksum=CHECKSUM,
            published_at=NOW + timedelta(minutes=11),
        )


def test_missing_resource_and_conflicting_duplicate_fail_closed() -> None:
    missing = FullResyncStateMachine(trigger="cursor_expired_response", started_at=NOW)
    for resource_type in REQUIRED_SNAPSHOT_RESOURCE_TYPES[:-1]:
        missing.add_snapshot_resource(resource_type, (snapshot_item(resource_type),))
    missing.replay_events((), event_cursor=EVENT_CURSOR)
    missing_report = missing.reconcile(reconciled_at=NOW + timedelta(minutes=1))
    assert missing_report.escalation_reason == "missing_snapshot_resource"

    conflicting = FullResyncStateMachine(trigger="checksum_mismatch", started_at=NOW)
    add_complete_snapshot(conflicting)
    original = event(1)
    changed = original.model_copy(update={"payload": {"decision": "different"}})
    conflicting.replay_events((original, changed), event_cursor=EVENT_CURSOR)
    conflict_report = conflicting.reconcile(reconciled_at=NOW + timedelta(minutes=1))
    assert conflict_report.escalation_reason == "event_identity_conflict"


def test_source_checksum_tampering_is_rejected_before_reconciliation() -> None:
    original = snapshot_item("alert")
    changed = original.model_dump()
    changed["payload"] = {"offline_only": False}
    with pytest.raises(ValidationError, match="checksum"):
        SnapshotItem.model_validate(changed)


def test_resync_signal_is_explicit_and_contains_no_secret_material() -> None:
    assert resync_required_details("cursor_expired_response") == {
        "action": "full_snapshot_resync",
        "partial_snapshot_publish_allowed": False,
        "projection_publication": "pause",
        "stale_or_degraded_state_visible": True,
        "trigger": "cursor_expired_response",
    }
