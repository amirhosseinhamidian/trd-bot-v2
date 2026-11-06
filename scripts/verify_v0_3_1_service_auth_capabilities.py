#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-service-auth-capabilities.json"
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"
FREEZE_PATH = ROOT / "artifacts/v0.3.1/trd-v031-01-service-auth-capabilities-freeze.json"
AUTH_PATH = ROOT / "src/trd_bot/integration/nexora/auth.py"
ROUTES_PATH = ROOT / "src/trd_bot/integration/nexora/routes.py"
MAIN_PATH = ROOT / "src/trd_bot/main.py"
CONFIG_PATH = ROOT / "src/trd_bot/core/config.py"

CANDIDATE_COMMIT = "8020a31e0caede35461c7f5684e82b06bda4bb35"
CANDIDATE_TREE = "5c625cac1b92cbc825c2dc661839e045280eb160"
PARENT_FREEZE_COMMIT = "7b878dec891f5cd6e540a58cdeab2bc458214491"
CONTRACT_CHECKSUM = "92ce5484436bf27a02d092d6670a71117c6255f46e324a7ce6864741bc84aeca"
FREEZE_CHECKSUM = "86415f16cc21cf0650916fb201cecc0b5ff397cd090c81038e7ddfa519ed3251"
RELEASE_INVENTORY_CHECKSUM = "084f1a8a2507907ed0360e75718df1b91b6de96dfc522ffd62f30c6dba86cb4b"

EXPECTED_IMPLEMENTATION_FILES = {
    ".env.example": "6792591b5fbd38fc702b84b3ab267b9b4cf1679bc283a8298b5742f56ae8ea88",
    "src/trd_bot/core/config.py": (
        "f416d40833d1a6a01df8bdd45c3a67180ab19d8c6b5a622ce25785fa412df945"
    ),
    "src/trd_bot/integration/nexora/auth.py": (
        "4a4dde58faab4aeae7231db4f5201ff4834220b53de140dfe20d700f3f098ddf"
    ),
    "src/trd_bot/integration/nexora/contracts.py": (
        "4191434e7c66d16e7688f87eccf7041335009d3cfc2c3a6a5b78085cfb2bf8bc"
    ),
    "src/trd_bot/integration/nexora/routes.py": (
        "611ec8fd8ef2351ad3a38041f52b2a4acb375fb0378067f512fd69269e1cb17e"
    ),
    "src/trd_bot/main.py": "fe95df5c6445e533a55b9099d3d986fadaa622d5323cc94410b8f371b5b1d675",
    "tests/test_nexora_integration_capabilities.py": (
        "efa8c95c5e8d84cf69189719a3bc8d5b761fe47a17b6cfff23dc8852d4f8302e"
    ),
    "tests/test_release_hardening.py": (
        "a2099688a71f6501f5f7a26126cf32b01a53bf6b00bf770fe0bf40bf043ca726"
    ),
}

EXPECTED_CAPABILITIES = {
    "contract_versions": ["nexora-trd-integration-v1"],
    "event_envelopes": ["trd-integration-event-envelope-v1"],
    "export_manifests": ["nexora-export-manifest-v1"],
    "source_references": ["nexora-source-reference-v1"],
    "commands": [
        "decision_review.accept.v1",
        "decision_review.reject.v1",
        "decision_review.defer.v1",
    ],
}


class V031ServiceBoundaryError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031ServiceBoundaryError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return load_json(path)


def load_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    return load_json(path)


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return load_json(path)


def validate_freeze_record(record: dict[str, Any], contract: dict[str, Any]) -> None:
    require(canonical_checksum(record) == FREEZE_CHECKSUM, "V031-01 Freeze artifact drift")
    require(
        record.get("schema_version") == "trd-bot-v031-service-auth-capabilities-freeze-v1",
        "Freeze schema drift",
    )
    require(record.get("decision_id") == "TRD-V031-01", "Freeze decision drift")
    require(record.get("status") == "frozen" and record.get("frozen") is True, "stage not frozen")
    require(record.get("repository") == "amirhosseinhamidian/trd-bot-v2", "repository drift")
    require(record.get("branch") == "feature/v0.3.1-nexora-integration", "branch drift")
    require(record.get("candidate_commit_sha") == CANDIDATE_COMMIT, "Freeze candidate drift")
    require(record.get("candidate_tree_sha") == CANDIDATE_TREE, "Freeze candidate tree drift")
    require(
        record.get("parent_freeze_commit_sha") == PARENT_FREEZE_COMMIT,
        "parent Freeze commit drift",
    )
    require(
        record.get("candidate_commit_message")
        == "feat(trd-bot): add Nexora service auth and capabilities",
        "candidate message drift",
    )

    stage_contract = record.get("stage_contract")
    require(isinstance(stage_contract, dict), "Freeze stage contract must be an object")
    require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "frozen stage contract drift")
    require(
        stage_contract.get("path") == "contracts/trd-bot-v0.3.1-service-auth-capabilities.json",
        "Freeze stage contract path drift",
    )
    require(
        stage_contract.get("canonical_checksum") == CONTRACT_CHECKSUM,
        "Freeze stage contract checksum drift",
    )

    implementation = record.get("implementation")
    require(isinstance(implementation, dict), "Freeze implementation must be an object")
    require(implementation.get("provider_version") == "0.3.0", "provider version advanced early")
    require(
        implementation.get("release_inventory_checksum") == RELEASE_INVENTORY_CHECKSUM,
        "release inventory checksum drift",
    )
    files = implementation.get("files_sha256")
    require(isinstance(files, dict), "Freeze implementation file checksums must be an object")
    require(files == EXPECTED_IMPLEMENTATION_FILES, "Freeze implementation inventory drift")
    # These checksums identify the accepted historical candidate. Later stages may
    # extend these files while the immutable Git candidate remains reproducible.

    workflows = record.get("workflows")
    require(isinstance(workflows, dict), "Freeze workflows must be an object")
    require(
        set(workflows) == {"integration_roadmap", "service_auth_capabilities", "ci"},
        "Freeze workflow inventory drift",
    )
    expected_runs = {
        "integration_roadmap": 42032113701,
        "service_auth_capabilities": 42032113793,
        "ci": 42032113886,
    }
    expected_jobs = {
        "integration_roadmap": {
            "v0.3.1 integration roadmap contract": 127260890601,
        },
        "service_auth_capabilities": {
            "v0.3.1 service auth and capabilities": 127260890861,
        },
        "ci": {
            "Frontend quality, tests, and build": 127260891573,
            "Backend quality and tests": 127260891680,
            "PostgreSQL migrations and integration tests": 127260891055,
        },
    }
    for workflow_name, run_id in expected_runs.items():
        workflow = workflows.get(workflow_name)
        require(isinstance(workflow, dict), f"Freeze workflow missing: {workflow_name}")
        require(workflow.get("run_id") == run_id, f"Freeze workflow run drift: {workflow_name}")
        require(workflow.get("run_attempt") == 1, f"Freeze workflow attempt drift: {workflow_name}")
        require(workflow.get("event") == "push", f"Freeze workflow event drift: {workflow_name}")
        require(
            workflow.get("status") == "completed",
            f"Freeze workflow incomplete: {workflow_name}",
        )
        require(workflow.get("conclusion") == "success", f"Freeze workflow failed: {workflow_name}")
        jobs = workflow.get("jobs")
        require(isinstance(jobs, dict), f"Freeze jobs missing: {workflow_name}")
        require(
            set(jobs) == set(expected_jobs[workflow_name]),
            f"Freeze job inventory drift: {workflow_name}",
        )
        for job_name, job_id in expected_jobs[workflow_name].items():
            job = jobs.get(job_name)
            require(isinstance(job, dict), f"Freeze job missing: {job_name}")
            require(job.get("job_id") == job_id, f"Freeze job ID drift: {job_name}")
            require(job.get("status") == "completed", f"Freeze job incomplete: {job_name}")
            require(job.get("conclusion") == "success", f"Freeze job failed: {job_name}")

    acceptance = record.get("acceptance")
    require(isinstance(acceptance, dict), "Freeze acceptance must be an object")
    require(acceptance.get("failed_workflows") == [], "Freeze contains failed workflows")
    for key in (
        "stage_contract_frozen",
        "service_authentication_frozen",
        "constant_time_comparison_frozen",
        "absolute_private_token_file_frozen",
        "loopback_and_https_transport_boundary_frozen",
        "browser_token_delivery_forbidden",
        "capability_matrix_frozen",
        "response_version_headers_frozen",
        "correlation_id_boundary_frozen",
        "runtime_behavior_added",
        "version_0_3_0_remains_incompatible",
    ):
        require(acceptance.get(key) is True, f"Freeze acceptance invariant disabled: {key}")
    for key in (
        "database_migration_added",
        "release_version_bumped",
        "provider_compatibility_claimed",
        "real_provider_smoke_passed",
        "nexora_p3_03_opened",
        "snapshot_protocol_added",
        "live_execution_enabled",
        "exchange_credentials_added",
        "production_readiness_claimed",
    ):
        require(acceptance.get(key) is False, f"premature Freeze claim: {key}")

    transition = record.get("transition")
    require(isinstance(transition, dict), "Freeze transition must be an object")
    require(transition.get("next_allowed_stage") == "TRD-V031-02", "post-Freeze stage drift")
    require(
        transition.get("next_stage_title") == "Stable snapshot protocol and source references",
        "post-Freeze stage title drift",
    )
    require(
        transition.get("nexora_stage_remains_blocked_until") == "compatible_real_provider_smoke",
        "Nexora P3-03 opened before real provider smoke",
    )


def validate_contract(contract: dict[str, Any], profile: dict[str, Any]) -> None:
    require(
        contract.get("schema_version") == "trd-bot-v031-service-auth-capabilities-v1",
        "stage schema drift",
    )
    require(contract.get("decision_id") == "TRD-V031-01", "stage decision drift")
    require(contract.get("status") == "candidate", "stage must remain candidate before Freeze")

    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "prerequisite must be an object")
    require(prerequisite.get("decision_id") == "TRD-V031-00", "prerequisite decision drift")
    require(
        prerequisite.get("freeze_commit_sha") == "7b878dec891f5cd6e540a58cdeab2bc458214491",
        "roadmap Freeze commit drift",
    )
    require(prerequisite.get("frozen") is True, "roadmap prerequisite is not frozen")

    runtime = contract.get("runtime")
    require(isinstance(runtime, dict), "runtime must be an object")
    require(runtime.get("api_namespace") == "/api/v1/integration/nexora", "namespace drift")
    require(
        runtime.get("capabilities_endpoint") == "/api/v1/integration/nexora/capabilities",
        "capabilities endpoint drift",
    )
    require(runtime.get("provider_release_during_stage") == "0.3.0", "provider version drift")
    require(runtime.get("provider_compatibility_claimed") is False, "compatibility claimed early")
    require(runtime.get("database_migration_added") is False, "unexpected migration claim")

    authentication = contract.get("service_authentication")
    require(isinstance(authentication, dict), "service authentication must be an object")
    expected_authentication = {
        "scheme": "bearer_service_token",
        "provider_file_environment_variable": "TRD_BOT_NEXORA_SERVICE_TOKEN_FILE",
        "token_source": "absolute_private_regular_file",
        "minimum_token_bytes": 32,
        "maximum_token_bytes": 4096,
        "constant_time_comparison": True,
        "symbolic_links_allowed": False,
        "group_or_other_permissions_allowed": False,
        "missing_or_invalid_status": 401,
        "unavailable_or_unsafe_configuration_status": 503,
        "production_transport": "https",
        "development_http_scope": "loopback_only",
        "browser_cors_delivery_allowed": False,
        "token_in_query_cookie_log_payload_or_export_allowed": False,
    }
    require(authentication == expected_authentication, "service authentication policy drift")

    response = contract.get("response_contract")
    require(isinstance(response, dict), "response contract must be an object")
    profile_capabilities = profile.get("capability_negotiation")
    require(isinstance(profile_capabilities, dict), "frozen capability profile is missing")
    for key, expected in EXPECTED_CAPABILITIES.items():
        require(response.get(key) == expected, f"stage {key} drift")
        require(profile_capabilities.get(key) == expected, f"frozen profile {key} drift")
    require(response.get("cache_ttl_seconds") == 300, "capability cache TTL drift")
    require(
        response.get("schema_version") == "nexora-integration-capabilities-v1",
        "capability schema drift",
    )

    scope = contract.get("scope")
    require(isinstance(scope, dict), "scope must be an object")
    for forbidden in (
        "snapshot_endpoints_added",
        "event_endpoints_added",
        "command_endpoints_added",
        "export_endpoints_added",
        "live_execution_enabled",
        "exchange_credentials_added",
        "wallet_or_fund_transfer_enabled",
        "nexora_p3_03_opened",
    ):
        require(scope.get(forbidden) is False, f"forbidden scope enabled: {forbidden}")

    acceptance = contract.get("acceptance")
    require(isinstance(acceptance, dict), "acceptance must be an object")
    require(acceptance.get("release_0_3_0_remains_incompatible") is True, "0.3.0 gate drift")
    require(acceptance.get("real_provider_smoke_completed") is False, "real smoke claimed early")
    require(acceptance.get("production_readiness_claimed") is False, "production claimed early")

    transition = contract.get("transition")
    require(isinstance(transition, dict), "transition must be an object")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-01-FREEZE",
        "next stage drift",
    )


def validate_implementation_sources() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    require(pyproject["project"]["version"] == "0.3.0", "release version advanced early")
    package = (ROOT / "src/trd_bot/__init__.py").read_text(encoding="utf-8")
    require('__version__ = "0.3.0"' in package, "runtime version advanced early")

    auth = AUTH_PATH.read_text(encoding="utf-8")
    require("hmac.compare_digest" in auth, "constant-time comparison missing")
    require("path.is_absolute()" in auth, "absolute token-file check missing")
    require("os.O_NOFOLLOW" in auth, "symbolic-link-safe open missing")
    require("stat.S_IRWXG | stat.S_IRWXO" in auth, "private permission check missing")

    routes = ROUTES_PATH.read_text(encoding="utf-8")
    require('"/capabilities"' in routes, "capabilities route missing")
    require("X-Contract-Version" in routes, "contract response header missing")
    require("X-Correlation-ID" in routes, "correlation response header missing")
    require("X-TRD-Bot-Version" in routes, "provider response header missing")
    require("_is_loopback_host" in routes, "loopback transport guard missing")

    config = CONFIG_PATH.read_text(encoding="utf-8")
    require("nexora_service_token_file: Path | None" in config, "token-file setting missing")
    main = MAIN_PATH.read_text(encoding="utf-8")
    require("nexora_integration_router" in main, "Nexora router is not mounted")
    require('prefix="/api/v1/integration/nexora"' in main, "Nexora namespace drift")


def main() -> int:
    contract = load_contract()
    profile = load_profile()
    freeze = load_freeze_record()
    validate_contract(contract, profile)
    validate_implementation_sources()
    validate_freeze_record(freeze, contract)
    print("TRD_V031_01_SERVICE_AUTHENTICATION=PASS")
    print("TRD_V031_01_CAPABILITY_NEGOTIATION=PASS")
    print("TRD_V031_01_CONSTANT_TIME_COMPARISON=PASS")
    print("TRD_V031_01_TRANSPORT_BOUNDARY=PASS")
    print("TRD_V031_01_FREEZE=PASS")
    print("TRD_V031_01_DATABASE_MIGRATION=NONE")
    print("TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    print("NEXT_ALLOWED_STAGE=TRD-V031-02")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
