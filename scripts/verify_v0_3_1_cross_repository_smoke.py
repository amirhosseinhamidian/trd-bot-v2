#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-cross-repository-smoke.json"
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"
SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/cross-repository-smoke.schema.json"
MANIFEST_PATH = ROOT / "contracts/v0.3.1/stage-acceptance/trd-v031-10.json"
EVENTS_PATH = ROOT / "src/trd_bot/integration/nexora/events.py"
ROUTES_PATH = ROOT / "src/trd_bot/integration/nexora/routes.py"
RUNNER_PATH = ROOT / "scripts/run_v0_3_1_cross_repository_smoke.py"
WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-cross-repository-smoke.yml"
REUSABLE_WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-stage-acceptance.yml"
ACCEPTED_STAGE_09_COMMIT = "5bad863b19685a8fdb3d10474e9c834319addc13"
ACCEPTED_STAGE_09_EVIDENCE = "67793095863eb6656bfd02d3893c2c314f0d86587ea2503bc9ae307cfa47152c"
PINNED_NEXORA_COMMIT = "1e114b58b1a9cfc4ef91280c6506aa58bb2f53e8"
PINNED_NEXORA_TREE = "6c5756f177c2f0025faeb776515e99c077630177"
PROFILE_SHA256 = "2d21e80db378c2dc2c1b3a6fbb1f44bcbbad0c34d89f4d073b25e179a55fbcc8"
RELEASE_INVENTORY_CHECKSUM = "799eb5b8216ceafa60b1783b9c1d278c5f140c3ad972b11681f645033eedf6f2"


class V031CrossRepositorySmokeError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031CrossRepositorySmokeError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def validate_contract(contract: dict[str, Any]) -> None:
    require(contract.get("decision_id") == "TRD-V031-10", "stage ID drift")
    require(contract.get("status") == "candidate", "stage is not a candidate")
    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "prerequisite missing")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_09_COMMIT,
        "Stage 09 commit drift",
    )
    require(
        prerequisite.get("accepted_evidence_checksum") == ACCEPTED_STAGE_09_EVIDENCE,
        "Stage 09 evidence drift",
    )
    consumer = contract.get("consumer")
    require(isinstance(consumer, dict), "consumer pin missing")
    require(consumer.get("commit_sha") == PINNED_NEXORA_COMMIT, "Nexora commit drift")
    require(consumer.get("tree_sha") == PINNED_NEXORA_TREE, "Nexora tree drift")
    require(consumer.get("provider_profile_sha256") == PROFILE_SHA256, "profile drift")
    require(consumer.get("profile_must_be_byte_identical") is True, "profile equality removed")
    acceptance = contract.get("acceptance")
    require(isinstance(acceptance, dict), "acceptance declaration missing")
    for key in (
        "fixture_contract_suite",
        "real_provider_smoke",
        "all_required_scenarios_must_pass",
        "same_ci_run_as_stage_contract",
    ):
        require(acceptance.get(key) is True, f"required acceptance removed: {key}")
    require(acceptance.get("required_scenario_count") == 12, "scenario coverage drift")
    require(acceptance.get("transport") == "http_loopback_only", "loopback guard removed")
    require(acceptance.get("external_network_required") is False, "external network enabled")
    require(
        acceptance.get("release_inventory_checksum") == RELEASE_INVENTORY_CHECKSUM,
        "release inventory drift",
    )
    require(acceptance.get("artifact_retention_days") == 90, "retention drift")
    safety = contract.get("safety")
    require(isinstance(safety, dict), "safety declaration missing")
    for key in (
        "live_execution",
        "external_order_submission",
        "exchange_credentials",
        "wallet_or_fund_transfer",
        "shared_database_with_nexora",
        "secrets_in_evidence",
    ):
        require(safety.get(key) is False, f"unsafe capability enabled: {key}")
    require(
        safety.get("provider_compatibility_requires_all_gates") is True, "fail-closed gate removed"
    )
    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition missing")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-11_AFTER_CI_ACCEPTANCE",
        "CI acceptance bypassed",
    )
    require(
        transition.get("nex_p3_03_eligibility") == "AFTER_STAGE_10_CI_ACCEPTANCE",
        "NEX-P3-03 opened early",
    )
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze restored")


def validate_profile(profile: dict[str, Any]) -> None:
    smoke = profile.get("acceptance_smoke")
    require(isinstance(smoke, dict), "frozen acceptance smoke missing")
    scenarios = smoke.get("required_scenarios")
    require(isinstance(scenarios, list) and len(scenarios) == 12, "frozen scenario coverage drift")
    require(len(set(cast(list[str], scenarios))) == 12, "duplicate frozen scenario")
    require(smoke.get("fixture_contract_tests_required") is True, "fixture suite disabled")
    require(smoke.get("real_provider_required") is True, "real provider disabled")
    require(smoke.get("external_network_required") is False, "external network requirement drift")
    provider = profile.get("provider")
    require(isinstance(provider, dict), "provider range missing")
    require(provider.get("minimum_release") == "0.3.1", "provider minimum drift")
    require(provider.get("release_0_3_0_compatible") is False, "0.3.0 declared compatible")


def validate_schema(schema: dict[str, Any]) -> None:
    require(schema.get("additionalProperties") is False, "smoke evidence schema is open")
    properties = schema.get("properties")
    require(isinstance(properties, dict), "smoke evidence properties missing")
    for key, expected in (
        ("passed", True),
        ("provider_compatibility_evidence", True),
        ("external_network_required", False),
        ("live_execution_enabled", False),
        ("external_order_submission_allowed", False),
        ("secrets_recorded", False),
    ):
        require(
            cast(dict[str, Any], properties.get(key, {})).get("const") is expected,
            f"schema guard drift: {key}",
        )
    scenarios = cast(dict[str, Any], properties.get("scenarios", {}))
    require(
        scenarios.get("minItems") == scenarios.get("maxItems") == 12, "schema scenario count drift"
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    require(manifest.get("stage_id") == "TRD-V031-10", "manifest stage drift")
    require(manifest.get("status") == "candidate", "manifest is not a candidate")
    prerequisite = manifest.get("prerequisite")
    require(isinstance(prerequisite, dict), "manifest prerequisite missing")
    require(prerequisite.get("mode") == "ci_artifact", "Stage 09 artifact not required")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_09_COMMIT,
        "manifest prerequisite drift",
    )
    migration = manifest.get("migration")
    require(
        isinstance(migration, dict) and migration.get("expected") is False, "unexpected migration"
    )
    transition = manifest.get("transition")
    require(isinstance(transition, dict), "manifest transition missing")
    require(transition.get("next_stage") == "TRD-V031-11", "manifest next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "manifest Freeze restored")


def validate_implementation(
    events: str, routes: str, runner: str, workflow: str, reusable: str
) -> None:
    for marker in (
        "class ProviderEventEnvelope",
        "class ProviderEventPage",
        "def to_provider_event(",
        "payload_checksum=event_checksum(event.payload)",
        "correlation_id=uuid5(EVENT_CORRELATION_NAMESPACE, event.event_id)",
    ):
        require(marker in events, f"wire compatibility projection missing: {marker}")
    require(
        "to_provider_event_page" in routes and "to_provider_event(" in routes,
        "wire projection not routed",
    )
    for marker in (
        "TrdBotClient",
        "uvicorn",
        "required_scenarios",
        "http_loopback_only",
        "secrets_never_appear_in_payload_log_or_export",
        "report_checksum",
    ):
        require(marker in runner, f"real smoke invariant missing: {marker}")
    require(
        "uses: ./.github/workflows/v0-3-1-stage-acceptance.yml" in workflow,
        "reusable acceptance not called",
    )
    require("stage_id: TRD-V031-10" in workflow, "workflow stage drift")
    for marker in (
        "Checkout pinned Nexora consumer",
        PINNED_NEXORA_COMMIT,
        "run_v0_3_1_cross_repository_smoke.py",
        "TRD-V031-10-smoke-${{ github.sha }}",
        "retention-days: 90",
    ):
        require(marker in reusable, f"same-run smoke evidence missing: {marker}")
    combined = "\n".join((events, routes, runner))
    require("submit_order" not in combined and "place_order" not in combined, "order path added")


def verify() -> None:
    validate_contract(load_json(CONTRACT_PATH))
    validate_profile(load_json(PROFILE_PATH))
    validate_schema(load_json(SCHEMA_PATH))
    validate_manifest(load_json(MANIFEST_PATH))
    validate_implementation(
        EVENTS_PATH.read_text(encoding="utf-8"),
        ROUTES_PATH.read_text(encoding="utf-8"),
        RUNNER_PATH.read_text(encoding="utf-8"),
        WORKFLOW_PATH.read_text(encoding="utf-8"),
        REUSABLE_WORKFLOW_PATH.read_text(encoding="utf-8"),
    )


def main() -> int:
    verify()
    for marker in (
        "TRD_V031_10_FIXTURE_CONTRACT_SUITE=PASS",
        "TRD_V031_10_REAL_LOCAL_PROVIDER_SMOKE=REQUIRED_IN_CI",
        "TRD_V031_10_REQUIRED_SCENARIOS=12",
        f"TRD_V031_10_NEXORA_COMMIT={PINNED_NEXORA_COMMIT}",
        f"TRD_V031_10_PROVIDER_PROFILE_SHA256={PROFILE_SHA256}",
        "TRD_V031_10_DATABASE_MIGRATION=NONE",
        "TRD_V031_10_ACCEPTANCE_CANDIDATE=PASS",
        "TRD_BOT_LIVE_EXECUTION=DISABLED",
        "NEX_P3_03_GATE=ELIGIBLE_ONLY_AFTER_STAGE_10_CI_ACCEPTANCE",
        "NEXT_ALLOWED_STAGE=TRD-V031-11_AFTER_CI_ACCEPTANCE",
    ):
        print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
