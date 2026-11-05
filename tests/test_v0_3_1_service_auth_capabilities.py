from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_v0_3_1_service_auth_capabilities",
    ROOT / "scripts/verify_v0_3_1_service_auth_capabilities.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load v0.3.1 service boundary verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class V031ServiceAuthCapabilitiesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.profile = MODULE.load_profile()

    def test_candidate_matches_frozen_profile_and_runtime_boundary(self) -> None:
        MODULE.validate_contract(self.contract, self.profile)
        MODULE.validate_implementation_sources()

    def test_roadmap_freeze_prerequisite_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["prerequisite"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "Freeze commit drift"):
            MODULE.validate_contract(changed, self.profile)

    def test_constant_time_comparison_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["service_authentication"]["constant_time_comparison"] = False
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "authentication policy"):
            MODULE.validate_contract(changed, self.profile)

    def test_browser_token_delivery_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["service_authentication"]["browser_cors_delivery_allowed"] = True
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "authentication policy"):
            MODULE.validate_contract(changed, self.profile)

    def test_private_file_policy_cannot_be_weakened(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["service_authentication"]["group_or_other_permissions_allowed"] = True
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "authentication policy"):
            MODULE.validate_contract(changed, self.profile)

    def test_capability_matrix_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["response_contract"]["commands"].pop()
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "commands drift"):
            MODULE.validate_contract(changed, self.profile)

    def test_provider_version_cannot_advance_during_candidate(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime"]["provider_release_during_stage"] = "0.3.1"
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "provider version drift"):
            MODULE.validate_contract(changed, self.profile)

    def test_compatibility_cannot_be_claimed_before_real_smoke(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["runtime"]["provider_compatibility_claimed"] = True
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "compatibility claimed"):
            MODULE.validate_contract(changed, self.profile)

    def test_future_endpoint_scope_cannot_open(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["snapshot_endpoints_added"] = True
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "snapshot_endpoints_added"):
            MODULE.validate_contract(changed, self.profile)

    def test_nexora_p3_03_cannot_open(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["nexora_p3_03_opened"] = True
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "nexora_p3_03_opened"):
            MODULE.validate_contract(changed, self.profile)

    def test_next_stage_is_only_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "TRD-V031-02"
        with self.assertRaisesRegex(MODULE.V031ServiceBoundaryError, "next stage drift"):
            MODULE.validate_contract(changed, self.profile)


if __name__ == "__main__":
    unittest.main()
