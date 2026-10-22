import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.verify_v0_3_phase_six import _specs

from trd_bot.outcome_learning import OutcomeLearningReadiness
from trd_bot.phase_six_acceptance import (
    PHASE_SIX_GATE_IDS,
    PhaseSixAcceptanceRecord,
    PhaseSixCapacityEvidence,
    PhaseSixCiEvidence,
    PhaseSixCommandEvidence,
    PhaseSixGateEvidence,
    PhaseSixInstallationEvidence,
    PhaseSixInventoryEvidence,
    PhaseSixMaintenanceEvidence,
    PhaseSixManualEvidence,
    PhaseSixOutcomeLearningEvidence,
    PhaseSixPriorFreezeEvidence,
    parse_phase_six_acceptance_record,
    serialize_phase_six_acceptance_record,
)

_SHA = "a" * 40
_NOW = datetime(2026, 10, 22, 16, tzinfo=UTC)
_INVENTORY_CHECKSUM = "b" * 64
_FINAL_RECORD = Path(__file__).resolve().parents[1] / "artifacts/p6-07/v0.3-final-acceptance.json"


def _gates(failed: str | None = None) -> tuple[PhaseSixGateEvidence, ...]:
    return tuple(
        PhaseSixGateEvidence(
            gate_id=gate_id,
            commands=(
                PhaseSixCommandEvidence(
                    label="gate",
                    command=("python", "-m", "pytest"),
                    exit_code=1 if gate_id == failed else 0,
                    duration_ms=1,
                ),
            ),
        )
        for gate_id in PHASE_SIX_GATE_IDS
    )


def _record(*, failed_gate: str | None = None) -> PhaseSixAcceptanceRecord:
    return PhaseSixAcceptanceRecord(
        candidate_commit_sha=_SHA,
        branch="feature/v0.3-market-intelligence",
        environment_label="macbook-pro-reference",
        generated_at=_NOW,
        prior_freeze=PhaseSixPriorFreezeEvidence(
            phase_five_record_checksum="c" * 64,
            phase_five_commit_sha="d" * 40,
            phase_five_ready=True,
        ),
        capacity=PhaseSixCapacityEvidence(
            artifact_checksum="e" * 64,
            report_checksum="f" * 64,
            commit_sha=_SHA,
            environment_label="macbook-pro-reference",
            generated_at=_NOW - timedelta(minutes=5),
            policy_checksum="1" * 64,
            passed=True,
        ),
        outcome_learning=PhaseSixOutcomeLearningEvidence(
            artifact_checksum="2" * 64,
            report_checksum="3" * 64,
            commit_sha=_SHA,
            environment_label="macbook-pro-reference",
            generated_at=_NOW - timedelta(minutes=4),
            policy_checksum="4" * 64,
            readiness=OutcomeLearningReadiness.OBSERVATIONAL,
            human_review_required=False,
            offline_only=True,
            automatic_policy_updates_applied=False,
            production_ml_training_performed=False,
        ),
        maintenance=PhaseSixMaintenanceEvidence(
            artifact_checksum="5" * 64,
            report_checksum="6" * 64,
            commit_sha=_SHA,
            environment_label="macbook-pro-reference",
            generated_at=_NOW - timedelta(minutes=3),
            policy_checksum="7" * 64,
            human_approval_required=False,
            retention_dry_run_audit_written=True,
            automatic_maintenance_executed=False,
            immutable_evidence_deletion_allowed=False,
        ),
        installation=PhaseSixInstallationEvidence(
            artifact_checksum="8" * 64,
            report_checksum="9" * 64,
            commit_sha=_SHA,
            environment_label="macbook-pro-reference",
            generated_at=_NOW - timedelta(minutes=2),
            source_migration_revision="20260926_0017",
            target_migration_revision="20261020_0036",
            release_inventory_checksum=_INVENTORY_CHECKSUM,
            passed=True,
        ),
        inventory=PhaseSixInventoryEvidence(
            definition_checksum=_INVENTORY_CHECKSUM,
            product_version="0.3.0",
            counts={
                "api_operations": 112,
                "database_tables": 55,
                "frontend_pages": 23,
                "jobs": 10,
                "migration_heads": 1,
                "migration_revisions": 36,
                "providers": 3,
            },
            passed=True,
        ),
        ci=PhaseSixCiEvidence(
            run_url="https://github.com/example/trd-bot/actions/runs/123",
            head_sha=_SHA,
            conclusion="success",
        ),
        manual=PhaseSixManualEvidence(
            fresh_install_upgrade_and_restore="pass",
            api_worker_ui_lifecycle="pass",
            outcome_learning_human_review="pass",
            retention_maintenance_closed="pass",
            paper_shadow_decision_lineage="pass",
            no_live_trading_security_inventory="pass",
        ),
        gates=_gates(failed_gate),
    )


def test_complete_evidence_freezes_v0_3() -> None:
    record = _record()

    assert record.ready_to_freeze_v0_3 is True
    assert record.failed_gates == ()
    assert (
        parse_phase_six_acceptance_record(serialize_phase_six_acceptance_record(record)) == record
    )
    assert len(record.record_checksum) == 64


def test_committed_final_acceptance_record_is_valid_when_present() -> None:
    if not _FINAL_RECORD.exists():
        return
    record = parse_phase_six_acceptance_record(_FINAL_RECORD.read_bytes())

    assert record.ready_to_freeze_v0_3 is True
    assert record.failed_gates == ()
    assert record.release_version == "0.3.0"


def test_failed_gate_blocks_v0_3_freeze() -> None:
    record = _record(failed_gate="frontend")

    assert record.ready_to_freeze_v0_3 is False
    assert record.failed_gates == ("frontend",)


def test_record_rejects_missing_gate_sha_environment_inventory_and_stale_evidence() -> None:
    baseline = _record()
    with pytest.raises(ValueError, match="every Phase 6 gate"):
        PhaseSixAcceptanceRecord.model_validate(
            {**baseline.model_dump(), "gates": [item.model_dump() for item in _gates()[:-1]]}
        )
    with pytest.raises(ValueError, match="Actions head SHA"):
        PhaseSixAcceptanceRecord.model_validate(
            {
                **baseline.model_dump(),
                "ci": {**baseline.ci.model_dump(), "head_sha": "1" * 40},
            }
        )
    with pytest.raises(ValueError, match="artifact environment"):
        PhaseSixAcceptanceRecord.model_validate(
            {
                **baseline.model_dump(),
                "capacity": {
                    **baseline.capacity.model_dump(),
                    "environment_label": "other",
                },
            }
        )
    with pytest.raises(ValueError, match="inventory checksums"):
        PhaseSixAcceptanceRecord.model_validate(
            {
                **baseline.model_dump(),
                "installation": {
                    **baseline.installation.model_dump(),
                    "release_inventory_checksum": "0" * 64,
                },
            }
        )
    with pytest.raises(ValueError, match="must be current"):
        PhaseSixAcceptanceRecord.model_validate(
            {**baseline.model_dump(), "generated_at": _NOW + timedelta(days=8)}
        )


@pytest.mark.parametrize(
    "field",
    ("ready_to_freeze_v0_3", "failed_gates", "record_checksum", "gate"),
)
def test_parser_rejects_tampered_derived_outcomes(field: str) -> None:
    payload = json.loads(serialize_phase_six_acceptance_record(_record()))
    if field == "ready_to_freeze_v0_3":
        payload[field] = False
    elif field == "failed_gates":
        payload[field] = ["backend"]
    elif field == "record_checksum":
        payload[field] = "0" * 64
    else:
        payload["gates"][0]["passed"] = False

    with pytest.raises(ValueError, match="inconsistent"):
        parse_phase_six_acceptance_record(json.dumps(payload))


def test_command_evidence_rejects_database_credentials() -> None:
    with pytest.raises(ValueError, match="database URLs"):
        PhaseSixCommandEvidence(
            label="unsafe",
            command=("tool", "postgresql+psycopg://user:secret@localhost/db"),
            exit_code=0,
            duration_ms=1,
        )


def test_final_gate_plan_matches_ci_and_uses_the_destructive_test_database() -> None:
    specs_by_gate = dict(_specs())
    assert tuple(specs_by_gate) == PHASE_SIX_GATE_IDS

    migration_commands = [command for _, command, _ in specs_by_gate["migration_cycle"]]
    postgresql_command = specs_by_gate["postgresql_resilience"][0][1]
    frontend_commands = [command for _, command, _ in specs_by_gate["frontend"]]

    assert any(
        ("downgrade", "base") in tuple(itertools.pairwise(command))
        for command in migration_commands
    )
    assert ("-m", "integration") in tuple(itertools.pairwise(postgresql_command))
    assert frontend_commands[0] == ("npm", "ci")
