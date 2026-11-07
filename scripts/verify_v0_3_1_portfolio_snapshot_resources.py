#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-portfolio-snapshot-resources.json"
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"
SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/portfolio-snapshot-resources.schema.json"
PREVIOUS_FREEZE_PATH = ROOT / "artifacts/v0.3.1/trd-v031-02-snapshot-protocol-freeze.json"
CONTRACT_CHECKSUM = "ba47facd32990e9e8b8644eec0b2d513a655b6b504eb1c6a26685b948da6d981"
SCHEMA_CHECKSUM = "5a523d248e20bad484cfdf6ff5b5b31501237e9e7d3f45a3a056e3db9e557fa5"
PREVIOUS_FREEZE_CHECKSUM = "51c681b89cdae8e16837a8310441266a3cbb98e57d2bf6bdd753e917068a1ee2"
PREVIOUS_FREEZE_COMMIT = "b4d5fb62dabffd8e74257d5b3e10148a191395a3"
EXPECTED_RESOURCES = (
    "paper_shadow_portfolio",
    "paper_shadow_position",
    "portfolio_intelligence",
    "simulation_outcome",
)
EXPECTED_SCHEMA_VERSIONS = {
    "paper_shadow_portfolio": "trd-bot-paper-shadow-portfolio-v1",
    "paper_shadow_position": "trd-bot-paper-shadow-position-v1",
    "portfolio_intelligence": "trd-bot-portfolio-intelligence-v1",
    "simulation_outcome": "trd-bot-simulation-outcome-v1",
}


class V031PortfolioSnapshotError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031PortfolioSnapshotError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return load_json(path)


def load_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    return load_json(path)


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    return load_json(path)


def load_previous_freeze(path: Path = PREVIOUS_FREEZE_PATH) -> dict[str, Any]:
    return load_json(path)


def validate_previous_freeze(record: dict[str, Any]) -> None:
    require(
        canonical_checksum(record) == PREVIOUS_FREEZE_CHECKSUM,
        "V031-02 Freeze artifact drift",
    )
    require(record.get("decision_id") == "TRD-V031-02", "previous Freeze decision drift")
    require(record.get("status") == "frozen" and record.get("frozen") is True, "V031-02 open")
    transition = record.get("transition")
    require(isinstance(transition, dict), "V031-02 Freeze transition missing")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-03",
        "V031-03 gate is not open",
    )


def validate_contract(
    contract: dict[str, Any],
    profile: dict[str, Any],
    *,
    expected_checksum: str = CONTRACT_CHECKSUM,
) -> None:
    require(canonical_checksum(contract) == expected_checksum, "V031-03 stage contract drift")
    require(
        contract.get("schema_version") == "trd-bot-v031-portfolio-snapshot-resources-v1",
        "stage schema drift",
    )
    require(contract.get("decision_id") == "TRD-V031-03", "stage decision drift")
    require(contract.get("status") == "candidate", "stage must remain candidate before Freeze")
    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "stage prerequisite must be an object")
    require(prerequisite.get("frozen") is True, "V031-02 must be frozen")
    require(
        prerequisite.get("freeze_commit_sha") == PREVIOUS_FREEZE_COMMIT,
        "V031-02 Freeze commit drift",
    )

    endpoint = contract.get("endpoint")
    require(isinstance(endpoint, dict), "snapshot endpoint must be an object")
    require(endpoint.get("method") == "GET", "snapshot method drift")
    require(
        endpoint.get("path") == "/api/v1/integration/nexora/snapshots/{resource_type}",
        "snapshot path drift",
    )
    require(endpoint.get("authentication") == "bearer_service_token", "authentication drift")
    require(endpoint.get("cursor_expired_status") == 410, "cursor expiry status drift")
    require(
        endpoint.get("cursor_expired_action") == "full_snapshot_resync",
        "cursor expiry action drift",
    )

    resources = contract.get("resources")
    require(isinstance(resources, dict), "portfolio resources must be an object")
    require(tuple(resources.get("allowlist", ())) == EXPECTED_RESOURCES, "resource allowlist drift")
    require(resources.get("schema_versions") == EXPECTED_SCHEMA_VERSIONS, "schema versions drift")
    snapshot_groups = profile.get("snapshot_groups")
    require(isinstance(snapshot_groups, dict), "provider snapshot groups missing")
    require(
        tuple(snapshot_groups.get("portfolio", ())) == EXPECTED_RESOURCES,
        "provider portfolio resources drift",
    )
    for key in (
        "source_reference_required",
        "source_checksum_required",
        "deterministic_ascending_order",
        "scan_time_boundary_required",
    ):
        require(resources.get(key) is True, f"resource invariant disabled: {key}")

    safety = contract.get("safety")
    require(isinstance(safety, dict), "safety boundary must be an object")
    for key in ("paper_shadow_only", "offline_only_required"):
        require(safety.get(key) is True, f"safety invariant disabled: {key}")
    for key in (
        "external_order_submission_allowed",
        "exchange_credentials_allowed",
        "service_token_in_payload_allowed",
        "service_token_in_cursor_allowed",
        "direct_database_access_for_consumer",
    ):
        require(safety.get(key) is False, f"unsafe capability enabled: {key}")

    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "persistence boundary must be an object")
    require(persistence.get("uses_existing_snapshot_scan_store") is True, "scan store disabled")
    require(persistence.get("migration_added") is False, "unexpected migration added")
    require(persistence.get("migration_head") == "20261106_0037", "migration head drift")

    scope = contract.get("scope")
    require(isinstance(scope, dict), "stage scope must be an object")
    for key in (
        "snapshot_http_endpoint_registered",
        "portfolio_snapshot_resources_added",
        "paper_shadow_portfolio_added",
        "paper_shadow_position_added",
        "portfolio_intelligence_added",
        "simulation_outcome_added",
    ):
        require(scope.get(key) is True, f"required scope disabled: {key}")
    for key in (
        "decision_snapshot_resources_added",
        "alert_snapshot_resources_added",
        "event_feed_added",
        "review_commands_added",
        "export_protocol_added",
        "release_version_bumped",
        "provider_compatibility_claimed",
        "nexora_p3_03_opened",
        "live_execution_enabled",
    ):
        require(scope.get(key) is False, f"premature scope claim: {key}")

    transition = contract.get("transition")
    require(isinstance(transition, dict), "stage transition must be an object")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-03-FREEZE",
        "candidate may only advance to its Freeze",
    )
    require(transition.get("post_freeze_stage") == "TRD-V031-04", "post-Freeze stage drift")


def validate_schema(schema: dict[str, Any], *, expected_checksum: str = SCHEMA_CHECKSUM) -> None:
    require(canonical_checksum(schema) == expected_checksum, "portfolio resource schema drift")
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "portfolio schema definitions missing")
    for resource_type, schema_version in EXPECTED_SCHEMA_VERSIONS.items():
        definition = definitions.get(resource_type)
        require(isinstance(definition, dict), f"resource schema missing: {resource_type}")
        properties = definition.get("properties")
        require(isinstance(properties, dict), f"resource properties missing: {resource_type}")
        version = properties.get("resource_schema_version")
        require(
            isinstance(version, dict) and version.get("const") == schema_version,
            f"resource schema version drift: {resource_type}",
        )
        require(properties.get("offline_only") == {"const": True}, "offline boundary drift")
        require(
            properties.get("external_order_submission_allowed") == {"const": False},
            "external order boundary drift",
        )
    serialized = json.dumps(schema, sort_keys=True).casefold()
    for forbidden in ("service_token", "authorization", "exchange_credential", "api_secret"):
        require(forbidden not in serialized, f"forbidden schema field: {forbidden}")


def validate_implementation_sources() -> None:
    reader = (ROOT / "src/trd_bot/integration/nexora/portfolio_snapshots.py").read_text(
        encoding="utf-8"
    )
    routes = (ROOT / "src/trd_bot/integration/nexora/routes.py").read_text(encoding="utf-8")
    for marker in (
        "class PortfolioSnapshotResourceReader",
        "PORTFOLIO_SNAPSHOT_RESOURCE_TYPES",
        "RESOURCE_SCHEMA_VERSIONS",
        "external_order_submission_allowed",
    ):
        require(marker in reader, f"portfolio resource implementation missing: {marker}")
    for marker in (
        '"/snapshots/{resource_type}"',
        "SnapshotCursorExpiredError",
        "HTTP_410_GONE",
        'headers["Cache-Control"] = "private, no-store"',
    ):
        require(marker in routes, f"snapshot route implementation missing: {marker}")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    require(pyproject["project"]["version"] == "0.3.0", "release version advanced early")
    migrations = sorted(path.name for path in (ROOT / "alembic/versions").glob("*.py"))
    require(
        migrations[-1] == "20261106_0037_nexora_snapshot_protocol.py",
        "unexpected migration added",
    )


def main() -> int:
    validate_previous_freeze(load_previous_freeze())
    validate_contract(load_contract(), load_profile())
    validate_schema(load_schema())
    validate_implementation_sources()
    print("TRD_V031_03_PORTFOLIO_RESOURCE_ALLOWLIST=PASS")
    print("TRD_V031_03_STABLE_PAGING=PASS")
    print("TRD_V031_03_SOURCE_REFERENCE_CHECKSUM=PASS")
    print("TRD_V031_03_AUTHENTICATED_ENDPOINT=PASS")
    print("TRD_V031_03_DATABASE_MIGRATION=NONE")
    print("TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    print("NEXT_ALLOWED_STAGE=TRD-V031-03-FREEZE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
