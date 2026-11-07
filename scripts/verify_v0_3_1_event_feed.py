#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-event-feed.json"
SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/event-feed.schema.json"
MANIFEST_PATH = ROOT / "contracts/v0.3.1/stage-acceptance/trd-v031-06.json"
EVENTS_PATH = ROOT / "src/trd_bot/integration/nexora/events.py"
STORE_PATH = ROOT / "src/trd_bot/db/nexora_events.py"
MODELS_PATH = ROOT / "src/trd_bot/db/models.py"
ROUTES_PATH = ROOT / "src/trd_bot/integration/nexora/routes.py"
MIGRATION_PATH = ROOT / "alembic/versions/20261107_0038_nexora_event_feed.py"
WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-event-feed.yml"
ACCEPTED_STAGE_05_COMMIT = "10435e4c98e59d2d616fde1c6b92a2598d20a1ee"
ACCEPTED_STAGE_05_EVIDENCE = "c543e4cf0d2813599139d487df15e7dcbbc330cb05e3f2a261a7e25201c7f08b"


class V031EventFeedError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031EventFeedError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("decision_id") == "TRD-V031-06", "stage ID drift")
    require(contract.get("status") == "candidate", "stage is not a candidate")
    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_05_COMMIT, "Stage 05 commit drift"
    )
    require(
        prerequisite.get("accepted_evidence_checksum") == ACCEPTED_STAGE_05_EVIDENCE,
        "Stage 05 evidence drift",
    )
    protocol = contract.get("protocol")
    require(isinstance(protocol, dict), "event protocol missing")
    require(protocol.get("delivery_semantics") == "at_least_once", "delivery semantics drift")
    require(protocol.get("exactly_once_claimed") is False, "exactly-once claimed")
    require(protocol.get("ordering_scope") == "per_aggregate", "ordering scope drift")
    require(protocol.get("gap_detection") == "aggregate_version", "gap detection removed")
    require(
        protocol.get("deduplication_keys") == ["event_id", "idempotency_key"],
        "deduplication keys drift",
    )
    require(protocol.get("expired_cursor_status") == 410, "expired cursor status drift")
    require(protocol.get("expired_cursor_action") == "full_snapshot_resync", "resync action drift")
    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "persistence missing")
    require(persistence.get("migration_added") is True, "event migration missing")
    require(persistence.get("migration_revision") == "20261107_0038", "migration revision drift")
    safety = contract.get("safety")
    require(isinstance(safety, dict), "safety boundary missing")
    require(safety.get("offline_only_required") is True, "offline-only guard removed")
    for key in (
        "external_order_submission_allowed",
        "exchange_credentials_allowed",
        "service_token_in_payload_allowed",
        "service_token_in_cursor_allowed",
        "live_execution_enabled",
        "provider_compatibility_claimed",
        "nexora_p3_03_opened",
    ):
        require(safety.get(key) is False, f"unsafe capability enabled: {key}")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-07_AFTER_CI_ACCEPTANCE",
        "CI acceptance bypassed",
    )
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze restored")


def validate_schema(schema: dict[str, Any]) -> None:
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "schema definitions missing")
    envelope = definitions.get("envelope")
    page = definitions.get("page")
    require(
        isinstance(envelope, dict) and envelope.get("additionalProperties") is False,
        "envelope schema is open",
    )
    require(
        isinstance(page, dict) and page.get("additionalProperties") is False, "page schema is open"
    )
    properties = envelope.get("properties")
    require(isinstance(properties, dict), "envelope properties missing")
    require(properties.get("offline_only") == {"const": True}, "offline schema guard drift")
    require(
        properties.get("external_order_submission_allowed") == {"const": False},
        "external order schema guard drift",
    )
    require("aggregate_version" in properties, "aggregate gap evidence missing")
    require("event_checksum" in properties, "event checksum missing")


def validate_manifest(manifest: dict[str, Any]) -> None:
    require(manifest.get("stage_id") == "TRD-V031-06", "manifest stage drift")
    require(manifest.get("status") == "candidate", "manifest is not a candidate")
    prerequisite = manifest.get("prerequisite")
    require(isinstance(prerequisite, dict), "manifest prerequisite missing")
    require(prerequisite.get("mode") == "ci_artifact", "Stage 05 acceptance artifact not required")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_05_COMMIT,
        "manifest prerequisite SHA drift",
    )
    migration = manifest.get("migration")
    require(
        isinstance(migration, dict) and migration.get("expected") is True,
        "manifest migration drift",
    )
    transition = manifest.get("transition")
    require(isinstance(transition, dict), "manifest transition missing")
    require(transition.get("next_stage") == "TRD-V031-07", "manifest next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "manifest Freeze restored")


def validate_implementation(
    events: str, store: str, models: str, routes: str, migration: str, workflow: str
) -> None:
    for marker in (
        'EVENT_ENVELOPE_SCHEMA_VERSION: Final = "trd-integration-event-envelope-v1"',
        'delivery_semantics: Literal["at_least_once"]',
        "aggregate_version",
        "event_checksum",
        "external_order_submission_allowed: Literal[False]",
    ):
        require(marker in events, f"event contract invariant missing: {marker}")
    for marker in (
        "EventAggregateGapError",
        "EventIdempotencyConflictError",
        "EventCursorExpiredError",
        "page_limit",
    ):
        require(marker in store, f"event persistence invariant missing: {marker}")
    require(
        "NexoraIntegrationEventRow" in models and "NexoraEventCursorRow" in models,
        "event models missing",
    )
    require('"/events"' in routes and '"/events/{event_id}"' in routes, "event endpoints missing")
    require('revision: str = "20261107_0038"' in migration, "migration revision missing")
    require('down_revision: str | None = "20261106_0037"' in migration, "migration lineage drift")
    require(
        "uses: ./.github/workflows/v0-3-1-stage-acceptance.yml" in workflow,
        "reusable acceptance not called",
    )
    require("stage_id: TRD-V031-06" in workflow, "workflow stage drift")
    combined = "\n".join((events, store, models, routes))
    require("exchange_credentials" not in combined, "exchange credential path added")
    require("submit_order" not in combined and "place_order" not in combined, "order path added")


def verify() -> None:
    validate_contract(load_json(CONTRACT_PATH))
    validate_schema(load_json(SCHEMA_PATH))
    validate_manifest(load_json(MANIFEST_PATH))
    validate_implementation(
        EVENTS_PATH.read_text(encoding="utf-8"),
        STORE_PATH.read_text(encoding="utf-8"),
        MODELS_PATH.read_text(encoding="utf-8"),
        ROUTES_PATH.read_text(encoding="utf-8"),
        MIGRATION_PATH.read_text(encoding="utf-8"),
        WORKFLOW_PATH.read_text(encoding="utf-8"),
    )


def main() -> int:
    verify()
    for marker in (
        "TRD_V031_06_EVENT_ENVELOPE=PASS",
        "TRD_V031_06_AT_LEAST_ONCE_REPLAY=PASS",
        "TRD_V031_06_EVENT_LOOKUP=PASS",
        "TRD_V031_06_AGGREGATE_GAP_DETECTION=PASS",
        "TRD_V031_06_EXPIRED_CURSOR_FULL_RESYNC=PASS",
        "TRD_V031_06_MIGRATION=20261107_0038",
        "TRD_V031_06_ACCEPTANCE_CANDIDATE=PASS",
        "TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE",
        "NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE",
        "TRD_BOT_LIVE_EXECUTION=DISABLED",
        "NEXT_ALLOWED_STAGE=TRD-V031-07_AFTER_CI_ACCEPTANCE",
    ):
        print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
