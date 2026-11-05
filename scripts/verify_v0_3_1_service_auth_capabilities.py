#!/usr/bin/env python3
from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-service-auth-capabilities.json"
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"
AUTH_PATH = ROOT / "src/trd_bot/integration/nexora/auth.py"
ROUTES_PATH = ROOT / "src/trd_bot/integration/nexora/routes.py"
MAIN_PATH = ROOT / "src/trd_bot/main.py"
CONFIG_PATH = ROOT / "src/trd_bot/core/config.py"

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


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return load_json(path)


def load_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    return load_json(path)


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
    validate_contract(contract, profile)
    validate_implementation_sources()
    print("TRD_V031_01_SERVICE_AUTHENTICATION=PASS")
    print("TRD_V031_01_CAPABILITY_NEGOTIATION=PASS")
    print("TRD_V031_01_CONSTANT_TIME_COMPARISON=PASS")
    print("TRD_V031_01_TRANSPORT_BOUNDARY=PASS")
    print("TRD_V031_01_DATABASE_MIGRATION=NONE")
    print("TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    print("NEXT_ALLOWED_STAGE=TRD-V031-01-FREEZE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
