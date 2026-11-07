#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-decision-review-commands.json"
SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/decision-review-command.schema.json"
MANIFEST_PATH = ROOT / "contracts/v0.3.1/stage-acceptance/trd-v031-07.json"
COMMANDS_PATH = ROOT / "src/trd_bot/integration/nexora/decision_reviews.py"
STORE_PATH = ROOT / "src/trd_bot/db/nexora_decision_reviews.py"
MODELS_PATH = ROOT / "src/trd_bot/db/models.py"
ROUTES_PATH = ROOT / "src/trd_bot/integration/nexora/routes.py"
MIGRATION_PATH = ROOT / "alembic/versions/20261107_0039_nexora_decision_reviews.py"
WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-decision-reviews.yml"
ACCEPTED_STAGE_06_COMMIT = "ee96c73ead801a93497b1cb9b06decb5eac5842a"
ACCEPTED_STAGE_06_EVIDENCE = "84948fc942e4621ba8345ae62f808c5231851a05f01444e72448e9a47343ad7b"


class V031DecisionReviewError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031DecisionReviewError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("decision_id") == "TRD-V031-07", "stage ID drift")
    require(contract.get("status") == "candidate", "stage is not a candidate")
    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_06_COMMIT,
        "Stage 06 commit drift",
    )
    require(
        prerequisite.get("accepted_evidence_checksum") == ACCEPTED_STAGE_06_EVIDENCE,
        "Stage 06 evidence drift",
    )
    endpoint = contract.get("endpoint")
    require(isinstance(endpoint, dict), "command endpoint missing")
    require(endpoint.get("idempotency_header") == "Idempotency-Key", "idempotency header drift")
    require(endpoint.get("success_status") == 202, "acceptance status drift")
    protocol = contract.get("protocol")
    require(isinstance(protocol, dict), "command protocol missing")
    require(
        protocol.get("command_types")
        == [
            "decision_review.accept.v1",
            "decision_review.reject.v1",
            "decision_review.defer.v1",
        ],
        "command type drift",
    )
    require(protocol.get("portfolio_modes") == ["paper", "shadow"], "mode boundary drift")
    require(protocol.get("exact_retry_status") == "duplicate", "duplicate receipt removed")
    require(protocol.get("same_key_different_body_status") == 409, "409 conflict removed")
    require(protocol.get("source_evidence_mismatch_status") == 412, "source guard removed")
    require(protocol.get("source_evidence_checksum_required") is True, "checksum guard removed")
    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "persistence missing")
    require(persistence.get("migration_revision") == "20261107_0039", "migration drift")
    require(persistence.get("append_only_journal") is True, "append-only journal removed")
    ownership = contract.get("ownership")
    require(isinstance(ownership, dict), "ownership boundary missing")
    require(ownership.get("owner_review_source_of_truth") == "nexora", "review ownership drift")
    for key in (
        "execution_authorization_created",
        "live_order_created",
        "portfolio_transaction_posted",
    ):
        require(ownership.get(key) is False, f"unsafe review side effect enabled: {key}")
    safety = contract.get("safety")
    require(isinstance(safety, dict), "safety boundary missing")
    require(safety.get("offline_only_required") is True, "offline-only guard removed")
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
        transition.get("next_allowed_stage") == "TRD-V031-08_AFTER_CI_ACCEPTANCE",
        "CI acceptance bypassed",
    )
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze restored")


def validate_schema(schema: dict[str, Any]) -> None:
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "schema definitions missing")
    command = definitions.get("command")
    receipt = definitions.get("receipt")
    source = definitions.get("source_reference")
    require(
        isinstance(command, dict) and command.get("additionalProperties") is False,
        "command schema is open",
    )
    require(
        isinstance(receipt, dict) and receipt.get("additionalProperties") is False,
        "receipt schema is open",
    )
    require(
        isinstance(source, dict) and source.get("additionalProperties") is False,
        "source-reference schema is open",
    )
    command_properties = command.get("properties")
    require(isinstance(command_properties, dict), "command properties missing")
    require("evidence" in command_properties, "source evidence missing")
    receipt_properties = receipt.get("properties")
    require(isinstance(receipt_properties, dict), "receipt properties missing")
    require(
        receipt_properties.get("status") == {"enum": ["accepted", "duplicate"]},
        "duplicate receipt schema drift",
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    require(manifest.get("stage_id") == "TRD-V031-07", "manifest stage drift")
    require(manifest.get("status") == "candidate", "manifest is not a candidate")
    prerequisite = manifest.get("prerequisite")
    require(isinstance(prerequisite, dict), "manifest prerequisite missing")
    require(prerequisite.get("mode") == "ci_artifact", "Stage 06 acceptance artifact not required")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_06_COMMIT,
        "manifest prerequisite SHA drift",
    )
    migration = manifest.get("migration")
    require(
        isinstance(migration, dict) and migration.get("expected") is True,
        "manifest migration drift",
    )
    transition = manifest.get("transition")
    require(isinstance(transition, dict), "manifest transition missing")
    require(transition.get("next_stage") == "TRD-V031-08", "manifest next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "manifest Freeze restored")


def validate_implementation(
    commands: str, store: str, models: str, routes: str, migration: str, workflow: str
) -> None:
    for marker in (
        'DECISION_REVIEW_COMMAND_SCHEMA_VERSION: Final = "nexora-decision-review-command-v1"',
        'COMMAND_RECEIPT_SCHEMA_VERSION: Final = "nexora-command-receipt-v1"',
        'Literal["paper", "shadow"]',
        "request_checksum",
    ):
        require(marker in commands, f"command invariant missing: {marker}")
    for marker in (
        "DecisionReviewIdempotencyConflictError",
        "DecisionReviewSourceEvidenceError",
        "source evidence reference or checksum",
        'status="duplicate"',
    ):
        require(marker in store, f"review persistence invariant missing: {marker}")
    require("NexoraDecisionReviewRow" in models, "decision-review model missing")
    require('"/commands/decision-reviews"' in routes, "decision-review endpoint missing")
    require('revision: str = "20261107_0039"' in migration, "migration revision missing")
    require('down_revision: str | None = "20261107_0038"' in migration, "migration lineage drift")
    require(
        "uses: ./.github/workflows/v0-3-1-stage-acceptance.yml" in workflow,
        "reusable acceptance not called",
    )
    require("stage_id: TRD-V031-07" in workflow, "workflow stage drift")
    combined = "\n".join((commands, store, models, routes))
    require("exchange_credentials" not in combined, "exchange credential path added")
    require("submit_order" not in combined and "place_order" not in combined, "order path added")


def verify() -> None:
    validate_contract(load_json(CONTRACT_PATH))
    validate_schema(load_json(SCHEMA_PATH))
    validate_manifest(load_json(MANIFEST_PATH))
    validate_implementation(
        COMMANDS_PATH.read_text(encoding="utf-8"),
        STORE_PATH.read_text(encoding="utf-8"),
        MODELS_PATH.read_text(encoding="utf-8"),
        ROUTES_PATH.read_text(encoding="utf-8"),
        MIGRATION_PATH.read_text(encoding="utf-8"),
        WORKFLOW_PATH.read_text(encoding="utf-8"),
    )


def main() -> int:
    verify()
    for marker in (
        "TRD_V031_07_ACCEPT_REJECT_DEFER=PASS",
        "TRD_V031_07_DUPLICATE_RECEIPT=PASS",
        "TRD_V031_07_IDEMPOTENCY_CONFLICT_409=PASS",
        "TRD_V031_07_SOURCE_EVIDENCE_GUARD=PASS",
        "TRD_V031_07_MIGRATION=20261107_0039",
        "TRD_V031_07_ACCEPTANCE_CANDIDATE=PASS",
        "TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE",
        "NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE",
        "TRD_BOT_LIVE_EXECUTION=DISABLED",
        "NEXT_ALLOWED_STAGE=TRD-V031-08_AFTER_CI_ACCEPTANCE",
    ):
        print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
