from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import unittest
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ACCEPTANCE = load_script("v0_3_1_stage_acceptance")
FETCH = load_script("fetch_v0_3_1_acceptance_evidence")


class V031StageAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ACCEPTANCE.load_policy()
        self.manifest = ACCEPTANCE.load_manifest("TRD-V031-05")
        self.gates = {name: "success" for name in self.policy["workflow"]["required_gates"]}

    def candidate_manifest(self) -> dict[str, Any]:
        manifest = copy.deepcopy(self.manifest)
        manifest["status"] = "candidate"
        manifest["evidence_paths"] = ["contracts/trd-bot-v0.3.1-stage-acceptance-policy.json"]
        return cast(dict[str, Any], manifest)

    def build(self, **changes: object) -> dict[str, Any]:
        arguments: dict[str, object] = {
            "repository": "amirhosseinhamidian/trd-bot-v2",
            "commit_sha": "1" * 40,
            "tree_sha": "2" * 40,
            "ref": "refs/heads/feature/v0.3.1-nexora-integration",
            "run_id": 123,
            "run_attempt": 1,
            "event": "push",
            "gates": self.gates,
            "artifact_checksums": {"candidate": "3" * 64},
            "generated_at": datetime(2026, 11, 7, 12, tzinfo=UTC),
        }
        arguments.update(changes)
        return cast(
            dict[str, Any],
            ACCEPTANCE.build_evidence(
                self.policy,
                self.candidate_manifest(),
                **arguments,
            ),
        )

    def test_policy_manifest_schema_and_historical_freezes_are_valid(self) -> None:
        ACCEPTANCE.validate_policy(self.policy)
        ACCEPTANCE.validate_evidence_schema(ACCEPTANCE.load_evidence_schema())
        ACCEPTANCE.validate_historical_freezes(self.policy)
        ACCEPTANCE.validate_manifest(self.policy, self.manifest)
        ACCEPTANCE.validate_prerequisite(self.policy, self.manifest)

    def test_actual_next_stage_uses_integrated_acceptance(self) -> None:
        self.assertEqual(self.policy["effective_from_stage"], "TRD-V031-05")
        self.assertFalse(self.policy["workflow"]["separate_stage_freeze_required"])
        self.assertEqual(
            [stage["id"] for stage in self.policy["stages"]],
            [f"TRD-V031-{number:02d}" for number in range(5, 12)],
        )

    def test_historical_freeze_checksum_cannot_drift(self) -> None:
        changed = copy.deepcopy(self.policy)
        changed["historical_freezes"][4]["canonical_checksum"] = "0" * 64
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "historical Freeze drift"):
            ACCEPTANCE.validate_historical_freezes(changed)

    def test_live_execution_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.policy)
        changed["safety"]["live_execution"] = True
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "live_execution"):
            ACCEPTANCE.validate_policy(changed)

    def test_nexora_smoke_gate_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.policy)
        changed["safety"]["nexora_p3_03_requires_real_local_provider_smoke"] = False
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "smoke requirement"):
            ACCEPTANCE.validate_policy(changed)

    def test_candidate_stage_is_runnable_but_planned_stage_is_not(self) -> None:
        ACCEPTANCE.validate_manifest(self.policy, self.manifest, require_candidate=True)
        planned = copy.deepcopy(self.manifest)
        planned["status"] = "planned"
        with self.assertRaisesRegex(
            ACCEPTANCE.StageAcceptanceError, "not an implementation candidate"
        ):
            ACCEPTANCE.validate_manifest(self.policy, planned, require_candidate=True)

    def test_successful_push_accepts_and_opens_only_the_next_stage(self) -> None:
        evidence = self.build()
        ACCEPTANCE.validate_evidence(
            self.policy,
            evidence,
            expected_stage_id="TRD-V031-05",
            expected_commit_sha="1" * 40,
        )
        self.assertEqual(evidence["overall_result"], "accepted")
        self.assertTrue(evidence["accepted"])
        self.assertEqual(evidence["transition"], {"next_stage": "TRD-V031-06", "opened": True})

    def test_pull_request_is_validation_only(self) -> None:
        evidence = self.build(event="pull_request")
        ACCEPTANCE.validate_evidence(self.policy, evidence)
        self.assertEqual(evidence["overall_result"], "validation_only")
        self.assertFalse(evidence["transition"]["opened"])

    def test_failed_gate_rejects_acceptance(self) -> None:
        gates = dict(self.gates)
        gates["postgresql"] = "failure"
        evidence = self.build(gates=gates)
        ACCEPTANCE.validate_evidence(self.policy, evidence)
        self.assertEqual(evidence["overall_result"], "rejected")
        self.assertFalse(evidence["accepted"])

    def test_cancelled_gate_rejects_acceptance(self) -> None:
        gates = dict(self.gates)
        gates["frontend"] = "cancelled"
        evidence = self.build(gates=gates)
        self.assertEqual(evidence["overall_result"], "rejected")
        self.assertFalse(evidence["transition"]["opened"])

    def test_skipped_gate_is_incomplete(self) -> None:
        gates = dict(self.gates)
        gates["security"] = "skipped"
        evidence = self.build(gates=gates)
        ACCEPTANCE.validate_evidence(self.policy, evidence)
        self.assertEqual(evidence["overall_result"], "incomplete")
        self.assertFalse(evidence["transition"]["opened"])

    def test_missing_gate_result_is_rejected_before_generation(self) -> None:
        gates = dict(self.gates)
        gates.pop("backend")
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "gate result inventory"):
            self.build(gates=gates)

    def test_evidence_checksum_detects_drift(self) -> None:
        evidence = self.build()
        evidence["git"]["commit_sha"] = "4" * 40
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "evidence checksum drift"):
            ACCEPTANCE.validate_evidence(self.policy, evidence)

    def test_secret_like_material_is_rejected(self) -> None:
        evidence = self.build()
        evidence["token"] = "github_pat_" + "x" * 30
        evidence["evidence_checksum"] = ACCEPTANCE.canonical_checksum(
            evidence,
            exclude=frozenset({"evidence_checksum"}),
        )
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "secret-like evidence key"):
            ACCEPTANCE.validate_evidence(self.policy, evidence)

    def test_wrong_commit_cannot_satisfy_prerequisite(self) -> None:
        evidence = self.build()
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "unexpected accepted commit"):
            ACCEPTANCE.validate_evidence(
                self.policy,
                evidence,
                expected_commit_sha="9" * 40,
            )

    def test_artifact_selection_is_same_sha_and_unexpired(self) -> None:
        name = "TRD-V031-05-acceptance-" + "1" * 40
        payload = {
            "artifacts": [
                {
                    "id": 10,
                    "name": name,
                    "expired": False,
                    "archive_download_url": "https://api.github.com/example",
                    "workflow_run": {"head_sha": "1" * 40},
                },
                {
                    "id": 11,
                    "name": name,
                    "expired": True,
                    "workflow_run": {"head_sha": "1" * 40},
                },
            ]
        }
        selected = FETCH.select_artifact(payload, artifact_name=name, commit_sha="1" * 40)
        self.assertEqual(selected["id"], 10)

    def test_ambiguous_artifacts_fail_closed(self) -> None:
        name = "TRD-V031-05-acceptance-" + "1" * 40
        item = {
            "name": name,
            "expired": False,
            "workflow_run": {"head_sha": "1" * 40},
        }
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "found 2"):
            FETCH.select_artifact(
                {"artifacts": [item, dict(item)]},
                artifact_name=name,
                commit_sha="1" * 40,
            )

    def test_evidence_archive_must_contain_one_root_json(self) -> None:
        expected = self.build()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            bundle.writestr("acceptance-evidence.json", json.dumps(expected))
        self.assertEqual(FETCH.extract_evidence(buffer.getvalue()), expected)

        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w") as bundle:
            bundle.writestr("nested/acceptance-evidence.json", json.dumps(expected))
        with self.assertRaisesRegex(ACCEPTANCE.StageAcceptanceError, "root evidence"):
            FETCH.extract_evidence(nested.getvalue())


if __name__ == "__main__":
    unittest.main()
