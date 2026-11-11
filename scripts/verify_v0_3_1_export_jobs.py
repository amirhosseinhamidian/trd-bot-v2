#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-export-jobs.json"
SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/export-protocol.schema.json"
MANIFEST_PATH = ROOT / "contracts/v0.3.1/stage-acceptance/trd-v031-08.json"
PROTOCOL_PATH = ROOT / "src/trd_bot/integration/nexora/exports.py"
STORE_PATH = ROOT / "src/trd_bot/db/nexora_exports.py"
MODELS_PATH = ROOT / "src/trd_bot/db/models.py"
ROUTES_PATH = ROOT / "src/trd_bot/integration/nexora/routes.py"
JOBS_PATH = ROOT / "src/trd_bot/jobs.py"
MIGRATION_PATH = ROOT / "alembic/versions/20261111_0040_nexora_exports.py"
WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-export-jobs.yml"
ACCEPTED_STAGE_07_COMMIT = "b26913e7147d2867d0855a92f4e9518aff254e96"
ACCEPTED_STAGE_07_EVIDENCE = "dce1e4abd2db8ad03cef88152db16cfaaaac8934c51c33e07f404347d56494dd"


class V031ExportJobsError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031ExportJobsError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("decision_id") == "TRD-V031-08", "stage ID drift")
    require(contract.get("status") == "candidate", "stage is not a candidate")
    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_07_COMMIT,
        "Stage 07 commit drift",
    )
    require(
        prerequisite.get("accepted_evidence_checksum") == ACCEPTED_STAGE_07_EVIDENCE,
        "Stage 07 evidence drift",
    )
    require(
        contract.get("operations")
        == [
            "POST /api/v1/integration/nexora/exports",
            "GET /api/v1/integration/nexora/exports/{export_id}",
            "GET /api/v1/integration/nexora/exports/{export_id}/manifest",
        ],
        "export operation drift",
    )
    protocol = contract.get("protocol")
    require(isinstance(protocol, dict), "export protocol missing")
    require(protocol.get("profiles") == ["private", "ai_safe"], "profile boundary drift")
    require(protocol.get("partial_manifest_allowed") is False, "partial manifest enabled")
    require(protocol.get("file_checksums_required") is True, "file checksums removed")
    require(protocol.get("source_lineage_required") is True, "source lineage removed")
    require(protocol.get("secret_fields_allowed") is False, "secret export enabled")
    require(protocol.get("same_key_different_body_status") == 409, "409 conflict removed")
    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "export persistence missing")
    require(persistence.get("migration_revision") == "20261111_0040", "migration drift")
    require(persistence.get("atomic_completion") is True, "atomic completion removed")
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
        transition.get("next_allowed_stage") == "TRD-V031-09_AFTER_CI_ACCEPTANCE",
        "CI acceptance bypassed",
    )
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze restored")


def validate_schema(schema: dict[str, Any]) -> None:
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "schema definitions missing")
    for name in ("request", "status", "source_reference", "file", "manifest"):
        definition = definitions.get(name)
        require(
            isinstance(definition, dict) and definition.get("additionalProperties") is False,
            f"{name} schema is open",
        )
    manifest = cast(dict[str, Any], definitions["manifest"])
    properties = manifest.get("properties")
    require(isinstance(properties, dict), "manifest properties missing")
    require(
        cast(dict[str, Any], properties.get("completion_status", {})).get("const") == "complete",
        "partial completion schema enabled",
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    require(manifest.get("stage_id") == "TRD-V031-08", "manifest stage drift")
    require(manifest.get("status") == "candidate", "manifest is not a candidate")
    prerequisite = manifest.get("prerequisite")
    require(isinstance(prerequisite, dict), "manifest prerequisite missing")
    require(prerequisite.get("mode") == "ci_artifact", "Stage 07 acceptance artifact not required")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_07_COMMIT,
        "manifest prerequisite SHA drift",
    )
    transition = manifest.get("transition")
    require(isinstance(transition, dict), "manifest transition missing")
    require(transition.get("next_stage") == "TRD-V031-09", "manifest next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "manifest Freeze restored")


def validate_implementation(
    protocol: str,
    store: str,
    models: str,
    routes: str,
    jobs: str,
    migration: str,
    workflow: str,
) -> None:
    for marker in (
        'Literal["private", "ai_safe"]',
        'Literal["complete"]',
        "contains_secret",
        "lineage_references",
    ):
        require(marker in protocol, f"protocol invariant missing: {marker}")
    for marker in (
        "hashlib.sha256(content).hexdigest()",
        'row.status = "complete"',
        "NexoraExportArtifactRow",
        "redaction_profile",
    ):
        require(marker in store, f"export persistence invariant missing: {marker}")
    require("NexoraExportJobRow" in models, "export job model missing")
    require("NexoraExportArtifactRow" in models, "export artifact model missing")
    for operation in ('"/exports"', '"/exports/{export_id}"', '"/exports/{export_id}/manifest"'):
        require(operation in routes, f"export endpoint missing: {operation}")
    require('NEXORA_EXPORT = "nexora_export"' in jobs, "export worker kind missing")
    require('revision: str = "20261111_0040"' in migration, "migration revision missing")
    require('down_revision: str | None = "20261107_0039"' in migration, "migration lineage drift")
    require(
        "uses: ./.github/workflows/v0-3-1-stage-acceptance.yml" in workflow,
        "reusable acceptance not called",
    )
    require("stage_id: TRD-V031-08" in workflow, "workflow stage drift")
    combined = "\n".join((protocol, store, models, routes, jobs))
    require("submit_order" not in combined and "place_order" not in combined, "order path added")


def verify() -> None:
    validate_contract(load_json(CONTRACT_PATH))
    validate_schema(load_json(SCHEMA_PATH))
    validate_manifest(load_json(MANIFEST_PATH))
    validate_implementation(
        PROTOCOL_PATH.read_text(encoding="utf-8"),
        STORE_PATH.read_text(encoding="utf-8"),
        MODELS_PATH.read_text(encoding="utf-8"),
        ROUTES_PATH.read_text(encoding="utf-8"),
        JOBS_PATH.read_text(encoding="utf-8"),
        MIGRATION_PATH.read_text(encoding="utf-8"),
        WORKFLOW_PATH.read_text(encoding="utf-8"),
    )


def main() -> int:
    verify()
    for marker in (
        "TRD_V031_08_PRIVATE_EXPORT=PASS",
        "TRD_V031_08_AI_SAFE_EXPORT=PASS",
        "TRD_V031_08_COMPLETE_MANIFEST=PASS",
        "TRD_V031_08_FILE_CHECKSUMS=PASS",
        "TRD_V031_08_SOURCE_LINEAGE=PASS",
        "TRD_V031_08_MIGRATION=20261111_0040",
        "TRD_V031_08_ACCEPTANCE_CANDIDATE=PASS",
        "TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE",
        "NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE",
        "TRD_BOT_LIVE_EXECUTION=DISABLED",
        "NEXT_ALLOWED_STAGE=TRD-V031-09_AFTER_CI_ACCEPTANCE",
    ):
        print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
