from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_v0_3_1_integration_roadmap",
    ROOT / "scripts/verify_v0_3_1_integration_roadmap.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load v0.3.1 integration roadmap verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class V031IntegrationRoadmapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.roadmap = MODULE.load_roadmap()
        self.contract = MODULE.load_contract()
        self.profile = MODULE.load_profile()
        self.freeze = MODULE.load_freeze_record()

    def test_candidate_adopts_frozen_contract_and_valid_roadmap(self) -> None:
        MODULE.validate_frozen_upstream(self.roadmap, self.contract, self.profile)
        MODULE.validate_profile(self.profile)
        MODULE.validate_roadmap(self.roadmap)
        MODULE.validate_freeze_record(
            self.freeze,
            self.roadmap,
            self.contract,
            self.profile,
        )

    def test_freeze_candidate_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["candidate_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "Freeze artifact drift"):
            MODULE.validate_freeze_record(changed, self.roadmap, self.contract, self.profile)

    def test_freeze_cannot_accept_failed_ci_job(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["workflows"]["ci"]["jobs"]["Backend quality and tests"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "Freeze artifact drift"):
            MODULE.validate_freeze_record(changed, self.roadmap, self.contract, self.profile)

    def test_freeze_detects_roadmap_drift(self) -> None:
        changed_roadmap = copy.deepcopy(self.roadmap)
        changed_roadmap["decision_date"] = "2026-11-06"
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "frozen roadmap drift"):
            MODULE.validate_freeze_record(
                self.freeze,
                changed_roadmap,
                self.contract,
                self.profile,
            )

    def test_freeze_cannot_claim_provider_compatibility(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["acceptance"]["provider_compatibility_claimed"] = True
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "Freeze artifact drift"):
            MODULE.validate_freeze_record(changed, self.roadmap, self.contract, self.profile)

    def test_freeze_cannot_open_nexora_p3_03(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["acceptance"]["nexora_p3_03_opened"] = True
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "Freeze artifact drift"):
            MODULE.validate_freeze_record(changed, self.roadmap, self.contract, self.profile)

    def test_freeze_opens_only_v031_01(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["transition"]["next_allowed_stage"] = "TRD-V031-02"
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "Freeze artifact drift"):
            MODULE.validate_freeze_record(changed, self.roadmap, self.contract, self.profile)

    def test_canonical_checksum_is_order_independent(self) -> None:
        reversed_contract = dict(reversed(list(self.contract.items())))
        self.assertEqual(
            MODULE.canonical_checksum(self.contract),
            MODULE.canonical_checksum(reversed_contract),
        )

    def test_v0_3_0_cannot_be_declared_compatible(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["provider_baseline"]["compatible"] = True
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "vendored Nexora contract drift"):
            MODULE.validate_frozen_upstream(self.roadmap, changed, self.profile)

    def test_upstream_freeze_commit_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.roadmap)
        changed["upstream_freeze"]["freeze_commit_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "Freeze commit drift"):
            MODULE.validate_frozen_upstream(changed, self.contract, self.profile)

    def test_contract_checksum_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["decision_date"] = "2026-11-05"
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "vendored Nexora contract drift"):
            MODULE.validate_frozen_upstream(self.roadmap, changed, self.profile)

    def test_operation_inventory_cannot_shrink(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["operations"].pop()
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "operation inventory drift"):
            MODULE.validate_profile(changed)

    def test_service_token_cannot_be_exposed_to_browser(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["service_authentication"]["browser_delivery_allowed"] = True
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "browser_delivery_allowed"):
            MODULE.validate_profile(changed)

    def test_exactly_once_delivery_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["event_feed"]["exactly_once_claimed"] = True
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "exactly-once"):
            MODULE.validate_profile(changed)

    def test_real_provider_smoke_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.profile)
        changed["acceptance_smoke"]["real_provider_required"] = False
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "real provider smoke"):
            MODULE.validate_profile(changed)

    def test_stage_order_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.roadmap)
        changed["stages"][2], changed["stages"][3] = changed["stages"][3], changed["stages"][2]
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "stage order drift"):
            MODULE.validate_roadmap(changed)

    def test_future_stage_cannot_open_before_roadmap_freeze(self) -> None:
        changed = copy.deepcopy(self.roadmap)
        changed["stages"][2]["status"] = "candidate"
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "future stage opened early"):
            MODULE.validate_roadmap(changed)

    def test_v031_00_cannot_add_runtime_behavior(self) -> None:
        changed = copy.deepcopy(self.roadmap)
        changed["stages"][0]["runtime_change"] = True
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "runtime behavior"):
            MODULE.validate_roadmap(changed)

    def test_live_execution_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.roadmap)
        changed["invariants"]["live_execution"] = True
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "live_execution"):
            MODULE.validate_roadmap(changed)

    def test_nexora_p3_03_cannot_open_before_real_smoke(self) -> None:
        changed = copy.deepcopy(self.roadmap)
        changed["acceptance"]["nexora_p3_03_remains_blocked_until_real_smoke"] = False
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "acceptance gate disabled"):
            MODULE.validate_roadmap(changed)

    def test_next_stage_is_only_roadmap_freeze(self) -> None:
        changed = copy.deepcopy(self.roadmap)
        changed["transition"]["next_allowed_stage"] = "TRD-V031-01"
        with self.assertRaisesRegex(MODULE.V031RoadmapError, "next stage drift"):
            MODULE.validate_roadmap(changed)


if __name__ == "__main__":
    unittest.main()
