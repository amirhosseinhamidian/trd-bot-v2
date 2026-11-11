from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Final, Literal

from pydantic import Field, JsonValue, model_validator

from trd_bot.integration.nexora.contracts import ContractModel
from trd_bot.integration.nexora.events import IntegrationEventEnvelope
from trd_bot.integration.nexora.snapshots import SnapshotItem

RESYNC_REPORT_SCHEMA_VERSION: Final = "nexora-full-resync-report-v1"
RESYNC_PUBLICATION_SCHEMA_VERSION: Final = "nexora-full-resync-publication-v1"
REQUIRED_SNAPSHOT_RESOURCE_TYPES: Final = (
    "paper_shadow_portfolio",
    "paper_shadow_position",
    "portfolio_intelligence",
    "simulation_outcome",
    "market_context",
    "decision_evaluation",
    "candidate",
    "risk_gate",
    "alert",
    "alert_outcome",
)

type ResyncTrigger = Literal[
    "cursor_expired_response",
    "aggregate_version_gap",
    "checksum_mismatch",
]
type ResyncState = Literal[
    "projection_paused",
    "snapshot_scanning",
    "event_replay",
    "reconciling",
    "ready_to_publish",
    "operator_intervention_required",
    "published",
]
type EscalationReason = Literal[
    "missing_snapshot_resource",
    "snapshot_resource_conflict",
    "event_identity_conflict",
    "aggregate_version_gap",
]


class FullResyncError(ValueError):
    """Base error for an invalid or unsafe full-resync transition."""


class FullResyncStateError(FullResyncError):
    pass


class FullResyncPublicationError(FullResyncError):
    pass


def _require_utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise FullResyncError(f"{field} must be timezone-aware UTC")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _checksum(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value).encode()).hexdigest()}"


def _aggregate_key(aggregate_type: str, aggregate_id: str) -> str:
    return f"{aggregate_type}:{aggregate_id}"


def resync_required_details(trigger: ResyncTrigger) -> dict[str, JsonValue]:
    """Return the frozen fail-closed signal carried by recovery-triggering responses."""

    return {
        "action": "full_snapshot_resync",
        "partial_snapshot_publish_allowed": False,
        "projection_publication": "pause",
        "stale_or_degraded_state_visible": True,
        "trigger": trigger,
    }


class FullResyncReport(ContractModel):
    schema_version: Literal["nexora-full-resync-report-v1"]
    trigger: ResyncTrigger
    state: Literal["ready_to_publish", "operator_intervention_required"]
    started_at: datetime
    reconciled_at: datetime
    projection_publication: Literal["paused"]
    stale_or_degraded_state_visible: Literal[True]
    partial_snapshot_publish_allowed: Literal[False]
    snapshot_resource_counts: dict[str, int]
    snapshot_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    replayed_event_ids: tuple[str, ...]
    deduplicated_event_ids: tuple[str, ...]
    event_cursor: str = Field(pattern=r"^evc_[0-9a-f]{64}$")
    aggregate_versions: dict[str, int]
    publication_token: str | None = Field(default=None, pattern=r"^rsy_[0-9a-f]{64}$")
    checkpoint_and_projection_publish_atomically: Literal[True]
    operator_intervention_required: bool
    escalation_reason: EscalationReason | None
    live_execution_enabled: Literal[False]
    external_order_submission_allowed: Literal[False]

    @model_validator(mode="after")
    def validate_report(self) -> FullResyncReport:
        _require_utc(self.started_at, field="started_at")
        _require_utc(self.reconciled_at, field="reconciled_at")
        if self.reconciled_at < self.started_at:
            raise ValueError("reconciled_at cannot precede started_at")
        expected_resources = set(REQUIRED_SNAPSHOT_RESOURCE_TYPES)
        if set(self.snapshot_resource_counts) != expected_resources:
            raise ValueError("resync report must cover every snapshot resource")
        if any(count < 0 for count in self.snapshot_resource_counts.values()):
            raise ValueError("snapshot resource counts cannot be negative")
        ready = self.state == "ready_to_publish"
        if ready != (self.publication_token is not None):
            raise ValueError("publication token is available only for a reconciled resync")
        if ready == self.operator_intervention_required:
            raise ValueError("operator intervention must be the inverse of publication readiness")
        if ready != (self.escalation_reason is None):
            raise ValueError("escalation reason must be present only for operator intervention")
        return self


class FullResyncPublication(ContractModel):
    schema_version: Literal["nexora-full-resync-publication-v1"]
    state: Literal["published"]
    publication_token: str = Field(pattern=r"^rsy_[0-9a-f]{64}$")
    projection_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    checkpoint_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    published_at: datetime
    checkpoint_and_projection_published_atomically: Literal[True]
    live_execution_enabled: Literal[False]
    external_order_submission_allowed: Literal[False]

    @model_validator(mode="after")
    def validate_publication(self) -> FullResyncPublication:
        _require_utc(self.published_at, field="published_at")
        return self


class FullResyncStateMachine:
    """Reconcile complete snapshots and replayable events without partial publication."""

    def __init__(
        self,
        *,
        trigger: ResyncTrigger,
        started_at: datetime,
        snapshot_aggregate_versions: Mapping[str, int] | None = None,
    ) -> None:
        _require_utc(started_at, field="started_at")
        versions = dict(snapshot_aggregate_versions or {})
        if any(not key or version < 0 for key, version in versions.items()):
            raise FullResyncError("snapshot aggregate versions must be non-negative")
        self.trigger = trigger
        self.started_at = started_at
        self.state: ResyncState = "projection_paused"
        self._snapshot_aggregate_versions = versions
        self._snapshots: dict[str, tuple[SnapshotItem, ...]] = {}
        self._event_cursor: str | None = None
        self._replayed_events: tuple[IntegrationEventEnvelope, ...] = ()
        self._deduplicated_event_ids: tuple[str, ...] = ()
        self._aggregate_versions = dict(versions)
        self._escalation_reason: EscalationReason | None = None
        self._publication_token: str | None = None

    @property
    def projection_publication_paused(self) -> bool:
        return self.state != "published"

    def add_snapshot_resource(
        self,
        resource_type: str,
        items: Sequence[SnapshotItem],
    ) -> None:
        if self.state not in {"projection_paused", "snapshot_scanning"}:
            raise FullResyncStateError("snapshot resources cannot be added in this resync state")
        if resource_type not in REQUIRED_SNAPSHOT_RESOURCE_TYPES:
            raise FullResyncError("snapshot resource is not part of the frozen resync contract")
        if resource_type in self._snapshots:
            self._escalate("snapshot_resource_conflict")
            return
        resolved = tuple(items)
        identities: set[str] = set()
        for item in resolved:
            reference = item.source_reference
            if reference.resource_type != resource_type:
                self._escalate("snapshot_resource_conflict")
                return
            if reference.resource_id in identities:
                self._escalate("snapshot_resource_conflict")
                return
            identities.add(reference.resource_id)
        self._snapshots[resource_type] = resolved
        self.state = "snapshot_scanning"

    def replay_events(
        self,
        events: Iterable[IntegrationEventEnvelope],
        *,
        event_cursor: str,
    ) -> None:
        if self.state == "operator_intervention_required":
            return
        if self.state != "snapshot_scanning":
            raise FullResyncStateError("event replay requires snapshot scanning first")
        if set(self._snapshots) != set(REQUIRED_SNAPSHOT_RESOURCE_TYPES):
            self._escalate("missing_snapshot_resource")
            return
        if (
            len(event_cursor) != 68
            or not event_cursor.startswith("evc_")
            or any(character not in "0123456789abcdef" for character in event_cursor[4:])
        ):
            raise FullResyncError("event cursor must be an opaque v0.3.1 cursor")

        by_event_id: dict[str, IntegrationEventEnvelope] = {}
        by_idempotency_key: dict[str, IntegrationEventEnvelope] = {}
        unique: list[IntegrationEventEnvelope] = []
        duplicates: list[str] = []
        for event in events:
            same_id = by_event_id.get(event.event_id)
            same_key = by_idempotency_key.get(event.idempotency_key)
            if same_id is not None or same_key is not None:
                existing = same_id or same_key
                if existing != event:
                    self._escalate("event_identity_conflict")
                    return
                duplicates.append(event.event_id)
                continue
            by_event_id[event.event_id] = event
            by_idempotency_key[event.idempotency_key] = event
            unique.append(event)

        unique.sort(
            key=lambda event: (
                event.aggregate_type,
                event.aggregate_id,
                event.aggregate_version,
                event.event_id,
            )
        )
        versions = dict(self._snapshot_aggregate_versions)
        replayed: list[IntegrationEventEnvelope] = []
        for event in unique:
            key = _aggregate_key(event.aggregate_type, event.aggregate_id)
            current = versions.get(key, 0)
            if event.aggregate_version <= current:
                duplicates.append(event.event_id)
                continue
            if event.aggregate_version != current + 1:
                self._escalate("aggregate_version_gap")
                return
            versions[key] = event.aggregate_version
            replayed.append(event)

        self._event_cursor = event_cursor
        self._replayed_events = tuple(replayed)
        self._deduplicated_event_ids = tuple(sorted(set(duplicates)))
        self._aggregate_versions = versions
        self.state = "event_replay"

    def reconcile(self, *, reconciled_at: datetime) -> FullResyncReport:
        _require_utc(reconciled_at, field="reconciled_at")
        if reconciled_at < self.started_at:
            raise FullResyncError("reconciled_at cannot precede started_at")
        if self.state == "snapshot_scanning":
            self._escalate("missing_snapshot_resource")
        if self.state == "operator_intervention_required":
            return self._report(reconciled_at=reconciled_at, publication_token=None)
        if self.state != "event_replay" or self._event_cursor is None:
            raise FullResyncStateError("resync cannot reconcile before event replay")
        self.state = "reconciling"
        token_evidence = {
            "aggregate_versions": self._aggregate_versions,
            "event_cursor": self._event_cursor,
            "snapshot_checksum": self._snapshot_checksum(),
            "trigger": self.trigger,
        }
        publication_token = f"rsy_{_checksum(token_evidence).removeprefix('sha256:')}"
        self._publication_token = publication_token
        self.state = "ready_to_publish"
        return self._report(
            reconciled_at=reconciled_at,
            publication_token=publication_token,
        )

    def publish_atomically(
        self,
        report: FullResyncReport,
        *,
        projection_checksum: str,
        checkpoint_checksum: str,
        published_at: datetime,
    ) -> FullResyncPublication:
        if self.state != "ready_to_publish" or report.state != "ready_to_publish":
            raise FullResyncPublicationError("unreconciled resync cannot publish")
        if report.publication_token is None:
            raise FullResyncPublicationError("publication token is missing")
        if report.publication_token != self._publication_token:
            raise FullResyncPublicationError("publication token does not belong to this resync")
        if (
            report.snapshot_checksum != self._snapshot_checksum()
            or report.event_cursor != self._event_cursor
            or report.aggregate_versions != self._aggregate_versions
        ):
            raise FullResyncPublicationError("resync report no longer matches reconciled evidence")
        publication = FullResyncPublication(
            schema_version=RESYNC_PUBLICATION_SCHEMA_VERSION,
            state="published",
            publication_token=report.publication_token,
            projection_checksum=projection_checksum,
            checkpoint_checksum=checkpoint_checksum,
            published_at=published_at,
            checkpoint_and_projection_published_atomically=True,
            live_execution_enabled=False,
            external_order_submission_allowed=False,
        )
        self.state = "published"
        return publication

    def _escalate(self, reason: EscalationReason) -> None:
        self._escalation_reason = reason
        self.state = "operator_intervention_required"

    def _snapshot_checksum(self) -> str:
        evidence = {
            resource_type: [item.model_dump(mode="json") for item in items]
            for resource_type, items in sorted(self._snapshots.items())
        }
        return _checksum(evidence)

    def _report(
        self,
        *,
        reconciled_at: datetime,
        publication_token: str | None,
    ) -> FullResyncReport:
        ready = self.state == "ready_to_publish"
        event_cursor = self._event_cursor or f"evc_{'0' * 64}"
        return FullResyncReport(
            schema_version=RESYNC_REPORT_SCHEMA_VERSION,
            trigger=self.trigger,
            state="ready_to_publish" if ready else "operator_intervention_required",
            started_at=self.started_at,
            reconciled_at=reconciled_at,
            projection_publication="paused",
            stale_or_degraded_state_visible=True,
            partial_snapshot_publish_allowed=False,
            snapshot_resource_counts={
                resource_type: len(self._snapshots.get(resource_type, ()))
                for resource_type in REQUIRED_SNAPSHOT_RESOURCE_TYPES
            },
            snapshot_checksum=self._snapshot_checksum(),
            replayed_event_ids=tuple(event.event_id for event in self._replayed_events),
            deduplicated_event_ids=self._deduplicated_event_ids,
            event_cursor=event_cursor,
            aggregate_versions=dict(sorted(self._aggregate_versions.items())),
            publication_token=publication_token,
            checkpoint_and_projection_publish_atomically=True,
            operator_intervention_required=not ready,
            escalation_reason=self._escalation_reason,
            live_execution_enabled=False,
            external_order_submission_allowed=False,
        )
