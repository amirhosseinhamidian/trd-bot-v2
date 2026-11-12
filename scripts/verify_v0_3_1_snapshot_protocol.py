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
FREEZE_PATH = ROOT / "artifacts/v0.3.1/trd-v031-02-snapshot-protocol-freeze.json"
CANDIDATE_COMMIT = "8666b879600c06f376602c1f672ea570bf87f7ab"
CANDIDATE_TREE = "7cc5e8386f599badbdc9b0746d42d73e918ffdba"
PARENT_FREEZE_COMMIT = "ef45640c5bb4b1458668635404c610d776b882f7"
CONTRACT_CHECKSUM = "346d0eb986027634621a4a2dff9a2759469d43233880976648129a397a5975fe"
SOURCE_REFERENCE_SCHEMA_CHECKSUM = (
    "2e24b051c69f97735aacb6c328c96e4b0c16a1ee6d36962c6500cc31a2b053dd"
)
SNAPSHOT_PAGE_SCHEMA_CHECKSUM = "c892c38978222005a64295be084de215875abc913647a4a54fc8ccfec059a85c"
PREVIOUS_FREEZE_COMMIT = "ef45640c5bb4b1458668635404c610d776b882f7"
FREEZE_CHECKSUM = "51c681b89cdae8e16837a8310441266a3cbb98e57d2bf6bdd753e917068a1ee2"
RELEASE_INVENTORY_CHECKSUM = "4e778fed94a2b96c87d2a652aae61bd9a699d5f90b09e1eaf8182abbabb1866d"

EXPECTED_IMPLEMENTATION_FILES = {
    "alembic/versions/20261106_0037_nexora_snapshot_protocol.py": (
        "92c831b7a8dd6525b2892a72a9d310a014b09de22eb179d254ee38335fdbfbab"
    ),
    "contracts/integration/nexora/v1/snapshot-page.schema.json": (
        "04555d8ad54da2d67a5e03ab373134ca40af8fbcf96a06207818c572de06d1fd"
    ),
    "contracts/integration/nexora/v1/source-reference.schema.json": (
        "19279d9403a2041fa664e409476aaa53ad0f36ddb67de5b134dc587d74f0e91e"
    ),
    "contracts/trd-bot-v0.3.1-snapshot-protocol.json": (
        "e975674ccf1ad74738e85c567e2cd37869da7da83934bc3737494cacece4fd1f"
    ),
    "src/trd_bot/db/__init__.py": (
        "3be679b5f0ea84f520ecc129bc58330d10f645bbfc325d5bed9e1cf4a94b05ff"
    ),
    "src/trd_bot/db/models.py": "c4741c8521a67be38fd18b04ce5182a2f140f3cbec953f69754d7f62272464ec",
    "src/trd_bot/db/nexora_snapshot_scans.py": (
        "27b76b173eb52655b226de87830052a75005b43b027d841581beee988a381901"
    ),
    "src/trd_bot/integration/nexora/snapshots.py": (
        "91fa92a233b0d81d367d106fd52723f50d60b255d3df5f72b0f8a338630c3cd7"
    ),
    "tests/test_nexora_snapshot_persistence.py": (
        "6c1ff06f3223c0a1b3dc5b64f34d17357121acf501fb75ff03379e681fa1f4c7"
    ),
    "tests/test_nexora_snapshot_protocol.py": (
        "77f72d96a6221b5f9bfb41321339737eae5adcd38694c3da6c25907503e3331b"
    ),
    "tests/test_release_hardening.py": (
        "ef69a0f77ea1a4b29979b2fa210eec5db8a7088c77eb5c319ef046f9a6485453"
    ),
}


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


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
    return load_json(path)


def validate_freeze_record(
    record: dict[str, Any],
    contract: dict[str, Any],
    source_schema: dict[str, Any],
    page_schema: dict[str, Any],
    *,
    expected_checksum: str = FREEZE_CHECKSUM,
) -> None:
    require(canonical_checksum(record) == expected_checksum, "V031-02 Freeze artifact drift")
    require(
        record.get("schema_version") == "trd-bot-v031-snapshot-protocol-freeze-v1",
        "Freeze schema drift",
    )
    require(record.get("decision_id") == "TRD-V031-02", "Freeze decision drift")
    require(record.get("status") == "frozen" and record.get("frozen") is True, "stage not frozen")
    require(record.get("repository") == "amirhosseinhamidian/trd-bot-v2", "repository drift")
    require(record.get("branch") == "feature/v0.3.1-nexora-integration", "branch drift")
    require(record.get("candidate_commit_sha") == CANDIDATE_COMMIT, "Freeze candidate drift")
    require(record.get("candidate_tree_sha") == CANDIDATE_TREE, "Freeze candidate tree drift")
    require(
        record.get("parent_freeze_commit_sha") == PARENT_FREEZE_COMMIT, "parent Freeze commit drift"
    )
    require(
        record.get("candidate_commit_message")
        == "feat(trd-bot): add stable Nexora snapshot protocol",
        "candidate message drift",
    )

    stage_contract = record.get("stage_contract")
    require(isinstance(stage_contract, dict), "Freeze stage contract must be an object")
    require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "frozen stage contract drift")
    require(
        stage_contract.get("path") == "contracts/trd-bot-v0.3.1-snapshot-protocol.json",
        "Freeze stage contract path drift",
    )
    require(
        stage_contract.get("canonical_checksum") == CONTRACT_CHECKSUM,
        "Freeze stage contract checksum drift",
    )

    schemas = record.get("schemas")
    require(isinstance(schemas, dict), "Freeze schemas must be an object")
    expected_schemas = {
        "source_reference": (
            "contracts/integration/nexora/v1/source-reference.schema.json",
            SOURCE_REFERENCE_SCHEMA_CHECKSUM,
            source_schema,
        ),
        "snapshot_page": (
            "contracts/integration/nexora/v1/snapshot-page.schema.json",
            SNAPSHOT_PAGE_SCHEMA_CHECKSUM,
            page_schema,
        ),
    }
    require(set(schemas) == set(expected_schemas), "Freeze schema inventory drift")
    for name, (path, checksum, payload) in expected_schemas.items():
        item = schemas.get(name)
        require(isinstance(item, dict), f"Freeze schema missing: {name}")
        require(item.get("path") == path, f"Freeze schema path drift: {name}")
        require(item.get("canonical_checksum") == checksum, f"Freeze schema checksum drift: {name}")
        require(canonical_checksum(payload) == checksum, f"frozen schema drift: {name}")

    implementation = record.get("implementation")
    require(isinstance(implementation, dict), "Freeze implementation must be an object")
    require(implementation.get("provider_version") == "0.3.0", "provider version advanced early")
    require(implementation.get("migration_revision") == "20261106_0037", "migration drift")
    require(
        implementation.get("release_inventory_checksum") == RELEASE_INVENTORY_CHECKSUM,
        "release inventory checksum drift",
    )
    files = implementation.get("files_sha256")
    require(isinstance(files, dict), "Freeze implementation file checksums must be an object")
    require(files == EXPECTED_IMPLEMENTATION_FILES, "Freeze implementation inventory drift")
    # These hashes identify the immutable accepted candidate. Later stages may
    # extend these files without changing the historical Git candidate.

    workflows = record.get("workflows")
    require(isinstance(workflows, dict), "Freeze workflows must be an object")
    expected_runs = {
        "integration_roadmap": 42219343788,
        "service_auth_capabilities": 42219343619,
        "snapshot_protocol": 42219343720,
        "ci": 42219343764,
    }
    expected_jobs = {
        "integration_roadmap": {"v0.3.1 integration roadmap contract": 127897197128},
        "service_auth_capabilities": {"v0.3.1 service auth and capabilities": 127897196159},
        "snapshot_protocol": {"v0.3.1 stable snapshot protocol": 127897196301},
        "ci": {
            "Backend quality and tests": 127897196527,
            "PostgreSQL migrations and integration tests": 127897196835,
            "Frontend quality, tests, and build": 127897196862,
        },
    }
    require(set(workflows) == set(expected_runs), "Freeze workflow inventory drift")
    for workflow_name, run_id in expected_runs.items():
        workflow = workflows.get(workflow_name)
        require(isinstance(workflow, dict), f"Freeze workflow missing: {workflow_name}")
        require(workflow.get("run_id") == run_id, f"Freeze workflow run drift: {workflow_name}")
        require(workflow.get("run_attempt") == 1, f"Freeze workflow attempt drift: {workflow_name}")
        require(workflow.get("event") == "push", f"Freeze workflow event drift: {workflow_name}")
        require(
            workflow.get("status") == "completed", f"Freeze workflow incomplete: {workflow_name}"
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
        "stable_scan_boundary_frozen",
        "opaque_cursor_contract_frozen",
        "deterministic_paging_frozen",
        "source_reference_checksum_frozen",
        "durable_scan_cursor_store_frozen",
        "database_migration_added",
        "runtime_behavior_added",
        "version_0_3_0_remains_incompatible",
    ):
        require(acceptance.get(key) is True, f"Freeze acceptance invariant disabled: {key}")
    for key in (
        "snapshot_http_endpoint_registered",
        "portfolio_snapshot_resources_added",
        "decision_snapshot_resources_added",
        "alert_snapshot_resources_added",
        "release_version_bumped",
        "provider_compatibility_claimed",
        "real_provider_smoke_passed",
        "nexora_p3_03_opened",
        "live_execution_enabled",
        "production_readiness_claimed",
    ):
        require(acceptance.get(key) is False, f"premature Freeze claim: {key}")

    transition = record.get("transition")
    require(isinstance(transition, dict), "Freeze transition must be an object")
    require(transition.get("next_allowed_stage") == "TRD-V031-03", "post-Freeze stage drift")
    require(
        transition.get("next_stage_title") == "Portfolio snapshot resources",
        "post-Freeze stage title drift",
    )
    require(
        transition.get("nexora_stage_remains_blocked_until") == "compatible_real_provider_smoke",
        "Nexora P3-03 opened before real provider smoke",
    )


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
    require(pyproject["project"]["version"] in {"0.3.0", "0.3.1"}, "release version drift")


def main() -> int:
    contract = load_contract()
    source_schema = load_source_reference_schema()
    page_schema = load_snapshot_page_schema()
    validate_stage_contract(contract, load_profile())
    validate_schemas(source_schema, page_schema)
    validate_previous_freeze()
    validate_implementation_sources()
    validate_freeze_record(load_freeze_record(), contract, source_schema, page_schema)
    print("TRD_V031_02_STABLE_SCAN_BOUNDARY=PASS")
    print("TRD_V031_02_OPAQUE_CURSOR=PASS")
    print("TRD_V031_02_DETERMINISTIC_PAGING=PASS")
    print("TRD_V031_02_SOURCE_REFERENCE_CHECKSUM=PASS")
    print("TRD_V031_02_DATABASE_MIGRATION=20261106_0037")
    print("TRD_V031_02_FREEZE=PASS")
    print("TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    print("NEXT_ALLOWED_STAGE=TRD-V031-03")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
