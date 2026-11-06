#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-snapshot-protocol.json"
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"
SOURCE_REFERENCE_SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/source-reference.schema.json"
SNAPSHOT_PAGE_SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/snapshot-page.schema.json"
PREVIOUS_FREEZE_PATH = ROOT / "artifacts/v0.3.1/trd-v031-01-service-auth-capabilities-freeze.json"
CONTRACT_CHECKSUM = "346d0eb986027634621a4a2dff9a2759469d43233880976648129a397a5975fe"
SOURCE_REFERENCE_SCHEMA_CHECKSUM = (
    "2e24b051c69f97735aacb6c328c96e4b0c16a1ee6d36962c6500cc31a2b053dd"
)
SNAPSHOT_PAGE_SCHEMA_CHECKSUM = "c892c38978222005a64295be084de215875abc913647a4a54fc8ccfec059a85c"
PREVIOUS_FREEZE_COMMIT = "ef45640c5bb4b1458668635404c610d776b882f7"


class V031SnapshotProtocolError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031SnapshotProtocolError(message)


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


def load_source_reference_schema(path: Path = SOURCE_REFERENCE_SCHEMA_PATH) -> dict[str, Any]:
    return load_json(path)


def load_snapshot_page_schema(path: Path = SNAPSHOT_PAGE_SCHEMA_PATH) -> dict[str, Any]:
    return load_json(path)


def validate_stage_contract(
    contract: dict[str, Any], profile: dict[str, Any], *, expected_checksum: str = CONTRACT_CHECKSUM
) -> None:
    require(canonical_checksum(contract) == expected_checksum, "V031-02 stage contract drift")
    require(
        contract.get("schema_version") == "trd-bot-v031-snapshot-protocol-v1", "stage schema drift"
    )
    require(contract.get("decision_id") == "TRD-V031-02", "stage decision drift")
    require(contract.get("status") == "candidate", "stage must remain a candidate before Freeze")
    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "stage prerequisite must be an object")
    require(
        prerequisite.get("freeze_commit_sha") == PREVIOUS_FREEZE_COMMIT,
        "V031-01 Freeze commit drift",
    )
    require(prerequisite.get("frozen") is True, "V031-01 must be frozen")
    protocol = contract.get("protocol")
    require(isinstance(protocol, dict), "snapshot protocol must be an object")
    expected = profile.get("snapshot_protocol")
    require(isinstance(expected, dict), "provider snapshot profile must be an object")
    require(
        protocol.get("page_schema_version") == expected.get("page_schema_version"),
        "snapshot page schema drift",
    )
    require(protocol.get("default_page_limit") == 100, "default page limit drift")
    require(protocol.get("maximum_page_limit") == 500, "maximum page limit drift")
    require(protocol.get("cursor") == "opaque_stable_cursor", "cursor mode drift")
    require(protocol.get("cursor_contains_credentials") is False, "cursor leaks credentials")
    require(protocol.get("continuation_reuses_high_watermark") is True, "scan is unstable")
    require(protocol.get("expired_cursor_status") == 410, "expired cursor status drift")
    require(
        protocol.get("expired_cursor_action") == "full_snapshot_resync",
        "expired cursor action drift",
    )
    require(protocol.get("silent_cursor_reset_allowed") is False, "silent reset enabled")
    source = contract.get("source_reference")
    require(isinstance(source, dict), "source reference must be an object")
    require(source.get("checksum_algorithm") == "sha256", "checksum weakened")
    require(source.get("every_item_requires_reference") is True, "lineage disabled")
    persistence = contract.get("persistence")
    require(isinstance(persistence, dict), "snapshot persistence must be an object")
    require(persistence.get("migration_revision") == "20261106_0037", "migration drift")
    scope = contract.get("scope")
    require(isinstance(scope, dict), "stage scope must be an object")
    for key in (
        "generic_snapshot_protocol_added",
        "source_reference_contract_added",
        "durable_scan_cursor_store_added",
    ):
        require(scope.get(key) is True, f"required scope disabled: {key}")
    for key in (
        "snapshot_http_endpoint_registered",
        "portfolio_snapshot_resources_added",
        "decision_snapshot_resources_added",
        "alert_snapshot_resources_added",
        "event_feed_added",
        "release_version_bumped",
        "provider_compatibility_claimed",
        "nexora_p3_03_opened",
        "live_execution_enabled",
    ):
        require(scope.get(key) is False, f"premature scope claim: {key}")
    transition = contract.get("transition")
    require(isinstance(transition, dict), "stage transition must be an object")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-02-FREEZE",
        "candidate may only advance to its Freeze",
    )
    require(transition.get("post_freeze_stage") == "TRD-V031-03", "post-Freeze stage drift")


def validate_schemas(source: dict[str, Any], page: dict[str, Any]) -> None:
    require(
        canonical_checksum(source) == SOURCE_REFERENCE_SCHEMA_CHECKSUM,
        "source-reference schema drift",
    )
    require(canonical_checksum(page) == SNAPSHOT_PAGE_SCHEMA_CHECKSUM, "snapshot-page schema drift")
    require(
        source.get("properties", {}).get("checksum", {}).get("pattern") == r"^sha256:[0-9a-f]{64}$",
        "checksum schema drift",
    )
    require(
        page.get("properties", {}).get("schema_version", {}).get("const")
        == "nexora-source-snapshot-page-v1",
        "snapshot page version drift",
    )


def validate_previous_freeze() -> None:
    freeze = load_json(PREVIOUS_FREEZE_PATH)
    require(freeze.get("status") == "frozen" and freeze.get("frozen") is True, "V031-01 open")
    transition = freeze.get("transition")
    require(
        isinstance(transition, dict) and transition.get("next_allowed_stage") == "TRD-V031-02",
        "V031-02 gate is not open",
    )


def validate_implementation_sources() -> None:
    paths = [
        ROOT / "src/trd_bot/integration/nexora/snapshots.py",
        ROOT / "src/trd_bot/db/nexora_snapshot_scans.py",
        ROOT / "src/trd_bot/db/models.py",
        ROOT / "alembic/versions/20261106_0037_nexora_snapshot_protocol.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for marker in (
        "class SourceReference",
        "class SnapshotPage",
        "class StableSnapshotPager",
        "class SqlAlchemyNexoraSnapshotScanStore",
        "nexora_snapshot_scans",
        "nexora_snapshot_cursors",
    ):
        require(marker in combined, f"snapshot implementation missing: {marker}")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    require(pyproject["project"]["version"] == "0.3.0", "release version advanced early")


def main() -> int:
    validate_stage_contract(load_contract(), load_profile())
    validate_schemas(load_source_reference_schema(), load_snapshot_page_schema())
    validate_previous_freeze()
    validate_implementation_sources()
    print("TRD_V031_02_STABLE_SCAN_BOUNDARY=PASS")
    print("TRD_V031_02_OPAQUE_CURSOR=PASS")
    print("TRD_V031_02_DETERMINISTIC_PAGING=PASS")
    print("TRD_V031_02_SOURCE_REFERENCE_CHECKSUM=PASS")
    print("TRD_V031_02_DATABASE_MIGRATION=20261106_0037")
    print("TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    print("NEXT_ALLOWED_STAGE=TRD-V031-02-FREEZE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
