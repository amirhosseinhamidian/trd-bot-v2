#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-full-resync.json"
SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/full-resync.schema.json"
MANIFEST_PATH = ROOT / "contracts/v0.3.1/stage-acceptance/trd-v031-09.json"
RESYNC_PATH = ROOT / "src/trd_bot/integration/nexora/resync.py"
ROUTES_PATH = ROOT / "src/trd_bot/integration/nexora/routes.py"
WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-full-resync.yml"
ACCEPTED_STAGE_08_COMMIT = "2ca62661fc80096e03c16e2b02cc19a997ba2d07"
ACCEPTED_STAGE_08_EVIDENCE = "00c7b9b88b1b99940f87bd7059bea8ef911a95ca93f85c273185871af61c63f4"
EXPECTED_RESOURCES = [
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
]


class V031FullResyncError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031FullResyncError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("decision_id") == "TRD-V031-09", "stage ID drift")
    require(contract.get("status") == "candidate", "stage is not a candidate")
    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_08_COMMIT,
        "Stage 08 commit drift",
    )
    require(
        prerequisite.get("accepted_evidence_checksum") == ACCEPTED_STAGE_08_EVIDENCE,
        "Stage 08 evidence drift",
    )
    api = contract.get("api_boundary")
    require(isinstance(api, dict), "API boundary missing")
    require(api.get("new_operations") == [], "unfrozen resync endpoint added")
    require(api.get("frozen_operations_changed") is False, "frozen API changed")
    require(api.get("cursor_expired_status") == 410, "cursor expiry status drift")
    require(api.get("projection_publication_signal") == "pause", "pause signal removed")
    state_machine = contract.get("state_machine")
    require(isinstance(state_machine, dict), "state machine missing")
    require(state_machine.get("snapshot_resource_count") == 10, "snapshot coverage drift")
    require(state_machine.get("all_snapshot_resources_required") is True, "partial scan enabled")
    require(
        state_machine.get("event_deduplication_keys") == ["event_id", "idempotency_key"],
        "event deduplication drift",
    )
    for key, message in (
        ("aggregate_versions_must_be_contiguous", "gap detection removed"),
        ("checkpoint_and_projection_publish_atomically", "atomic publication removed"),
        ("unresolved_gap_requires_operator_intervention", "operator escalation removed"),
        ("stale_or_degraded_state_must_be_visible", "degraded-state visibility removed"),
    ):
        require(state_machine.get(key) is True, message)
    require(
        state_machine.get("partial_snapshot_publish_allowed") is False,
        "partial publication enabled",
    )
    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "persistence declaration missing")
    require(persistence.get("migration_revision") is None, "unexpected migration added")
    require(persistence.get("new_tables") == [], "unexpected resync table added")
    safety = contract.get("safety")
    require(isinstance(safety, dict), "safety boundary missing")
    for key in (
        "external_order_submission_allowed",
        "exchange_credentials_allowed",
        "wallet_or_fund_transfer_allowed",
        "shared_database_allowed",
        "live_execution_enabled",
        "provider_compatibility_claimed",
        "nexora_p3_03_opened",
    ):
        require(safety.get(key) is False, f"unsafe capability enabled: {key}")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-10_AFTER_CI_ACCEPTANCE",
        "CI acceptance bypassed",
    )
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze restored")


def validate_schema(schema: dict[str, Any]) -> None:
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "schema definitions missing")
    for name in ("report", "publication"):
        definition = definitions.get(name)
        require(
            isinstance(definition, dict) and definition.get("additionalProperties") is False,
            f"{name} schema is open",
        )
    report = cast(dict[str, Any], definitions["report"])
    properties = report.get("properties")
    require(isinstance(properties, dict), "report properties missing")
    require(
        cast(dict[str, Any], properties.get("partial_snapshot_publish_allowed", {})).get("const")
        is False,
        "partial publish schema enabled",
    )
    require(
        cast(dict[str, Any], properties.get("live_execution_enabled", {})).get("const") is False,
        "live execution schema enabled",
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    require(manifest.get("stage_id") == "TRD-V031-09", "manifest stage drift")
    require(manifest.get("status") == "candidate", "manifest is not a candidate")
    prerequisite = manifest.get("prerequisite")
    require(isinstance(prerequisite, dict), "manifest prerequisite missing")
    require(prerequisite.get("mode") == "ci_artifact", "Stage 08 acceptance artifact not required")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_08_COMMIT,
        "manifest prerequisite SHA drift",
    )
    migration = manifest.get("migration")
    require(isinstance(migration, dict), "manifest migration declaration missing")
    require(migration.get("expected") is False, "unexpected migration expected")
    transition = manifest.get("transition")
    require(isinstance(transition, dict), "manifest transition missing")
    require(transition.get("next_stage") == "TRD-V031-10", "manifest next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "manifest Freeze restored")


def validate_implementation(resync: str, routes: str, workflow: str) -> None:
    for resource in EXPECTED_RESOURCES:
        require(f'"{resource}"' in resync, f"snapshot resource missing: {resource}")
    for marker in (
        "class FullResyncStateMachine",
        'self.state: ResyncState = "projection_paused"',
        'self.state = "snapshot_scanning"',
        'self.state = "event_replay"',
        'self.state = "reconciling"',
        'self.state = "ready_to_publish"',
        'self.state = "published"',
        'self._escalate("aggregate_version_gap")',
        "checkpoint_and_projection_published_atomically=True",
        "partial_snapshot_publish_allowed=False",
        "external_order_submission_allowed=False",
    ):
        require(marker in resync, f"resync invariant missing: {marker}")
    require("resync_required_details" in routes, "structured resync signal missing")
    require(
        'details=resync_required_details("cursor_expired_response")' in routes, "410 signal missing"
    )
    require(
        "uses: ./.github/workflows/v0-3-1-stage-acceptance.yml" in workflow,
        "reusable acceptance not called",
    )
    require("stage_id: TRD-V031-09" in workflow, "workflow stage drift")
    combined = "\n".join((resync, routes))
    require("submit_order" not in combined and "place_order" not in combined, "order path added")


def verify() -> None:
    validate_contract(load_json(CONTRACT_PATH))
    validate_schema(load_json(SCHEMA_PATH))
    validate_manifest(load_json(MANIFEST_PATH))
    validate_implementation(
        RESYNC_PATH.read_text(encoding="utf-8"),
        ROUTES_PATH.read_text(encoding="utf-8"),
        WORKFLOW_PATH.read_text(encoding="utf-8"),
    )


def main() -> int:
    verify()
    for marker in (
        "TRD_V031_09_RESYNC_STATE_MACHINE=PASS",
        "TRD_V031_09_PROJECTION_PAUSE_SIGNAL=PASS",
        "TRD_V031_09_SNAPSHOT_EVENT_RECONCILIATION=PASS",
        "TRD_V031_09_OPERATOR_ESCALATION=PASS",
        "TRD_V031_09_ATOMIC_PUBLICATION_GUARD=PASS",
        "TRD_V031_09_DATABASE_MIGRATION=NONE",
        "TRD_V031_09_ACCEPTANCE_CANDIDATE=PASS",
        "TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE",
        "NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE",
        "TRD_BOT_LIVE_EXECUTION=DISABLED",
        "NEXT_ALLOWED_STAGE=TRD-V031-10_AFTER_CI_ACCEPTANCE",
    ):
        print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
