from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_v0_3_1_snapshot_protocol", ROOT / "scripts/verify_v0_3_1_snapshot_protocol.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load v0.3.1 snapshot protocol verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class V031SnapshotProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_contract()
        self.profile = MODULE.load_profile()

    def test_candidate_matches_frozen_snapshot_profile(self) -> None:
        MODULE.validate_stage_contract(self.contract, self.profile)
        MODULE.validate_schemas(
            MODULE.load_source_reference_schema(), MODULE.load_snapshot_page_schema()
        )
        MODULE.validate_previous_freeze()
        MODULE.validate_implementation_sources()

    def test_contract_checksum_rejects_drift(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["protocol"]["maximum_page_limit"] = 1000
        with self.assertRaisesRegex(MODULE.V031SnapshotProtocolError, "stage contract drift"):
            MODULE.validate_stage_contract(changed, self.profile)

    def test_stage_cannot_claim_resources_early(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["scope"]["portfolio_snapshot_resources_added"] = True
        with self.assertRaisesRegex(MODULE.V031SnapshotProtocolError, "premature scope claim"):
            MODULE.validate_stage_contract(
                changed, self.profile, expected_checksum=MODULE.canonical_checksum(changed)
            )

    def test_candidate_can_only_advance_to_freeze(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["transition"]["next_allowed_stage"] = "TRD-V031-03"
        with self.assertRaisesRegex(MODULE.V031SnapshotProtocolError, "only advance"):
            MODULE.validate_stage_contract(
                changed, self.profile, expected_checksum=MODULE.canonical_checksum(changed)
            )


if __name__ == "__main__":
    unittest.main()
