#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-decision-snapshot-resources.json"
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"
SCHEMA_PATH = ROOT / "contracts/integration/nexora/v1/decision-snapshot-resources.schema.json"
PREVIOUS_FREEZE_PATH = (
    ROOT / "artifacts/v0.3.1/trd-v031-03-portfolio-snapshot-resources-freeze.json"
)
FREEZE_PATH = ROOT / "artifacts/v0.3.1/trd-v031-04-decision-snapshot-resources-freeze.json"
CANDIDATE_COMMIT = "6669a0c0c1662d0a0c465d1be9a90f20da52bda7"
CANDIDATE_TREE = "fb6112701e6d89f55e7410ecbc99101226d30dbd"
PARENT_FREEZE_COMMIT = "7069a554d603d492434f8bf0f5d33ecca8798f71"
CONTRACT_CHECKSUM = "c67fecca70474b88c9202313fd088a1cf14c05328857b38c67a0eece4f89bd7c"
SCHEMA_CHECKSUM = "c1b5263caf2a45b67b6ee0a43ac65730e9ed78f6dc5d70061071594693f1511b"
PREVIOUS_FREEZE_CHECKSUM = "dc67927d747637facb1bd971f38094efced45b1025c37a18115a320794ee0d6a"
PREVIOUS_FREEZE_COMMIT = "7069a554d603d492434f8bf0f5d33ecca8798f71"
FREEZE_CHECKSUM = "29428cd3813ce18af29a950137aa2b8449c377264239b164bf31cdf787a1ecde"
RELEASE_INVENTORY_CHECKSUM = "5d0451e214da19aaa9d7c93709a167f74600f1a69b5d6d89c54eb26b79c85be1"
EXPECTED_RESOURCES = (
    "market_context",
    "decision_evaluation",
    "candidate",
    "risk_gate",
)
EXPECTED_SCHEMA_VERSIONS = {
    "market_context": "trd-bot-market-context-v1",
    "decision_evaluation": "trd-bot-decision-evaluation-v1",
    "candidate": "trd-bot-candidate-v1",
    "risk_gate": "trd-bot-risk-gate-v1",
}
EXPECTED_IMPLEMENTATION_FILES = {
    "contracts/integration/nexora/v1/decision-snapshot-resources.schema.json": (
        "46db4d6e0b0c37169d4d9401341e1e582186abf993622eb866b31e3bc9c0050c"
    ),
    "contracts/trd-bot-v0.3.1-decision-snapshot-resources.json": (
        "78c12baaac04dacfb86472f3a5da643fa60982690e6e55b3d3bde85e6c335f25"
    ),
    "src/trd_bot/integration/nexora/decision_snapshots.py": (
        "57356145c04c08763ea8206b2541b4565e17fc31f7616d731b0a19e0ca7f066e"
    ),
    "src/trd_bot/integration/nexora/routes.py": (
        "7b6f256171bb41072de4538b91392963ab455a657b0d9e0a0b2adae1ae75252e"
    ),
    "tests/test_nexora_decision_snapshots.py": (
        "4a0c1f3b6f2bfb819034a2a1caca033c2edb12b6fe6cc4841286acb7987595ac"
    ),
    "tests/test_nexora_portfolio_snapshots.py": (
        "a738d30d685c839b210c86abaff5f53cab711bfad5cd43b2bf8b7b7afb2ca05d"
    ),
    "tests/test_v0_3_1_decision_snapshot_resources.py": (
        "8fda9a4fe70f19ed79f5794849e7cc68a33dd740dd5daa2123e1f99daf6774e9"
    ),
}


class V031DecisionSnapshotError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031DecisionSnapshotError(message)


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
        "V031-03 Freeze artifact drift",
    )
    require(record.get("decision_id") == "TRD-V031-03", "previous Freeze decision drift")
    require(record.get("status") == "frozen" and record.get("frozen") is True, "V031-03 open")
    transition = record.get("transition")
    require(isinstance(transition, dict), "V031-03 Freeze transition missing")
    require(
        transition.get("next_allowed_stage") == "TRD-V031-04",
        "V031-04 gate is not open",
    )


def validate_freeze_record(
    record: dict[str, Any],
    contract: dict[str, Any],
    schema: dict[str, Any],
    *,
    expected_checksum: str = FREEZE_CHECKSUM,
) -> None:
    require(canonical_checksum(record) == expected_checksum, "V031-04 Freeze artifact drift")
    require(
        record.get("schema_version") == "trd-bot-v031-decision-snapshot-resources-freeze-v1",
        "Freeze schema drift",
    )
    require(record.get("decision_id") == "TRD-V031-04", "Freeze decision drift")
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
        == "feat(trd-bot): add Nexora decision snapshot resources",
        "candidate message drift",
    )

    stage_contract = record.get("stage_contract")
    require(isinstance(stage_contract, dict), "Freeze stage contract must be an object")
    require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "frozen stage contract drift")
    require(
        stage_contract.get("path") == "contracts/trd-bot-v0.3.1-decision-snapshot-resources.json",
        "Freeze stage contract path drift",
    )
    require(
        stage_contract.get("canonical_checksum") == CONTRACT_CHECKSUM,
        "Freeze stage contract checksum drift",
    )

    schemas = record.get("schemas")
    require(isinstance(schemas, dict), "Freeze schemas must be an object")
    require(set(schemas) == {"decision_snapshot_resources"}, "Freeze schema inventory drift")
    resource_schema = schemas.get("decision_snapshot_resources")
    require(isinstance(resource_schema, dict), "Freeze decision schema missing")
    require(
        resource_schema.get("path")
        == "contracts/integration/nexora/v1/decision-snapshot-resources.schema.json",
        "Freeze decision schema path drift",
    )
    require(
        resource_schema.get("canonical_checksum") == SCHEMA_CHECKSUM,
        "Freeze decision schema checksum drift",
    )
    require(canonical_checksum(schema) == SCHEMA_CHECKSUM, "frozen decision schema drift")

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
        "integration_roadmap": 42351955931,
        "service_auth_capabilities": 42351955646,
        "snapshot_protocol": 42351955685,
        "portfolio_snapshot_resources": 42351955869,
        "decision_snapshot_resources": 42351955905,
        "ci": 42351955866,
    }
    expected_jobs = {
        "integration_roadmap": {"v0.3.1 integration roadmap contract": 128341792196},
        "service_auth_capabilities": {"v0.3.1 service auth and capabilities": 128341791640},
        "snapshot_protocol": {"v0.3.1 stable snapshot protocol": 128341791800},
        "portfolio_snapshot_resources": {"v0.3.1 portfolio snapshot resources": 128341792335},
        "decision_snapshot_resources": {"v0.3.1 decision snapshot resources": 128341792401},
        "ci": {
            "Backend quality and tests": 128341792505,
            "PostgreSQL migrations and integration tests": 128341792429,
            "Frontend quality, tests, and build": 128341792520,
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
        "decision_resource_allowlist_frozen",
        "decision_resource_schemas_frozen",
        "immutable_decision_evidence_frozen",
        "mutable_candidate_projection_excluded",
        "authenticated_snapshot_endpoint_frozen",
        "stable_paging_frozen",
        "source_reference_checksum_frozen",
        "offline_only_frozen",
        "runtime_behavior_added",
        "version_0_3_0_remains_incompatible",
    ):
        require(acceptance.get(key) is True, f"Freeze acceptance invariant disabled: {key}")
    for key in (
        "database_migration_added",
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
    require(transition.get("next_allowed_stage") == "TRD-V031-05", "post-Freeze stage drift")
    require(
        transition.get("next_stage_title") == "Alert snapshot resources",
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
    require(canonical_checksum(contract) == expected_checksum, "V031-04 stage contract drift")
    require(
        contract.get("schema_version") == "trd-bot-v031-decision-snapshot-resources-v1",
        "stage schema drift",
    )
    require(contract.get("decision_id") == "TRD-V031-04", "stage decision drift")
    require(contract.get("status") == "candidate", "stage must remain candidate before Freeze")
    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "stage prerequisite must be an object")
    require(prerequisite.get("frozen") is True, "V031-03 must be frozen")
    require(
        prerequisite.get("freeze_commit_sha") == PREVIOUS_FREEZE_COMMIT,
        "V031-03 Freeze commit drift",
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
    require(isinstance(resources, dict), "decision resources must be an object")
    require(tuple(resources.get("allowlist", ())) == EXPECTED_RESOURCES, "resource allowlist drift")
    require(resources.get("schema_versions") == EXPECTED_SCHEMA_VERSIONS, "schema versions drift")
    snapshot_groups = profile.get("snapshot_groups")
    require(isinstance(snapshot_groups, dict), "provider snapshot groups missing")
    require(
        tuple(snapshot_groups.get("decision", ())) == EXPECTED_RESOURCES,
        "provider decision resources drift",
    )
    for key in (
        "immutable_evidence_only",
        "source_reference_required",
        "source_checksum_required",
        "deterministic_ascending_order",
        "scan_time_boundary_required",
    ):
        require(resources.get(key) is True, f"resource invariant disabled: {key}")

    safety = contract.get("safety")
    require(isinstance(safety, dict), "safety boundary must be an object")
    for key in ("research_shadow_paper_only", "offline_only_required"):
        require(safety.get(key) is True, f"safety invariant disabled: {key}")
    for key in (
        "human_review_command_added",
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
    require(
        persistence.get("uses_existing_market_context_and_decision_tables") is True,
        "existing decision evidence disabled",
    )
    require(persistence.get("migration_added") is False, "unexpected migration added")
    require(persistence.get("migration_head") == "20261106_0037", "migration head drift")

    scope = contract.get("scope")
    require(isinstance(scope, dict), "stage scope must be an object")
    for key in (
        "snapshot_http_endpoint_registered",
        "portfolio_snapshot_resources_added",
        "decision_snapshot_resources_added",
        "market_context_added",
        "decision_evaluation_added",
        "candidate_added",
        "risk_gate_added",
    ):
        require(scope.get(key) is True, f"required scope disabled: {key}")
    for key in (
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
        transition.get("next_allowed_stage") == "TRD-V031-04-FREEZE",
        "candidate may only advance to its Freeze",
    )
    require(transition.get("post_freeze_stage") == "TRD-V031-05", "post-Freeze stage drift")


def validate_schema(schema: dict[str, Any], *, expected_checksum: str = SCHEMA_CHECKSUM) -> None:
    require(canonical_checksum(schema) == expected_checksum, "decision resource schema drift")
    definitions = schema.get("$defs")
    require(isinstance(definitions, dict), "decision schema definitions missing")
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
    for forbidden in (
        "service_token",
        "authorization",
        "exchange_credential",
        "api_secret",
        "review_command",
    ):
        require(forbidden not in serialized, f"forbidden schema field: {forbidden}")


def validate_implementation_sources() -> None:
    reader = (ROOT / "src/trd_bot/integration/nexora/decision_snapshots.py").read_text(
        encoding="utf-8"
    )
    routes = (ROOT / "src/trd_bot/integration/nexora/routes.py").read_text(encoding="utf-8")
    for marker in (
        "class DecisionSnapshotResourceReader",
        "DECISION_SNAPSHOT_RESOURCE_TYPES",
        "DecisionCandidateRankingRow",
        "external_order_submission_allowed",
    ):
        require(marker in reader, f"decision resource implementation missing: {marker}")
    require("CandidateProjectionRow" not in reader, "mutable candidate projection exposed")
    for marker in (
        "DECISION_SNAPSHOT_RESOURCE_TYPES",
        "DecisionSnapshotResourceReader",
        "SNAPSHOT_RESOURCE_TYPES",
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
    contract = load_contract()
    schema = load_schema()
    validate_previous_freeze(load_previous_freeze())
    validate_contract(contract, load_profile())
    validate_schema(schema)
    validate_implementation_sources()
    validate_freeze_record(load_freeze_record(), contract, schema)
    print("TRD_V031_04_DECISION_RESOURCE_ALLOWLIST=PASS")
    print("TRD_V031_04_IMMUTABLE_EVIDENCE=PASS")
    print("TRD_V031_04_STABLE_PAGING=PASS")
    print("TRD_V031_04_SOURCE_REFERENCE_CHECKSUM=PASS")
    print("TRD_V031_04_AUTHENTICATED_ENDPOINT=PASS")
    print("TRD_V031_04_DATABASE_MIGRATION=NONE")
    print("TRD_V031_04_FREEZE=PASS")
    print("TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    print("NEXT_ALLOWED_STAGE=TRD-V031-05")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
