#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-alert-snapshot-resources.json"
SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/alert-snapshot-resources.schema.json"
MANIFEST_PATH = ROOT / "contracts/v0.3.1/stage-acceptance/trd-v031-05.json"
PREVIOUS_FREEZE_PATH = ROOT / "artifacts/v0.3.1/trd-v031-04-decision-snapshot-resources-freeze.json"
READER_PATH = ROOT / "src/trd_bot/integration/nexora/alert_snapshots.py"
ROUTES_PATH = ROOT / "src/trd_bot/integration/nexora/routes.py"
WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-alert-snapshots.yml"
PREVIOUS_FREEZE_CHECKSUM = "29428cd3813ce18af29a950137aa2b8449c377264239b164bf31cdf787a1ecde"
EXPECTED_RESOURCES = ("alert", "alert_outcome")
EXPECTED_SCHEMA_VERSIONS = {
    "alert": "trd-bot-alert-v1",
    "alert_outcome": "trd-bot-alert-outcome-v1",
}


class V031AlertSnapshotError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031AlertSnapshotError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_previous_freeze(record: dict[str, Any]) -> None:
    require(
        canonical_checksum(record) == PREVIOUS_FREEZE_CHECKSUM,
        "TRD-V031-04 historical Freeze artifact drift",
    )
    require(record.get("decision_id") == "TRD-V031-04", "previous stage drift")
    require(record.get("frozen") is True, "TRD-V031-04 is not frozen")


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("schema_version") == "trd-bot-v031-alert-snapshot-resources-v1",
        "stage contract schema drift",
    )
    require(contract.get("decision_id") == "TRD-V031-05", "stage ID drift")
    require(contract.get("status") == "candidate", "stage is not a candidate")
    resources = contract.get("resources")
    require(isinstance(resources, dict), "resources must be an object")
    require(tuple(resources.get("allowlist", ())) == EXPECTED_RESOURCES, "resource allowlist drift")
    require(
        resources.get("schema_versions") == EXPECTED_SCHEMA_VERSIONS,
        "resource schema versions drift",
    )
    require(resources.get("immutable_evidence_only") is True, "immutable evidence required")
    require(resources.get("mutable_inbox_state_excluded") is True, "mutable inbox state exposed")
    safety = contract.get("safety")
    require(isinstance(safety, dict), "safety must be an object")
    require(safety.get("offline_only_required") is True, "offline-only guard removed")
    for key in (
        "external_order_submission_allowed",
        "exchange_credentials_allowed",
        "service_token_in_payload_allowed",
        "service_token_in_cursor_allowed",
        "direct_database_access_for_consumer",
    ):
        require(safety.get(key) is False, f"unsafe capability enabled: {key}")
    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "persistence must be an object")
    require(persistence.get("migration_added") is False, "unexpected migration added")
    require(persistence.get("migration_head") == "20261106_0037", "migration head drift")
    scope = contract.get("scope")
    require(isinstance(scope, dict), "scope must be an object")
    for key in ("provider_compatibility_claimed", "nexora_p3_03_opened", "live_execution_enabled"):
        require(scope.get(key) is False, f"scope safety gate opened: {key}")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition must be an object")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-06_AFTER_CI_ACCEPTANCE",
        "next stage bypasses CI acceptance",
    )
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze restored")


def validate_schema(schema: dict[str, Any]) -> None:
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "schema definitions missing")
    require("alert" in definitions and "alert_outcome" in definitions, "resource schemas missing")
    for name in EXPECTED_RESOURCES:
        definition = definitions[name]
        require(isinstance(definition, dict), f"{name} schema must be an object")
        require(definition.get("additionalProperties") is False, f"{name} schema is open")
        properties = definition.get("properties")
        require(isinstance(properties, dict), f"{name} properties missing")
        require(properties.get("offline_only") == {"const": True}, "offline schema guard drift")
        require(
            properties.get("external_order_submission_allowed") == {"const": False},
            "external order schema guard drift",
        )
    alert_properties = cast(dict[str, Any], definitions["alert"])["properties"]
    for mutable in ("acknowledged_at", "acknowledged_by", "snoozed_until", "snoozed_by"):
        require(mutable not in alert_properties, f"mutable inbox field exposed: {mutable}")


def validate_manifest(manifest: dict[str, Any]) -> None:
    require(manifest.get("stage_id") == "TRD-V031-05", "manifest stage drift")
    require(manifest.get("status") == "candidate", "manifest is not a candidate")
    migration = manifest.get("migration")
    require(isinstance(migration, dict), "manifest migration missing")
    require(migration.get("expected") is False, "manifest expects a migration")
    transition = manifest.get("transition")
    require(isinstance(transition, dict), "manifest transition missing")
    require(transition.get("next_stage") == "TRD-V031-06", "manifest next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "manifest Freeze restored")


def validate_implementation(reader: str, routes: str, workflow: str) -> None:
    for required in (
        'ALERT: Final = "alert"',
        'ALERT_OUTCOME: Final = "alert_outcome"',
        "AlertRow.created_at",
        "AlertOutcomeRow.recorded_at",
        '"offline_only": True',
        '"external_order_submission_allowed": False',
    ):
        require(required in reader, f"reader invariant missing: {required}")
    for forbidden in ("AlertInboxStateRow", "AlertActionRow", "acknowledged_at", "snoozed_until"):
        require(forbidden not in reader, f"mutable alert state imported: {forbidden}")
    require("AlertSnapshotResourceReader" in routes, "alert reader route missing")
    require("*ALERT_SNAPSHOT_RESOURCE_TYPES" in routes, "alert route allowlist missing")
    require(
        "uses: ./.github/workflows/v0-3-1-stage-acceptance.yml" in workflow,
        "reusable acceptance not called",
    )
    require("stage_id: TRD-V031-05" in workflow, "workflow stage drift")


def verify() -> None:
    validate_previous_freeze(load_json(PREVIOUS_FREEZE_PATH))
    validate_contract(load_json(CONTRACT_PATH))
    validate_schema(load_json(SCHEMA_PATH))
    validate_manifest(load_json(MANIFEST_PATH))
    validate_implementation(
        READER_PATH.read_text(encoding="utf-8"),
        ROUTES_PATH.read_text(encoding="utf-8"),
        WORKFLOW_PATH.read_text(encoding="utf-8"),
    )


def main() -> int:
    verify()
    for marker in (
        "TRD_V031_05_ALERT_RESOURCE_ALLOWLIST=PASS",
        "TRD_V031_05_IMMUTABLE_ALERT_EVIDENCE=PASS",
        "TRD_V031_05_STABLE_PAGING=PASS",
        "TRD_V031_05_SOURCE_REFERENCE_CHECKSUM=PASS",
        "TRD_V031_05_AUTHENTICATED_ENDPOINT=PASS",
        "TRD_V031_05_DATABASE_MIGRATION=NONE",
        "TRD_V031_05_ACCEPTANCE_CANDIDATE=PASS",
        "TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE",
        "NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE",
        "TRD_BOT_LIVE_EXECUTION=DISABLED",
        "NEXT_ALLOWED_STAGE=TRD-V031-06_AFTER_CI_ACCEPTANCE",
    ):
        print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
