import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from scripts import verify_v0_3_phase_two

from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
)
from trd_bot.phase_two_acceptance import (
    PHASE_TWO_GATE_IDS,
    PhaseTwoAcceptanceRecord,
    PhaseTwoCiEvidence,
    PhaseTwoCommandEvidence,
    PhaseTwoGateEvidence,
    PhaseTwoManualEvidence,
    PhaseTwoPriorFreezeEvidence,
    PhaseTwoProviderEvidence,
    evaluate_phase_two_provider_evidence,
    parse_phase_two_acceptance_record,
    serialize_phase_two_acceptance_record,
)

COMMIT_SHA = "a" * 40
GENERATED_AT = datetime(2026, 10, 15, 8, tzinfo=UTC)


def command(*, exit_code: int = 0) -> PhaseTwoCommandEvidence:
    return PhaseTwoCommandEvidence(
        label="Acceptance command",
        command=("python", "-m", "pytest"),
        exit_code=exit_code,
        duration_ms=25,
    )


def gates(*, failed_gate: str | None = None) -> tuple[PhaseTwoGateEvidence, ...]:
    return tuple(
        PhaseTwoGateEvidence(
            gate_id=gate_id,
            commands=(command(exit_code=1 if gate_id == failed_gate else 0),),
        )
        for gate_id in PHASE_TWO_GATE_IDS
    )


def prior_freezes() -> PhaseTwoPriorFreezeEvidence:
    return PhaseTwoPriorFreezeEvidence(
        phase_zero_record_checksum="b" * 64,
        phase_zero_commit_sha="c" * 40,
        phase_zero_ready=True,
        phase_one_record_checksum="d" * 64,
        phase_one_commit_sha="e" * 40,
        phase_one_ready=True,
    )


def provider_evidence(*, failed: bool = False) -> PhaseTwoProviderEvidence:
    return PhaseTwoProviderEvidence(
        report_checksum="f" * 64,
        report_commit_sha=COMMIT_SHA,
        report_environment_label="macbook-pro-reference",
        report_generated_at=GENERATED_AT,
        observations={
            "kraken-public.samples": Decimal(30),
            "kraken-public.failure_fraction": Decimal(0),
            "kraken-public.http_latency_p95_ms": Decimal(900),
            "binance-public.samples": Decimal(30),
            "binance-public.failure_fraction": Decimal(0),
            "binance-public.http_latency_p95_ms": Decimal(1_100),
        },
        failure_reasons=("provider exceeds its latency budget",) if failed else (),
    )


def record(
    *,
    failed_gate: str | None = None,
    provider_failed: bool = False,
) -> PhaseTwoAcceptanceRecord:
    return PhaseTwoAcceptanceRecord(
        commit_sha=COMMIT_SHA,
        branch="feature/v0.3-market-intelligence",
        environment_label="macbook-pro-reference",
        generated_at=GENERATED_AT,
        prior_freezes=prior_freezes(),
        provider=provider_evidence(failed=provider_failed),
        ci=PhaseTwoCiEvidence(
            run_url="https://github.com/example/trd-bot/actions/runs/12345",
            head_sha=COMMIT_SHA,
            conclusion="success",
        ),
        manual=PhaseTwoManualEvidence(
            local_api_worker_frontend="pass",
            watchlist_fallback_freshness="pass",
            worker_restart_deduplication="pass",
            late_data_replay_monitoring="pass",
            retention_hold_and_dry_run="pass",
            security_network_inventory="pass",
        ),
        gates=gates(failed_gate=failed_gate),
    )


def provider_report(*, failing: bool = False) -> CapacityBenchmarkReport:
    return CapacityBenchmarkReport(
        environment_label="macbook-pro-reference",
        commit_sha=COMMIT_SHA,
        generated_at=GENERATED_AT,
        python_version="3.12.14",
        platform="macOS-reference",
        evidence=(
            CapacityEvidence(
                scope=CapacityEvidenceScope.PROVIDER,
                method=CapacityEvidenceMethod.LIVE_PROBE,
                complete=True,
                observed_count=60,
                metrics={
                    "kraken-public.samples": Decimal(30),
                    "kraken-public.failure_fraction": Decimal("0.02") if failing else Decimal(0),
                    "kraken-public.http_latency_p95_ms": Decimal(900),
                    "binance-public.samples": Decimal(30),
                    "binance-public.failure_fraction": Decimal(0),
                    "binance-public.http_latency_p95_ms": Decimal(3_001)
                    if failing
                    else Decimal(1_100),
                },
            ),
        ),
    )


def test_complete_same_sha_evidence_freezes_phase_two() -> None:
    accepted = record()

    assert accepted.ready_to_freeze_phase_two is True
    assert accepted.failed_gates == ()
    assert (
        parse_phase_two_acceptance_record(serialize_phase_two_acceptance_record(accepted))
        == accepted
    )


@pytest.mark.parametrize(
    ("failed_gate", "provider_failed"),
    (("postgresql_resilience", False), (None, True)),
)
def test_failed_automated_or_provider_gate_blocks_freeze(
    failed_gate: str | None,
    provider_failed: bool,
) -> None:
    rejected = record(failed_gate=failed_gate, provider_failed=provider_failed)
    payload = json.loads(serialize_phase_two_acceptance_record(rejected))

    assert rejected.ready_to_freeze_phase_two is False
    assert payload["ready_to_freeze_phase_two"] is False
    assert payload["provider"]["passed"] is (not provider_failed)


def test_record_rejects_missing_gate_and_mismatched_same_sha_evidence() -> None:
    with pytest.raises(ValueError, match="every Phase 2 gate in order"):
        PhaseTwoAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "gates": [gate.model_dump() for gate in gates()[:-1]],
            }
        )

    with pytest.raises(ValueError, match="GitHub Actions head SHA"):
        PhaseTwoAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "ci": {
                    "run_url": "https://github.com/example/trd-bot/actions/runs/12345",
                    "head_sha": "1" * 40,
                    "conclusion": "success",
                },
            }
        )

    with pytest.raises(ValueError, match="provider report SHA"):
        PhaseTwoAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "provider": {
                    **provider_evidence().model_dump(),
                    "report_commit_sha": "2" * 40,
                },
            }
        )

    with pytest.raises(ValueError, match="provider report environment"):
        PhaseTwoAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "provider": {
                    **provider_evidence().model_dump(),
                    "report_environment_label": "different-environment",
                },
            }
        )

    with pytest.raises(ValueError, match="current at acceptance time"):
        PhaseTwoAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "provider": {
                    **provider_evidence().model_dump(),
                    "report_generated_at": GENERATED_AT - timedelta(days=366),
                },
            }
        )


@pytest.mark.parametrize(
    "field",
    ("ready_to_freeze_phase_two", "failed_gates", "provider.passed", "gates.0.passed"),
)
def test_parser_rejects_tampered_derived_outcomes(field: str) -> None:
    payload = json.loads(serialize_phase_two_acceptance_record(record()))
    if field == "ready_to_freeze_phase_two":
        payload[field] = False
    elif field == "failed_gates":
        payload[field] = ["backend"]
    elif field == "provider.passed":
        payload["provider"]["passed"] = False
    else:
        payload["gates"][0]["passed"] = False

    with pytest.raises(ValueError, match="inconsistent"):
        parse_phase_two_acceptance_record(json.dumps(payload))


def test_live_provider_evidence_is_evaluated_against_frozen_budgets() -> None:
    accepted = evaluate_phase_two_provider_evidence(
        provider_report(),
        report_checksum="3" * 64,
    )
    rejected = evaluate_phase_two_provider_evidence(
        provider_report(failing=True),
        report_checksum="4" * 64,
    )

    assert accepted.passed is True
    assert accepted.primary_provider == "kraken-public"
    assert accepted.fallback_providers == ("binance-public",)
    assert rejected.passed is False
    assert any("failure budget" in reason for reason in rejected.failure_reasons)
    assert any("latency budget" in reason for reason in rejected.failure_reasons)


def test_passing_provider_evidence_rejects_missing_or_out_of_budget_metrics() -> None:
    payload = provider_evidence().model_dump()
    observations = dict(payload["observations"])
    observations.pop("binance-public.samples")
    with pytest.raises(ValueError, match="every frozen SLO metric"):
        PhaseTwoProviderEvidence.model_validate({**payload, "observations": observations})

    observations = dict(payload["observations"])
    observations["kraken-public.http_latency_p95_ms"] = Decimal(3_001)
    with pytest.raises(ValueError, match="latency budget"):
        PhaseTwoProviderEvidence.model_validate({**payload, "observations": observations})


def test_database_validation_allows_only_disposable_postgresql_database() -> None:
    accepted = "postgresql+psycopg://user:password@localhost:55435/trd_bot_test"

    assert verify_v0_3_phase_two._validate_database_url(accepted) == accepted
    with pytest.raises(ValueError, match="only against trd_bot_test"):
        verify_v0_3_phase_two._validate_database_url(
            "postgresql+psycopg://user:password@localhost:55435/trd_bot"
        )
    with pytest.raises(ValueError, match="requires PostgreSQL"):
        verify_v0_3_phase_two._validate_database_url("sqlite:///trd_bot_test.sqlite3")


def test_acceptance_cli_writes_sanitized_same_sha_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "phase-two-acceptance.json"
    database_url = "postgresql+psycopg://user:secret@localhost:55435/trd_bot_test"
    monkeypatch.setattr(
        verify_v0_3_phase_two,
        "_repository_identity",
        lambda: (COMMIT_SHA, "feature/v0.3-market-intelligence"),
    )
    monkeypatch.setattr(
        verify_v0_3_phase_two,
        "_load_prior_freezes",
        lambda phase_zero_path, phase_one_path: prior_freezes(),
    )
    monkeypatch.setattr(
        verify_v0_3_phase_two,
        "_load_provider_evidence",
        lambda path, commit_sha: PhaseTwoProviderEvidence.model_validate(
            {
                **provider_evidence().model_dump(),
                "report_generated_at": datetime.now(UTC),
            }
        ),
    )
    monkeypatch.setattr(
        verify_v0_3_phase_two,
        "_run_gate",
        lambda *, gate_id, commands, environment: PhaseTwoGateEvidence(
            gate_id=gate_id,
            commands=(command(),),
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_v0_3_phase_two.py",
            "--database-url",
            database_url,
            "--confirm-destructive-migration-cycle",
            "trd_bot_test",
            "--provider-capacity-report",
            str(tmp_path / "provider.json"),
            "--github-actions-run-url",
            "https://github.com/example/trd-bot/actions/runs/12345",
            "--github-actions-head-sha",
            COMMIT_SHA,
            "--github-actions-conclusion",
            "success",
            "--local-stack-smoke",
            "pass",
            "--watchlist-fallback-smoke",
            "pass",
            "--worker-restart-smoke",
            "pass",
            "--late-data-replay-smoke",
            "pass",
            "--retention-hold-smoke",
            "pass",
            "--security-network-smoke",
            "pass",
            "--environment-label",
            "macbook-pro-reference",
            "--output",
            str(output),
        ],
    )

    assert verify_v0_3_phase_two.main() == 0
    serialized = output.read_text(encoding="utf-8")
    parsed = parse_phase_two_acceptance_record(serialized)
    assert parsed.ready_to_freeze_phase_two is True
    assert "secret" not in serialized


def test_python_executable_is_sanitized_in_command_evidence() -> None:
    sanitized = verify_v0_3_phase_two._sanitized_command((sys.executable, "-m", "pytest"))

    assert sanitized == ("python", "-m", "pytest")
