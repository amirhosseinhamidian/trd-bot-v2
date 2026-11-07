#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "contracts/trd-bot-v0.3.1-stage-acceptance-policy.json"
EVIDENCE_SCHEMA_PATH = ROOT / "contracts/trd-bot-v0.3.1-stage-acceptance-evidence.schema.json"
STAGE_MANIFEST_ROOT = ROOT / "contracts/v0.3.1/stage-acceptance"

POLICY_SCHEMA = "trd-bot-v031-stage-acceptance-policy-v1"
MANIFEST_SCHEMA = "trd-bot-v031-stage-acceptance-manifest-v1"
EVIDENCE_SCHEMA = "trd-bot-v031-stage-acceptance-evidence-v1"
EXPECTED_STAGE_IDS = [f"TRD-V031-{number:02d}" for number in range(5, 12)]
EXPECTED_HISTORICAL_STAGE_IDS = [f"TRD-V031-{number:02d}" for number in range(5)]
ALLOWED_GATE_CONCLUSIONS = {"success", "failure", "cancelled", "skipped", "missing"}
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SECRET_VALUE_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)^bearer\s+[A-Za-z0-9._~+/=-]{16,}$"),
)
FORBIDDEN_EVIDENCE_KEYS = {
    "authorization",
    "password",
    "private_key",
    "secret",
    "service_token",
    "token",
}


class StageAcceptanceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StageAcceptanceError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain a JSON object")
    return cast(dict[str, Any], payload)


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return load_json(path)


def load_evidence_schema(path: Path = EVIDENCE_SCHEMA_PATH) -> dict[str, Any]:
    return load_json(path)


def manifest_path(stage_id: str) -> Path:
    require(stage_id in EXPECTED_STAGE_IDS, f"unsupported stage ID: {stage_id}")
    return STAGE_MANIFEST_ROOT / f"{stage_id.lower()}.json"


def load_manifest(stage_id: str, path: Path | None = None) -> dict[str, Any]:
    return load_json(manifest_path(stage_id) if path is None else path)


def canonical_checksum(payload: Mapping[str, Any], *, exclude: frozenset[str] = frozenset()) -> str:
    canonical = {key: value for key, value in payload.items() if key not in exclude}
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def path_checksum(path: Path) -> str:
    require(path.exists(), f"evidence path does not exist: {path.relative_to(ROOT)}")
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    require(path.is_dir(), f"unsupported evidence path: {path.relative_to(ROOT)}")
    digest = hashlib.sha256()
    files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    require(bool(files), f"evidence directory is empty: {path.relative_to(ROOT)}")
    for candidate in files:
        relative = candidate.relative_to(path).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = candidate.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def validate_policy(policy: Mapping[str, Any]) -> None:
    require(policy.get("schema_version") == POLICY_SCHEMA, "acceptance policy schema drift")
    require(policy.get("status") == "active", "acceptance policy is not active")
    require(policy.get("repository") == "amirhosseinhamidian/trd-bot-v2", "repository drift")
    require(
        policy.get("effective_from_stage") == "TRD-V031-05",
        "integrated acceptance must start at the actual next stage",
    )
    require(
        policy.get("migration_base_commit_sha") == "250d84ebd93b9999230ac316b1cb919e66be7bc5",
        "workflow migration base commit drift",
    )

    workflow = policy.get("workflow")
    require(isinstance(workflow, dict), "workflow policy must be an object")
    require(workflow.get("model") == "implementation_plus_acceptance", "workflow model drift")
    require(workflow.get("separate_stage_freeze_required") is False, "separate Freeze restored")
    require(
        workflow.get("failed_cancelled_or_missing_gate_opens_next_stage") is False,
        "failed or incomplete CI can open the next stage",
    )
    require(
        workflow.get("pull_request_run_can_open_next_stage") is False,
        "pull request validation can open the next stage",
    )
    retention = workflow.get("artifact_retention_days")
    require(isinstance(retention, int) and 30 <= retention <= 90, "artifact retention drift")
    required_gates = workflow.get("required_gates")
    require(
        required_gates
        == [
            "prerequisite",
            "stage_contract",
            "backend",
            "postgresql",
            "frontend",
            "security",
        ],
        "required gate inventory drift",
    )

    historical = policy.get("historical_freezes")
    require(isinstance(historical, list), "historical Freeze inventory must be a list")
    require(
        [entry.get("stage_id") for entry in historical] == EXPECTED_HISTORICAL_STAGE_IDS,
        "historical Freeze order drift",
    )
    for entry in historical:
        require(entry.get("immutable") is True, "historical Freeze became mutable")
        checksum = entry.get("canonical_checksum")
        require(isinstance(checksum, str) and CHECKSUM_PATTERN.fullmatch(checksum), "bad checksum")
        commit = entry.get("freeze_commit_sha")
        require(isinstance(commit, str) and SHA_PATTERN.fullmatch(commit), "bad Freeze commit")

    stages = policy.get("stages")
    require(isinstance(stages, list), "stage policy must be a list")
    require([stage.get("id") for stage in stages] == EXPECTED_STAGE_IDS, "stage order drift")
    for index, stage in enumerate(stages):
        expected_previous = (
            "TRD-V031-04" if index == 0 else cast(dict[str, Any], stages[index - 1])["id"]
        )
        expected_next = (
            None if index == len(stages) - 1 else cast(dict[str, Any], stages[index + 1])["id"]
        )
        require(
            stage.get("depends_on") == expected_previous, f"dependency drift: {stage.get('id')}"
        )
        require(stage.get("next_stage") == expected_next, f"transition drift: {stage.get('id')}")
        if stage.get("formal_freeze_allowed") is True:
            require(
                stage.get("id") in {"TRD-V031-10", "TRD-V031-11"},
                "routine stage can request a formal Freeze",
            )

    safety = policy.get("safety")
    require(isinstance(safety, dict), "safety policy must be an object")
    for key in (
        "live_execution",
        "real_money_order_execution",
        "exchange_trading_credentials",
        "wallet_or_fund_transfer",
        "shared_database_with_nexora",
        "secret_exposure",
        "premature_compatibility_claim",
    ):
        require(safety.get(key) is False, f"safety boundary enabled: {key}")
    require(
        safety.get("nexora_p3_03_blocked_until_stage") == "TRD-V031-10",
        "NEX-P3-03 release stage drift",
    )
    require(
        safety.get("nexora_p3_03_requires_real_local_provider_smoke") is True,
        "real local provider smoke requirement removed",
    )


def validate_historical_freezes(policy: Mapping[str, Any]) -> None:
    historical = policy.get("historical_freezes")
    require(isinstance(historical, list), "historical Freeze inventory must be a list")
    for entry in historical:
        path_value = entry.get("artifact_path")
        require(isinstance(path_value, str), "historical Freeze path missing")
        path = ROOT / path_value
        require(path.is_file(), f"historical Freeze missing: {path_value}")
        checksum = canonical_checksum(load_json(path))
        require(
            checksum == entry.get("canonical_checksum"),
            f"historical Freeze drift: {entry.get('stage_id')}",
        )


def validate_evidence_schema(schema: Mapping[str, Any]) -> None:
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft")
    require(schema.get("additionalProperties") is False, "evidence schema must be closed")
    required = schema.get("required")
    require(isinstance(required, list), "evidence schema required fields missing")
    for field in (
        "stage_id",
        "git",
        "workflow",
        "gates",
        "artifact_checksums",
        "overall_result",
        "accepted",
        "transition",
        "safety",
        "evidence_checksum",
    ):
        require(field in required, f"evidence schema does not require {field}")


def stage_entry(policy: Mapping[str, Any], stage_id: str) -> dict[str, Any]:
    stages = policy.get("stages")
    require(isinstance(stages, list), "stage policy must be a list")
    matches = [stage for stage in stages if stage.get("id") == stage_id]
    require(len(matches) == 1, f"stage policy missing: {stage_id}")
    return cast(dict[str, Any], matches[0])


def validate_manifest(
    policy: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    require_candidate: bool = False,
) -> None:
    require(manifest.get("schema_version") == MANIFEST_SCHEMA, "stage manifest schema drift")
    stage_id = manifest.get("stage_id")
    require(isinstance(stage_id, str), "stage manifest ID missing")
    stage = stage_entry(policy, stage_id)
    status = manifest.get("status")
    require(status in {"planned", "candidate"}, "stage manifest status invalid")
    if require_candidate:
        require(status == "candidate", f"{stage_id} is not an implementation candidate")
    require(manifest.get("title") == stage.get("title"), "stage manifest title drift")

    prerequisite = manifest.get("prerequisite")
    require(isinstance(prerequisite, dict), "stage prerequisite missing")
    require(prerequisite.get("stage_id") == stage.get("depends_on"), "prerequisite stage drift")
    mode = prerequisite.get("mode")
    require(mode in {"legacy_freeze", "ci_artifact"}, "prerequisite evidence mode invalid")
    if mode == "legacy_freeze":
        require(stage_id == "TRD-V031-05", "legacy Freeze can only bridge into V031-05")
        path = prerequisite.get("artifact_path")
        checksum = prerequisite.get("artifact_canonical_checksum")
        require(isinstance(path, str) and path.startswith("artifacts/v0.3.1/"), "bad Freeze path")
        require(
            isinstance(checksum, str) and CHECKSUM_PATTERN.fullmatch(checksum),
            "bad Freeze checksum",
        )
        repository_state = prerequisite.get("repository_state_commit_sha")
        require(
            isinstance(repository_state, str) and SHA_PATTERN.fullmatch(repository_state),
            "legacy repository state commit invalid",
        )
    elif status == "candidate":
        accepted_commit = prerequisite.get("accepted_commit_sha")
        require(
            isinstance(accepted_commit, str) and SHA_PATTERN.fullmatch(accepted_commit),
            "candidate requires the previous accepted commit SHA",
        )

    verification = manifest.get("verification")
    require(isinstance(verification, dict), "stage verification plan missing")
    for key in ("verifier_path", "unittest_path"):
        value = verification.get(key)
        require(isinstance(value, str) and value.endswith(".py"), f"invalid {key}")
    focused = verification.get("focused_pytest_paths")
    require(isinstance(focused, list) and focused, "focused pytest inventory missing")
    require(
        all(isinstance(path, str) and path.endswith(".py") for path in focused), "bad test path"
    )

    migration = manifest.get("migration")
    require(isinstance(migration, dict), "migration policy missing")
    require(migration.get("expected") is stage.get("migration_expected"), "migration policy drift")
    require(migration.get("postgresql_round_trip_required") is True, "round trip check removed")
    require(migration.get("alembic_check_required") is True, "Alembic check removed")

    evidence_paths = manifest.get("evidence_paths")
    require(isinstance(evidence_paths, list) and evidence_paths, "evidence paths missing")
    require(len(evidence_paths) == len(set(evidence_paths)), "duplicate evidence paths")
    require(
        all(
            isinstance(path, str) and not Path(path).is_absolute() and ".." not in Path(path).parts
            for path in evidence_paths
        ),
        "unsafe evidence path",
    )
    if require_candidate:
        for relative in evidence_paths:
            require((ROOT / relative).exists(), f"candidate evidence path missing: {relative}")

    transition = manifest.get("transition")
    require(isinstance(transition, dict), "stage transition missing")
    require(transition.get("next_stage") == stage.get("next_stage"), "next stage drift")
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze restored")

    safety = manifest.get("safety")
    require(isinstance(safety, dict), "stage safety boundary missing")
    for key in (
        "live_execution",
        "external_order_submission",
        "exchange_credentials",
        "wallet_or_fund_transfer",
        "nexora_p3_03_opened",
        "provider_compatibility_claimed",
    ):
        require(safety.get(key) is False, f"stage safety boundary enabled: {key}")


def evidence_path_checksums(
    policy: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, str]:
    paths = [
        POLICY_PATH.relative_to(ROOT).as_posix(),
        EVIDENCE_SCHEMA_PATH.relative_to(ROOT).as_posix(),
        manifest_path(cast(str, manifest["stage_id"])).relative_to(ROOT).as_posix(),
        *cast(list[str], manifest["evidence_paths"]),
    ]
    return {relative: path_checksum(ROOT / relative) for relative in sorted(set(paths))}


def _gate_result(required_gates: list[str], gates: Mapping[str, str]) -> str:
    conclusions = [gates.get(gate, "missing") for gate in required_gates]
    if any(conclusion in {"failure", "cancelled"} for conclusion in conclusions):
        return "rejected"
    if any(conclusion in {"missing", "skipped"} for conclusion in conclusions):
        return "incomplete"
    require(all(conclusion == "success" for conclusion in conclusions), "unknown gate conclusion")
    return "passed"


def build_evidence(
    policy: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    repository: str,
    commit_sha: str,
    tree_sha: str,
    ref: str,
    run_id: int,
    run_attempt: int,
    event: str,
    gates: Mapping[str, str],
    artifact_checksums: Mapping[str, str],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    validate_manifest(policy, manifest, require_candidate=True)
    require(repository == policy.get("repository"), "evidence repository drift")
    require(SHA_PATTERN.fullmatch(commit_sha) is not None, "invalid commit SHA")
    require(SHA_PATTERN.fullmatch(tree_sha) is not None, "invalid tree SHA")
    require(run_id > 0 and run_attempt > 0, "invalid workflow identity")
    require(bool(ref), "git ref missing")

    workflow = cast(dict[str, Any], policy["workflow"])
    required_gates = cast(list[str], workflow["required_gates"])
    require(set(gates) == set(required_gates), "gate result inventory drift")
    for conclusion in gates.values():
        require(conclusion in ALLOWED_GATE_CONCLUSIONS, f"invalid gate conclusion: {conclusion}")
    for checksum in artifact_checksums.values():
        require(CHECKSUM_PATTERN.fullmatch(checksum) is not None, "invalid artifact checksum")

    gate_result = _gate_result(required_gates, gates)
    accepted_events = cast(list[str], workflow["accepted_events"])
    if gate_result == "passed":
        overall_result = "accepted" if event in accepted_events else "validation_only"
    else:
        overall_result = gate_result
    accepted = overall_result == "accepted"
    stage = stage_entry(policy, cast(str, manifest["stage_id"]))
    timestamp = generated_at or datetime.now(UTC)

    evidence: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA,
        "stage_id": manifest["stage_id"],
        "generated_at": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "repository": repository,
        "git": {
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "ref": ref,
        },
        "workflow": {
            "run_id": run_id,
            "run_attempt": run_attempt,
            "event": event,
        },
        "gates": {gate: {"required": True, "conclusion": gates[gate]} for gate in required_gates},
        "test_results": {
            "stage_contract": gates["stage_contract"],
            "backend_unit_and_quality": gates["backend"],
            "postgresql_migration_and_integration": gates["postgresql"],
            "frontend_quality_test_and_build": gates["frontend"],
            "security_boundary": gates["security"],
        },
        "artifact_checksums": dict(sorted(artifact_checksums.items())),
        "overall_result": overall_result,
        "accepted": accepted,
        "transition": {
            "next_stage": stage.get("next_stage"),
            "opened": accepted,
        },
        "safety": {
            "live_execution": False,
            "real_money_order_execution": False,
            "exchange_credentials": False,
            "wallet_or_fund_transfer": False,
            "shared_database_with_nexora": False,
            "nexora_p3_03_opened": False,
            "provider_compatibility_claimed": False,
        },
    }
    _reject_secret_material(evidence)
    evidence["evidence_checksum"] = canonical_checksum(evidence)
    return evidence


def _reject_secret_material(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            require(
                key.lower() not in FORBIDDEN_EVIDENCE_KEYS,
                f"secret-like evidence key: {path}.{key}",
            )
            _reject_secret_material(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_material(item, path=f"{path}[{index}]")
    elif isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            require(pattern.search(value) is None, f"secret-like evidence value: {path}")


def validate_evidence(
    policy: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    expected_stage_id: str | None = None,
    expected_commit_sha: str | None = None,
    expected_next_stage: str | None = None,
) -> None:
    validate_policy(policy)
    require(evidence.get("schema_version") == EVIDENCE_SCHEMA, "evidence schema drift")
    stage_id = evidence.get("stage_id")
    require(isinstance(stage_id, str) and stage_id in EXPECTED_STAGE_IDS, "evidence stage drift")
    if expected_stage_id is not None:
        require(stage_id == expected_stage_id, "unexpected evidence stage")
    require(evidence.get("repository") == policy.get("repository"), "evidence repository drift")

    git = evidence.get("git")
    require(isinstance(git, dict), "evidence git identity missing")
    commit_sha = git.get("commit_sha")
    tree_sha = git.get("tree_sha")
    require(isinstance(commit_sha, str) and SHA_PATTERN.fullmatch(commit_sha), "invalid commit SHA")
    require(isinstance(tree_sha, str) and SHA_PATTERN.fullmatch(tree_sha), "invalid tree SHA")
    if expected_commit_sha is not None:
        require(commit_sha == expected_commit_sha, "unexpected accepted commit SHA")

    workflow_identity = evidence.get("workflow")
    require(isinstance(workflow_identity, dict), "workflow identity missing")
    require(
        isinstance(workflow_identity.get("run_id"), int) and workflow_identity["run_id"] > 0,
        "workflow run ID invalid",
    )
    require(
        isinstance(workflow_identity.get("run_attempt"), int)
        and workflow_identity["run_attempt"] > 0,
        "workflow run attempt invalid",
    )
    event = workflow_identity.get("event")
    require(isinstance(event, str), "workflow event missing")

    workflow = cast(dict[str, Any], policy["workflow"])
    required_gates = cast(list[str], workflow["required_gates"])
    gate_payload = evidence.get("gates")
    require(isinstance(gate_payload, dict), "evidence gates missing")
    require(set(gate_payload) == set(required_gates), "evidence gate inventory drift")
    conclusions: dict[str, str] = {}
    for gate in required_gates:
        item = gate_payload.get(gate)
        require(isinstance(item, dict), f"evidence gate missing: {gate}")
        require(item.get("required") is True, f"required gate weakened: {gate}")
        conclusion = item.get("conclusion")
        require(conclusion in ALLOWED_GATE_CONCLUSIONS, f"gate conclusion invalid: {gate}")
        conclusions[gate] = cast(str, conclusion)

    gate_result = _gate_result(required_gates, conclusions)
    accepted_events = cast(list[str], workflow["accepted_events"])
    expected_result = (
        ("accepted" if event in accepted_events else "validation_only")
        if gate_result == "passed"
        else gate_result
    )
    require(evidence.get("overall_result") == expected_result, "overall acceptance result drift")
    accepted = expected_result == "accepted"
    require(evidence.get("accepted") is accepted, "accepted flag drift")

    transition = evidence.get("transition")
    require(isinstance(transition, dict), "evidence transition missing")
    next_stage = stage_entry(policy, stage_id).get("next_stage")
    require(transition.get("next_stage") == next_stage, "evidence next stage drift")
    require(transition.get("opened") is accepted, "stage opened without accepted evidence")
    if expected_next_stage is not None:
        require(accepted and next_stage == expected_next_stage, "prerequisite did not open stage")

    checksums = evidence.get("artifact_checksums")
    require(isinstance(checksums, dict) and checksums, "artifact checksums missing")
    for checksum in checksums.values():
        require(isinstance(checksum, str) and CHECKSUM_PATTERN.fullmatch(checksum), "bad checksum")

    safety = evidence.get("safety")
    require(isinstance(safety, dict), "evidence safety boundary missing")
    for key, value in safety.items():
        require(value is False, f"unsafe acceptance claim: {key}")
    _reject_secret_material(evidence)

    checksum = evidence.get("evidence_checksum")
    require(isinstance(checksum, str), "evidence checksum missing")
    require(
        checksum == canonical_checksum(evidence, exclude=frozenset({"evidence_checksum"})),
        "evidence checksum drift",
    )


def validate_prerequisite(
    policy: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    previous_evidence: Mapping[str, Any] | None = None,
) -> None:
    validate_manifest(policy, manifest)
    prerequisite = cast(dict[str, Any], manifest["prerequisite"])
    stage_id = cast(str, manifest["stage_id"])
    if prerequisite["mode"] == "legacy_freeze":
        path = ROOT / cast(str, prerequisite["artifact_path"])
        record = load_json(path)
        require(
            canonical_checksum(record) == prerequisite["artifact_canonical_checksum"],
            "legacy prerequisite Freeze drift",
        )
        transition = record.get("transition")
        require(isinstance(transition, dict), "legacy prerequisite transition missing")
        require(transition.get("next_allowed_stage") == stage_id, "legacy Freeze opens wrong stage")
        return

    require(previous_evidence is not None, "previous CI acceptance evidence missing")
    validate_evidence(
        policy,
        previous_evidence,
        expected_stage_id=cast(str, prerequisite["stage_id"]),
        expected_commit_sha=cast(str, prerequisite["accepted_commit_sha"]),
        expected_next_stage=stage_id,
    )
