from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_v0_3_1_portfolio_snapshot_resources",
    ROOT / "scripts/verify_v0_3_1_portfolio_snapshot_resources.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load v0.3.1 portfolio snapshot resource verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class V031PortfolioSnapshotResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.profile = MODULE.load_profile()
        self.schema = MODULE.load_schema()
        self.freeze = MODULE.load_freeze_record()

    def test_candidate_matches_frozen_profile_and_previous_freeze(self) -> None:
        MODULE.validate_previous_freeze(MODULE.load_previous_freeze())
        MODULE.validate_contract(self.contract, self.profile)
        MODULE.validate_schema(self.schema)
        MODULE.validate_implementation_sources()
        MODULE.validate_freeze_record(self.freeze, self.contract, self.schema)

    def test_contract_checksum_rejects_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["endpoint"]["cursor_expired_status"] = 404
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "stage contract drift"):
            MODULE.validate_contract(changed, self.profile)

    def test_resource_allowlist_cannot_expand_early(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["resources"]["allowlist"].append("risk_gate")
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "resource allowlist drift"):
            MODULE.validate_contract(
                changed,
                self.profile,
                expected_checksum=MODULE.canonical_checksum(changed),
            )

    def test_decision_and_alert_resources_remain_blocked(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["decision_snapshot_resources_added"] = True
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "premature scope claim"):
            MODULE.validate_contract(
                changed,
                self.profile,
                expected_checksum=MODULE.canonical_checksum(changed),
            )

    def test_live_execution_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["live_execution_enabled"] = True
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "premature scope claim"):
            MODULE.validate_contract(
                changed,
                self.profile,
                expected_checksum=MODULE.canonical_checksum(changed),
            )

    def test_resource_schema_cannot_allow_external_orders(self) -> None:
        changed = copy.deepcopy(self.schema)
        changed["$defs"]["paper_shadow_portfolio"]["properties"][
            "external_order_submission_allowed"
        ] = {"const": True}
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "external order boundary"):
            MODULE.validate_schema(
                changed,
                expected_checksum=MODULE.canonical_checksum(changed),
            )

    def test_candidate_can_only_advance_to_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "TRD-V031-04"
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "only advance"):
            MODULE.validate_contract(
                changed,
                self.profile,
                expected_checksum=MODULE.canonical_checksum(changed),
            )

    def test_freeze_checksum_rejects_drift(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["candidate_tree_sha"] = "0" * 40
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "Freeze artifact drift"):
            MODULE.validate_freeze_record(changed, self.contract, self.schema)

    def test_freeze_rejects_failed_same_sha_workflow(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["workflows"]["portfolio_snapshot_resources"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "workflow failed"):
            MODULE.validate_freeze_record(
                changed,
                self.contract,
                self.schema,
                expected_checksum=MODULE.canonical_checksum(changed),
            )

    def test_freeze_does_not_open_nexora_before_real_provider_smoke(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["acceptance"]["nexora_p3_03_opened"] = True
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "premature Freeze claim"):
            MODULE.validate_freeze_record(
                changed,
                self.contract,
                self.schema,
                expected_checksum=MODULE.canonical_checksum(changed),
            )

    def test_freeze_opens_only_decision_snapshot_resources(self) -> None:
        changed = copy.deepcopy(self.freeze)
        changed["transition"]["next_allowed_stage"] = "TRD-V031-05"
        with self.assertRaisesRegex(MODULE.V031PortfolioSnapshotError, "post-Freeze stage drift"):
            MODULE.validate_freeze_record(
                changed,
                self.contract,
                self.schema,
                expected_checksum=MODULE.canonical_checksum(changed),
            )


if __name__ == "__main__":
    unittest.main()
