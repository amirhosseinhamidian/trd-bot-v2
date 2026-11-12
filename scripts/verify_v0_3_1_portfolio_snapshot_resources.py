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
FREEZE_PATH = ROOT / "artifacts/v0.3.1/trd-v031-03-portfolio-snapshot-resources-freeze.json"
CANDIDATE_COMMIT = "e42add51039ea7243672cc4cbfb1b7f6a2a862fb"
CANDIDATE_TREE = "d26e8f4a9392c643c1b5629b5480b0c6fb4b7ee4"
PARENT_FREEZE_COMMIT = "b4d5fb62dabffd8e74257d5b3e10148a191395a3"
CONTRACT_CHECKSUM = "ba47facd32990e9e8b8644eec0b2d513a655b6b504eb1c6a26685b948da6d981"
SCHEMA_CHECKSUM = "5a523d248e20bad484cfdf6ff5b5b31501237e9e7d3f45a3a056e3db9e557fa5"
PREVIOUS_FREEZE_CHECKSUM = "51c681b89cdae8e16837a8310441266a3cbb98e57d2bf6bdd753e917068a1ee2"
PREVIOUS_FREEZE_COMMIT = "b4d5fb62dabffd8e74257d5b3e10148a191395a3"
FREEZE_CHECKSUM = "dc67927d747637facb1bd971f38094efced45b1025c37a18115a320794ee0d6a"
RELEASE_INVENTORY_CHECKSUM = "5d0451e214da19aaa9d7c93709a167f74600f1a69b5d6d89c54eb26b79c85be1"
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
EXPECTED_IMPLEMENTATION_FILES = {
    "contracts/integration/nexora/v1/portfolio-snapshot-resources.schema.json": (
        "feb4274d768f4dc2f5b23e422e53a8b4aef8fdf21ef838cd0d43b21ec4b0fee3"
    ),
    "contracts/trd-bot-v0.3.1-portfolio-snapshot-resources.json": (
        "881a7481272c0ccafe32bda3678fe7ffb1a0656f49861bfc0dbd55b8039ab3f2"
    ),
    "src/trd_bot/integration/nexora/contracts.py": (
        "c7ea94a12ab005d3553b6c66ef303ad45881de91dd18669cd887db025f8566f7"
    ),
    "src/trd_bot/integration/nexora/portfolio_snapshots.py": (
        "68949811918178f4ff679ded20d17ddbfe79952f0479a4b8293fe6897713ab40"
    ),
    "src/trd_bot/integration/nexora/routes.py": (
        "f32b5cadf48b8ef50e99d652a8c53a6c530618b8c0c1fd8dcbbf503be34e7287"
    ),
    "tests/test_nexora_integration_capabilities.py": (
        "e782fa9724ca63c0a12e3b9f27e4b0270ade8f4433a94cc4f3c631b7c8ae3b91"
    ),
    "tests/test_nexora_portfolio_snapshots.py": (
        "d5802cc50463da3606f5c3b8253d41099d8bff8252f9acfb7c5bd64b9edcea95"
    ),
    "tests/test_release_hardening.py": (
        "36c17d3960e080e41ce38f6d8445b887b8b385f6bd2baf5dcb4464f3ee3e93e2"
    ),
    "tests/test_v0_3_1_portfolio_snapshot_resources.py": (
        "f7d86752ca4ee15cf2aa9899f394fa0dea416f7f5e59b8cc5f950b7c44f5b5d1"
    ),
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


def load_freeze_record(path: Path = FREEZE_PATH) -> dict[str, Any]:
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


def validate_freeze_record(
    record: dict[str, Any],
    contract: dict[str, Any],
    schema: dict[str, Any],
    *,
    expected_checksum: str = FREEZE_CHECKSUM,
) -> None:
    require(canonical_checksum(record) == expected_checksum, "V031-03 Freeze artifact drift")
    require(
        record.get("schema_version") == "trd-bot-v031-portfolio-snapshot-resources-freeze-v1",
        "Freeze schema drift",
    )
    require(record.get("decision_id") == "TRD-V031-03", "Freeze decision drift")
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
        == "feat(trd-bot): add Nexora portfolio snapshot resources",
        "candidate message drift",
    )

    stage_contract = record.get("stage_contract")
    require(isinstance(stage_contract, dict), "Freeze stage contract must be an object")
    require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "frozen stage contract drift")
    require(
        stage_contract.get("path") == "contracts/trd-bot-v0.3.1-portfolio-snapshot-resources.json",
        "Freeze stage contract path drift",
    )
    require(
        stage_contract.get("canonical_checksum") == CONTRACT_CHECKSUM,
        "Freeze stage contract checksum drift",
    )

    schemas = record.get("schemas")
    require(isinstance(schemas, dict), "Freeze schemas must be an object")
    require(set(schemas) == {"portfolio_snapshot_resources"}, "Freeze schema inventory drift")
    resource_schema = schemas.get("portfolio_snapshot_resources")
    require(isinstance(resource_schema, dict), "Freeze portfolio schema missing")
    require(
        resource_schema.get("path")
        == "contracts/integration/nexora/v1/portfolio-snapshot-resources.schema.json",
        "Freeze portfolio schema path drift",
    )
    require(
        resource_schema.get("canonical_checksum") == SCHEMA_CHECKSUM,
        "Freeze portfolio schema checksum drift",
    )
    require(canonical_checksum(schema) == SCHEMA_CHECKSUM, "frozen portfolio schema drift")

    implementation = record.get("implementation")
    require(isinstance(implementation, dict), "Freeze implementation must be an object")
    require(implementation.get("provider_version") == "0.3.0", "provider version advanced early")
    require(implementation.get("migration_revision") == "20261106_0037", "migration drift")
    require(implementation.get("database_migration_added") is False, "unexpected migration added")
    require(
        implementation.get("release_inventory_checksum") == RELEASE_INVENTORY_CHECKSUM,
        "release inventory checksum drift",
    )
    files = implementation.get("files_sha256")
    require(isinstance(files, dict), "Freeze implementation file checksums must be an object")
    require(files == EXPECTED_IMPLEMENTATION_FILES, "Freeze implementation inventory drift")

    workflows = record.get("workflows")
    require(isinstance(workflows, dict), "Freeze workflows must be an object")
    expected_runs = {
        "integration_roadmap": 42349603979,
        "service_auth_capabilities": 42349603880,
        "snapshot_protocol": 42349603881,
        "portfolio_snapshot_resources": 42349603997,
        "ci": 42349603882,
    }
    expected_jobs = {
        "integration_roadmap": {"v0.3.1 integration roadmap contract": 128334718450},
        "service_auth_capabilities": {"v0.3.1 service auth and capabilities": 128334717847},
        "snapshot_protocol": {"v0.3.1 stable snapshot protocol": 128334717612},
        "portfolio_snapshot_resources": {"v0.3.1 portfolio snapshot resources": 128334717690},
        "ci": {
            "Backend quality and tests": 128334717885,
            "PostgreSQL migrations and integration tests": 128334717959,
            "Frontend quality, tests, and build": 128334717732,
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
        "portfolio_resource_allowlist_frozen",
        "portfolio_resource_schemas_frozen",
        "authenticated_snapshot_endpoint_frozen",
        "stable_paging_frozen",
        "source_reference_checksum_frozen",
        "paper_shadow_only_frozen",
        "runtime_behavior_added",
        "version_0_3_0_remains_incompatible",
    ):
        require(acceptance.get(key) is True, f"Freeze acceptance invariant disabled: {key}")
    for key in (
        "database_migration_added",
        "decision_snapshot_resources_added",
        "alert_snapshot_resources_added",
        "event_feed_added",
        "review_commands_added",
        "export_protocol_added",
        "release_version_bumped",
        "provider_compatibility_claimed",
        "real_provider_smoke_passed",
        "nexora_p3_03_opened",
        "external_order_submission_allowed",
        "live_execution_enabled",
        "production_readiness_claimed",
    ):
        require(acceptance.get(key) is False, f"premature Freeze claim: {key}")

    transition = record.get("transition")
    require(isinstance(transition, dict), "Freeze transition must be an object")
    require(transition.get("next_allowed_stage") == "TRD-V031-04", "post-Freeze stage drift")
    require(
        transition.get("next_stage_title") == "Decision snapshot resources",
        "post-Freeze stage title drift",
    )
    require(
        transition.get("nexora_stage_remains_blocked_until") == "compatible_real_provider_smoke",
        "Nexora P3-03 opened before real provider smoke",
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
    require(pyproject["project"]["version"] in {"0.3.0", "0.3.1"}, "release version drift")
    migrations = sorted(path.name for path in (ROOT / "alembic/versions").glob("*.py"))
    require(
        "20261106_0037_nexora_snapshot_protocol.py" in migrations,
        "snapshot protocol migration missing",
    )


def main() -> int:
    contract = load_contract()
    schema = load_schema()
    validate_previous_freeze(load_previous_freeze())
    validate_contract(contract, load_profile())
    validate_schema(schema)
    validate_implementation_sources()
    validate_freeze_record(load_freeze_record(), contract, schema)
    print("TRD_V031_03_PORTFOLIO_RESOURCE_ALLOWLIST=PASS")
    print("TRD_V031_03_STABLE_PAGING=PASS")
    print("TRD_V031_03_SOURCE_REFERENCE_CHECKSUM=PASS")
    print("TRD_V031_03_AUTHENTICATED_ENDPOINT=PASS")
    print("TRD_V031_03_DATABASE_MIGRATION=NONE")
    print("TRD_V031_03_FREEZE=PASS")
    print("TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    print("NEXT_ALLOWED_STAGE=TRD-V031-04")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
