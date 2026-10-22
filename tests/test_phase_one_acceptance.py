import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts import verify_v0_3_phase_one

from trd_bot.phase_one_acceptance import (
    PHASE_ONE_GATE_IDS,
    PhaseOneAcceptanceRecord,
    PhaseOneCiEvidence,
    PhaseOneCommandEvidence,
    PhaseOneGateEvidence,
    PhaseOneManualEvidence,
    parse_phase_one_acceptance_record,
    serialize_phase_one_acceptance_record,
)

COMMIT_SHA = "a" * 40
GENERATED_AT = datetime(2026, 10, 11, 8, tzinfo=UTC)


def command(*, exit_code: int = 0) -> PhaseOneCommandEvidence:
    return PhaseOneCommandEvidence(
        label="Acceptance command",
        command=("python", "-m", "pytest"),
        exit_code=exit_code,
        duration_ms=25,
    )


def gates(*, failed_gate: str | None = None) -> tuple[PhaseOneGateEvidence, ...]:
    return tuple(
        PhaseOneGateEvidence(
            gate_id=gate_id,
            commands=(command(exit_code=1 if gate_id == failed_gate else 0),),
        )
        for gate_id in PHASE_ONE_GATE_IDS
    )


def record(*, failed_gate: str | None = None) -> PhaseOneAcceptanceRecord:
    return PhaseOneAcceptanceRecord(
        commit_sha=COMMIT_SHA,
        branch="feature/v0.3-market-intelligence",
        environment_label="macbook-pro-reference",
        generated_at=GENERATED_AT,
        ci=PhaseOneCiEvidence(
            run_url="https://github.com/example/trd-bot/actions/runs/12345",
            head_sha=COMMIT_SHA,
            conclusion="success",
        ),
        manual=PhaseOneManualEvidence(
            local_api_worker_frontend="pass",
            durable_workload_restart="pass",
            monitoring_recovery="pass",
            security_network_inventory="pass",
        ),
        gates=gates(failed_gate=failed_gate),
    )


def test_complete_same_sha_evidence_accepts_entry_to_phase_two() -> None:
    accepted = record()

    assert accepted.ready_to_enter_phase_two is True
    assert accepted.failed_gates == ()
    assert (
        parse_phase_one_acceptance_record(serialize_phase_one_acceptance_record(accepted))
        == accepted
    )


def test_failed_gate_blocks_phase_two_and_is_serialized() -> None:
    rejected = record(failed_gate="postgresql_recovery")
    payload = json.loads(serialize_phase_one_acceptance_record(rejected))

    assert rejected.ready_to_enter_phase_two is False
    assert rejected.failed_gates == ("postgresql_recovery",)
    assert payload["ready_to_enter_phase_two"] is False
    assert payload["failed_gates"] == ["postgresql_recovery"]


def test_record_rejects_missing_gate_or_mismatched_ci_sha() -> None:
    with pytest.raises(ValueError, match="every Phase 1 gate in order"):
        PhaseOneAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "gates": [gate.model_dump() for gate in gates()[:-1]],
            }
        )

    with pytest.raises(ValueError, match="head SHA"):
        PhaseOneAcceptanceRecord(
            **{
                **record().model_dump(exclude={"ci"}),
                "ci": {
                    "run_url": "https://github.com/example/trd-bot/actions/runs/12345",
                    "head_sha": "b" * 40,
                    "conclusion": "success",
                },
            }
        )


def test_parser_rejects_tampered_derived_decision() -> None:
    payload = json.loads(serialize_phase_one_acceptance_record(record()))
    payload["ready_to_enter_phase_two"] = False

    with pytest.raises(ValueError, match="decision is inconsistent"):
        parse_phase_one_acceptance_record(json.dumps(payload))


def test_database_validation_allows_only_disposable_postgresql_database() -> None:
    accepted = "postgresql+psycopg://user:password@localhost:55434/trd_bot_test"

    assert verify_v0_3_phase_one._validate_database_url(accepted) == accepted
    with pytest.raises(ValueError, match="only against trd_bot_test"):
        verify_v0_3_phase_one._validate_database_url(
            "postgresql+psycopg://user:password@localhost:55434/trd_bot"
        )
    with pytest.raises(ValueError, match="requires PostgreSQL"):
        verify_v0_3_phase_one._validate_database_url("sqlite:///trd_bot_test.sqlite3")


def test_acceptance_cli_writes_sanitized_same_sha_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "phase-one-acceptance.json"
    database_url = "postgresql+psycopg://user:secret@localhost:55434/trd_bot_test"
    monkeypatch.setattr(
        verify_v0_3_phase_one,
        "_repository_identity",
        lambda: (COMMIT_SHA, "feature/v0.3-market-intelligence"),
    )
    monkeypatch.setattr(
        verify_v0_3_phase_one,
        "_run_gate",
        lambda *, gate_id, commands, environment: PhaseOneGateEvidence(
            gate_id=gate_id,
            commands=(command(),),
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_v0_3_phase_one.py",
            "--database-url",
            database_url,
            "--confirm-destructive-migration-cycle",
            "trd_bot_test",
            "--github-actions-run-url",
            "https://github.com/example/trd-bot/actions/runs/12345",
            "--github-actions-head-sha",
            COMMIT_SHA,
            "--github-actions-conclusion",
            "success",
            "--local-stack-smoke",
            "pass",
            "--durable-restart-smoke",
            "pass",
            "--monitoring-recovery-smoke",
            "pass",
            "--security-network-smoke",
            "pass",
            "--environment-label",
            "macbook-pro-reference",
            "--output",
            str(output),
        ],
    )

    assert verify_v0_3_phase_one.main() == 0
    serialized = output.read_text(encoding="utf-8")
    parsed = parse_phase_one_acceptance_record(serialized)
    assert parsed.ready_to_enter_phase_two is True
    assert "secret" not in serialized
