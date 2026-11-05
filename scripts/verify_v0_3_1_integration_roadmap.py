#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = ROOT / "contracts/trd-bot-v0.3.1-nexora-integration-roadmap.json"
CONTRACT_PATH = ROOT / "contracts/integration/nexora/v1/nexora-v0.1-trd-bot-v031-integration.json"
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"

BASELINE_COMMIT = "bbb9fd4fbc25e25aa512a9fde1dda912321cdd33"
NEXORA_FREEZE_COMMIT = "1e114b58b1a9cfc4ef91280c6506aa58bb2f53e8"
CONTRACT_CHECKSUM = "e0c0cee635c27e52825501fd36de68cb07a6e3feeb70b8fdefeb5e5fcbbbf753"
PROFILE_CHECKSUM = "48cfcd61b8f2cb866e4c921d31f5c61db83d3f08e5123d690a069a57c3aba109"

EXPECTED_STAGE_IDS = [
    "TRD-V031-00",
    "TRD-V031-00-FREEZE",
    "TRD-V031-01",
    "TRD-V031-02",
    "TRD-V031-03",
    "TRD-V031-04",
    "TRD-V031-05",
    "TRD-V031-06",
    "TRD-V031-07",
    "TRD-V031-08",
    "TRD-V031-09",
    "TRD-V031-10",
    "TRD-V031-11",
]
EXPECTED_OPERATIONS = {
    "GET /capabilities",
    "GET /snapshots/{resource_type}",
    "GET /events",
    "GET /events/{event_id}",
    "POST /commands/decision-reviews",
    "POST /exports",
    "GET /exports/{export_id}",
    "GET /exports/{export_id}/manifest",
}
EXPECTED_SNAPSHOT_RESOURCES = {
    "paper_shadow_portfolio",
    "paper_shadow_position",
    "portfolio_intelligence",
    "simulation_outcome",
    "market_context",
    "decision_evaluation",
    "candidate",
    "risk_gate",
    "alert",
    "alert_outcome",
}
EXPECTED_COMMANDS = {
    "decision_review.accept.v1",
    "decision_review.reject.v1",
    "decision_review.defer.v1",
}
FORBIDDEN_TRUE = {
    "direct_nexora_database_access",
    "shared_database",
    "browser_service_token",
    "public_internet_required_for_smoke",
    "live_execution",
    "exchange_credentials",
    "wallet_or_fund_transfer",
    "autonomous_ai_execution",
    "strategy_behavior_materially_changed",
    "risk_policy_materially_changed",
    "secrets_in_logs_payloads_or_exports",
}


class V031RoadmapError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031RoadmapError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def canonical_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_roadmap(path: Path = ROADMAP_PATH) -> dict[str, Any]:
    return load_json(path)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return load_json(path)


def load_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    return load_json(path)


def validate_frozen_upstream(
    roadmap: dict[str, Any],
    contract: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    upstream = roadmap.get("upstream_freeze")
    require(isinstance(upstream, dict), "upstream Freeze reference must be an object")
    require(upstream.get("repository") == "amirhosseinhamidian/nexora", "upstream repository drift")
    require(upstream.get("freeze_commit_sha") == NEXORA_FREEZE_COMMIT, "Nexora Freeze commit drift")
    require(upstream.get("decision_id") == "NEX-P3-02", "Nexora decision drift")
    require(upstream.get("frozen") is True, "Nexora contract is not frozen")
    require(
        upstream.get("provider_implementation_deferred_to_this_repository") is True,
        "provider ownership drift",
    )
    require(canonical_checksum(contract) == CONTRACT_CHECKSUM, "vendored Nexora contract drift")
    require(canonical_checksum(profile) == PROFILE_CHECKSUM, "vendored provider profile drift")
    require(
        upstream.get("contract_canonical_checksum") == CONTRACT_CHECKSUM, "contract reference drift"
    )
    require(
        upstream.get("provider_profile_canonical_checksum") == PROFILE_CHECKSUM,
        "provider profile reference drift",
    )

    require(contract.get("decision_id") == "NEX-P3-02", "contract decision drift")
    provider = contract.get("provider_baseline")
    require(isinstance(provider, dict), "provider baseline must be an object")
    require(
        provider.get("inspected_commit_sha") == BASELINE_COMMIT, "provider baseline commit drift"
    )
    require(provider.get("compatible") is False, "v0.3.0 cannot be compatible")
    require(provider.get("direct_database_fallback_allowed") is False, "database fallback enabled")

    target = contract.get("target_provider")
    require(isinstance(target, dict), "target provider must be an object")
    require(target.get("release") == "0.3.1", "target provider release drift")
    require(
        target.get("compatibility_status_before_smoke") == "contract_candidate_only",
        "premature compatibility claim",
    )


def validate_profile(profile: dict[str, Any]) -> None:
    require(
        profile.get("schema_version") == "nexora-trd-bot-v031-provider-profile-v1",
        "provider profile schema drift",
    )
    require(
        profile.get("contract_version") == "nexora-trd-integration-v1", "contract version drift"
    )
    require(set(profile.get("operations", [])) == EXPECTED_OPERATIONS, "operation inventory drift")

    groups = profile.get("snapshot_groups")
    require(isinstance(groups, dict), "snapshot groups must be an object")
    resources = [resource for values in groups.values() for resource in values]
    require(set(resources) == EXPECTED_SNAPSHOT_RESOURCES, "snapshot resource inventory drift")
    require(len(resources) == len(set(resources)), "snapshot resources overlap")

    auth = profile.get("service_authentication")
    require(isinstance(auth, dict), "service authentication must be an object")
    require(auth.get("scheme") == "bearer_service_token", "service authentication scheme drift")
    require(auth.get("token_source") == "absolute_private_file", "service token source drift")
    require(auth.get("minimum_token_entropy_bytes") == 32, "service token entropy weakened")
    require(auth.get("constant_time_comparison_required") is True, "constant-time auth disabled")
    for key in (
        "query_parameter_allowed",
        "cookie_allowed",
        "browser_delivery_allowed",
        "logging_allowed",
    ):
        require(auth.get(key) is False, f"service token exposure enabled: {key}")

    capabilities = profile.get("capability_negotiation")
    require(isinstance(capabilities, dict), "capability negotiation must be an object")
    require(set(capabilities.get("commands", [])) == EXPECTED_COMMANDS, "command inventory drift")
    require(
        capabilities.get("missing_or_unknown_capability_action") == "fail_closed",
        "capability negotiation is not fail-closed",
    )

    events = profile.get("event_feed")
    require(isinstance(events, dict), "event feed must be an object")
    require(events.get("delivery_semantics") == "at_least_once", "event delivery semantics drift")
    require(events.get("exactly_once_claimed") is False, "exactly-once delivery claimed")
    require(events.get("expired_cursor_status") == 410, "expired cursor status drift")

    smoke = profile.get("acceptance_smoke")
    require(isinstance(smoke, dict), "acceptance smoke must be an object")
    require(smoke.get("real_provider_required") is True, "real provider smoke removed")
    require(len(smoke.get("required_scenarios", [])) == 12, "acceptance scenario inventory drift")


def validate_roadmap(roadmap: dict[str, Any]) -> None:
    require(
        roadmap.get("schema_version") == "trd-bot-v031-nexora-integration-roadmap-v1",
        "roadmap schema drift",
    )
    require(roadmap.get("decision_id") == "TRD-V031-00", "roadmap decision drift")
    require(roadmap.get("status") == "candidate", "roadmap must remain a candidate")

    repository = roadmap.get("repository")
    require(isinstance(repository, dict), "repository baseline must be an object")
    require(repository.get("baseline_release") == "0.3.0", "baseline release drift")
    require(repository.get("baseline_commit_sha") == BASELINE_COMMIT, "baseline commit drift")
    require(repository.get("target_release") == "0.3.1", "target release drift")

    with (ROOT / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    require(pyproject["project"]["version"] == "0.3.0", "V031-00 must not bump runtime version")

    stages = roadmap.get("stages")
    require(isinstance(stages, list), "roadmap stages must be a list")
    require([stage.get("id") for stage in stages] == EXPECTED_STAGE_IDS, "stage order drift")
    require(stages[0].get("status") == "candidate", "V031-00 candidate status drift")
    require(
        all(stage.get("status") == "blocked" for stage in stages[1:]), "future stage opened early"
    )
    require(stages[0].get("runtime_change") is False, "V031-00 added runtime behavior")
    require(stages[0].get("migration") is False, "V031-00 added a migration")

    for index, stage in enumerate(stages[1:], start=1):
        require(
            stage.get("depends_on") == [EXPECTED_STAGE_IDS[index - 1]],
            f"stage dependency drift: {stage.get('id')}",
        )
        require(
            isinstance(stage.get("delivers"), list) and stage["delivers"],
            f"stage deliverables missing: {stage.get('id')}",
        )

    invariants = roadmap.get("invariants")
    require(isinstance(invariants, dict), "roadmap invariants must be an object")
    require(
        invariants.get("supported_modes") == ["RESEARCH", "BACKTEST", "PAPER", "SHADOW"],
        "mode boundary drift",
    )
    for key in FORBIDDEN_TRUE:
        require(invariants.get(key) is False, f"forbidden capability enabled: {key}")
    for key in (
        "single_owner",
        "evidence_remains_immutable",
        "events_are_idempotent_and_recoverable",
    ):
        require(invariants.get(key) is True, f"required invariant disabled: {key}")

    acceptance = roadmap.get("acceptance")
    require(isinstance(acceptance, dict), "roadmap acceptance must be an object")
    for key in (
        "each_stage_requires_contract_tests",
        "migration_stages_require_postgresql_17_round_trip",
        "ci_required_on_same_candidate_sha",
        "real_provider_smoke_required_before_compatibility_claim",
        "nexora_p3_03_remains_blocked_until_real_smoke",
        "version_0_3_0_remains_incompatible",
    ):
        require(acceptance.get(key) is True, f"acceptance gate disabled: {key}")
    require(acceptance.get("production_readiness_claimed") is False, "production readiness claimed")

    transition = roadmap.get("transition")
    require(isinstance(transition, dict), "roadmap transition must be an object")
    require(transition.get("next_allowed_stage") == "TRD-V031-00-FREEZE", "next stage drift")
    require(
        transition.get("implementation_after_freeze") == "TRD-V031-01", "implementation stage drift"
    )
    require(
        transition.get("nexora_stage_unblocked_after_release_smoke") == "NEX-P3-03",
        "Nexora continuation drift",
    )


def main() -> int:
    roadmap = load_roadmap()
    contract = load_contract()
    profile = load_profile()
    validate_frozen_upstream(roadmap, contract, profile)
    validate_profile(profile)
    validate_roadmap(roadmap)
    print("TRD_V031_00_NEXORA_CONTRACT_ADOPTION=PASS")
    print("TRD_V031_00_ROADMAP=PASS")
    print("TRD_V031_00_RUNTIME_CHANGE=NONE")
    print("TRD_V031_00_DATABASE_MIGRATION=NONE")
    print("TRD_V031_01_IMPLEMENTATION_GATE=BLOCKED_UNTIL_FREEZE")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
