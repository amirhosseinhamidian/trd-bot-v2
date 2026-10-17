import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from scripts import verify_v0_3_phase_three

from trd_bot.market_context import (
    MarketContextGoldenBenchmarkReport,
    MarketContextGoldenScenarioEvidence,
    market_context_feature_set_v1,
    market_context_golden_fixture_v1,
    market_regime_policy_v1,
)
from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
)
from trd_bot.phase_three_acceptance import (
    PHASE_THREE_BACKGROUND_FIXTURE_REFERENCE,
    PHASE_THREE_GATE_IDS,
    PhaseThreeAcceptanceRecord,
    PhaseThreeBackgroundJobEvidence,
    PhaseThreeCiEvidence,
    PhaseThreeCommandEvidence,
    PhaseThreeGateEvidence,
    PhaseThreeGoldenEvidence,
    PhaseThreeManualEvidence,
    PhaseThreePriorFreezeEvidence,
    evaluate_phase_three_background_job_evidence,
    evaluate_phase_three_golden_evidence,
    parse_phase_three_acceptance_record,
    serialize_phase_three_acceptance_record,
)

COMMIT_SHA = "a" * 40
GENERATED_AT = datetime(2026, 10, 17, 8, tzinfo=UTC)
ENVIRONMENT = "macbook-pro-reference"


def command(*, exit_code: int = 0) -> PhaseThreeCommandEvidence:
    return PhaseThreeCommandEvidence(
        label="Acceptance command",
        command=("python", "-m", "pytest"),
        exit_code=exit_code,
        duration_ms=25,
    )


def gates(*, failed_gate: str | None = None) -> tuple[PhaseThreeGateEvidence, ...]:
    return tuple(
        PhaseThreeGateEvidence(
            gate_id=gate_id,
            commands=(command(exit_code=1 if gate_id == failed_gate else 0),),
        )
        for gate_id in PHASE_THREE_GATE_IDS
    )


def prior_freeze() -> PhaseThreePriorFreezeEvidence:
    return PhaseThreePriorFreezeEvidence(
        phase_two_record_checksum="b" * 64,
        phase_two_commit_sha="c" * 40,
        phase_two_ready=True,
    )


def golden_observations() -> dict[str, Decimal]:
    return {
        f"{scenario_id}.{suffix}": value
        for scenario_id in ("trending_up_low", "trending_down_high", "ranging_normal")
        for suffix, value in (("samples", Decimal(30)), ("runtime_p95_ms", Decimal(20)))
    }


def golden_evidence(*, failed: bool = False) -> PhaseThreeGoldenEvidence:
    fixture = market_context_golden_fixture_v1()
    return PhaseThreeGoldenEvidence(
        report_checksum="d" * 64,
        report_commit_sha=COMMIT_SHA,
        report_environment_label=ENVIRONMENT,
        report_generated_at=GENERATED_AT,
        fixture_checksum=fixture.definition_checksum,
        feature_set_checksum=market_context_feature_set_v1().definition_checksum,
        algorithm_policy_checksum=market_regime_policy_v1().definition_checksum,
        observations=golden_observations(),
        failure_reasons=("golden scenario did not pass",) if failed else (),
    )


def background_observations() -> dict[str, Decimal]:
    return {
        "queue_wait_p95_ms": Decimal(100),
        "market_context_evaluation.samples": Decimal(20),
        "market_context_evaluation.success_fraction": Decimal(1),
        "market_context_evaluation.failure_count": Decimal(0),
        "market_context_evaluation.runtime_p95_seconds": Decimal("0.1"),
        "market_context_evaluation.runtime_target_seconds": Decimal(30),
        "market_context_evaluation.runtime_within_target": Decimal(1),
        "market_context_evaluation.fixture_finalized_windows": Decimal(56),
        "market_context_evaluation.fixture_features": Decimal(5),
    }


def background_evidence(*, failed: bool = False) -> PhaseThreeBackgroundJobEvidence:
    return PhaseThreeBackgroundJobEvidence(
        report_checksum="e" * 64,
        report_commit_sha=COMMIT_SHA,
        report_environment_label=ENVIRONMENT,
        report_generated_at=GENERATED_AT,
        fixture_reference=PHASE_THREE_BACKGROUND_FIXTURE_REFERENCE,
        observed_count=410,
        observations=background_observations(),
        failure_reasons=("background fixture is incomplete",) if failed else (),
    )


def record(
    *,
    failed_gate: str | None = None,
    golden_failed: bool = False,
    background_failed: bool = False,
) -> PhaseThreeAcceptanceRecord:
    return PhaseThreeAcceptanceRecord(
        commit_sha=COMMIT_SHA,
        branch="feature/v0.3-market-intelligence",
        environment_label=ENVIRONMENT,
        generated_at=GENERATED_AT,
        prior_freeze=prior_freeze(),
        golden=golden_evidence(failed=golden_failed),
        background_jobs=background_evidence(failed=background_failed),
        ci=PhaseThreeCiEvidence(
            run_url="https://github.com/example/trd-bot/actions/runs/12345",
            head_sha=COMMIT_SHA,
            conclusion="success",
        ),
        manual=PhaseThreeManualEvidence(
            local_api_worker_frontend="pass",
            context_generation_and_ui="pass",
            stale_context_fail_closed="pass",
            worker_restart_deduplication="pass",
            monitoring_freshness_recovery="pass",
            security_network_inventory="pass",
        ),
        gates=gates(failed_gate=failed_gate),
    )


def golden_report(*, samples: int = 30) -> MarketContextGoldenBenchmarkReport:
    fixture = market_context_golden_fixture_v1()
    scenarios = tuple(
        MarketContextGoldenScenarioEvidence(
            scenario_id=definition.scenario_id,
            requested_samples=samples,
            successful_samples=samples,
            failed_samples=0,
            expected=definition.expected,
            observed=definition.expected,
            unique_output_fingerprints=(definition.expected.output_fingerprint,),
            runtime_p50_ms=Decimal(10),
            runtime_p95_ms=Decimal(20),
            runtime_budget_ms=Decimal(30_000),
        )
        for definition in fixture.scenarios
    )
    return MarketContextGoldenBenchmarkReport(
        fixture_checksum=fixture.definition_checksum,
        commit_sha=COMMIT_SHA,
        environment_label=ENVIRONMENT,
        generated_at=GENERATED_AT,
        python_version="3.12.14",
        platform="macOS-reference",
        feature_set_checksum=market_context_feature_set_v1().definition_checksum,
        algorithm_policy_checksum=market_regime_policy_v1().definition_checksum,
        warmup_iterations=2,
        scenarios=scenarios,
    )


def background_report(*, failing: bool = False) -> CapacityBenchmarkReport:
    metrics = background_observations()
    if failing:
        metrics["market_context_evaluation.runtime_p95_seconds"] = Decimal(31)
        metrics["market_context_evaluation.runtime_within_target"] = Decimal(0)
    return CapacityBenchmarkReport(
        environment_label=ENVIRONMENT,
        commit_sha=COMMIT_SHA,
        generated_at=GENERATED_AT,
        python_version="3.12.14",
        platform="macOS-reference",
        evidence=(
            CapacityEvidence(
                scope=CapacityEvidenceScope.BACKGROUND_JOBS,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=True,
                observed_count=410,
                metrics=metrics,
                evidence_reference=PHASE_THREE_BACKGROUND_FIXTURE_REFERENCE,
                limitation=(
                    "Runtime uses canonical in-memory repositories; PostgreSQL queue persistence "
                    "is measured independently in the attached queue evidence."
                ),
            ),
        ),
    )


def test_complete_same_sha_evidence_freezes_phase_three() -> None:
    accepted = record()

    assert accepted.ready_to_freeze_phase_three is True
    assert accepted.failed_gates == ()
    assert (
        parse_phase_three_acceptance_record(serialize_phase_three_acceptance_record(accepted))
        == accepted
    )


@pytest.mark.parametrize(
    ("failed_gate", "golden_failed", "background_failed"),
    (
        ("postgresql_resilience", False, False),
        (None, True, False),
        (None, False, True),
    ),
)
def test_any_failed_gate_or_benchmark_blocks_freeze(
    failed_gate: str | None,
    golden_failed: bool,
    background_failed: bool,
) -> None:
    rejected = record(
        failed_gate=failed_gate,
        golden_failed=golden_failed,
        background_failed=background_failed,
    )
    payload = json.loads(serialize_phase_three_acceptance_record(rejected))

    assert rejected.ready_to_freeze_phase_three is False
    assert payload["ready_to_freeze_phase_three"] is False


def test_record_rejects_missing_gate_mismatched_sha_environment_and_stale_evidence() -> None:
    with pytest.raises(ValueError, match="every Phase 3 gate in order"):
        PhaseThreeAcceptanceRecord.model_validate(
            {**record().model_dump(), "gates": [item.model_dump() for item in gates()[:-1]]}
        )

    with pytest.raises(ValueError, match="GitHub Actions head SHA"):
        PhaseThreeAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "ci": {
                    "run_url": "https://github.com/example/trd-bot/actions/runs/12345",
                    "head_sha": "1" * 40,
                    "conclusion": "success",
                },
            }
        )

    with pytest.raises(ValueError, match="golden report SHA"):
        PhaseThreeAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "golden": {
                    **golden_evidence().model_dump(),
                    "report_commit_sha": "2" * 40,
                },
            }
        )

    with pytest.raises(ValueError, match="background-job report environment"):
        PhaseThreeAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "background_jobs": {
                    **background_evidence().model_dump(),
                    "report_environment_label": "different-environment",
                },
            }
        )

    with pytest.raises(ValueError, match="golden report must be current"):
        PhaseThreeAcceptanceRecord.model_validate(
            {
                **record().model_dump(),
                "golden": {
                    **golden_evidence().model_dump(),
                    "report_generated_at": GENERATED_AT - timedelta(days=366),
                },
            }
        )


@pytest.mark.parametrize(
    "field",
    (
        "ready_to_freeze_phase_three",
        "failed_gates",
        "golden.passed",
        "background_jobs.passed",
        "gates.0.passed",
    ),
)
def test_parser_rejects_tampered_derived_outcomes(field: str) -> None:
    payload = json.loads(serialize_phase_three_acceptance_record(record()))
    if field == "ready_to_freeze_phase_three":
        payload[field] = False
    elif field == "failed_gates":
        payload[field] = ["backend"]
    elif field == "golden.passed":
        payload["golden"]["passed"] = False
    elif field == "background_jobs.passed":
        payload["background_jobs"]["passed"] = False
    else:
        payload["gates"][0]["passed"] = False

    with pytest.raises(ValueError, match="inconsistent"):
        parse_phase_three_acceptance_record(json.dumps(payload))


def test_golden_report_is_independently_evaluated() -> None:
    accepted = evaluate_phase_three_golden_evidence(
        golden_report(),
        report_checksum="f" * 64,
    )
    rejected = evaluate_phase_three_golden_evidence(
        golden_report(samples=29),
        report_checksum="1" * 64,
    )

    assert accepted.passed is True
    assert accepted.observations["trending_up_low.samples"] == 30
    assert rejected.passed is False
    assert any("did not pass" in reason for reason in rejected.failure_reasons)


def test_background_report_is_independently_evaluated() -> None:
    accepted = evaluate_phase_three_background_job_evidence(
        background_report(),
        report_checksum="f" * 64,
    )
    rejected = evaluate_phase_three_background_job_evidence(
        background_report(failing=True),
        report_checksum="1" * 64,
    )

    assert accepted.passed is True
    assert accepted.observations["market_context_evaluation.samples"] == 20
    assert rejected.passed is False
    assert any("runtime budget" in reason for reason in rejected.failure_reasons)


def test_passing_evidence_rejects_missing_or_out_of_budget_observations() -> None:
    golden_payload = golden_evidence().model_dump()
    golden_metrics = dict(golden_payload["observations"])
    golden_metrics.pop("ranging_normal.samples")
    with pytest.raises(ValueError, match="every frozen observation"):
        PhaseThreeGoldenEvidence.model_validate({**golden_payload, "observations": golden_metrics})

    background_payload = background_evidence().model_dump()
    background_metrics = dict(background_payload["observations"])
    background_metrics["queue_wait_p95_ms"] = Decimal(10_001)
    with pytest.raises(ValueError, match="queue-wait budget"):
        PhaseThreeBackgroundJobEvidence.model_validate(
            {**background_payload, "observations": background_metrics}
        )


def test_database_validation_allows_only_disposable_postgresql_database() -> None:
    accepted = "postgresql+psycopg://user:password@localhost:55437/trd_bot_test"

    assert verify_v0_3_phase_three._validate_database_url(accepted) == accepted
    with pytest.raises(ValueError, match="only against trd_bot_test"):
        verify_v0_3_phase_three._validate_database_url(
            "postgresql+psycopg://user:password@localhost:55437/trd_bot"
        )
    with pytest.raises(ValueError, match="requires PostgreSQL"):
        verify_v0_3_phase_three._validate_database_url("sqlite:///trd_bot_test.sqlite3")


def test_acceptance_cli_writes_sanitized_same_sha_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "phase-three-acceptance.json"
    database_url = "postgresql+psycopg://user:secret@localhost:55437/trd_bot_test"
    now = datetime.now(UTC)
    monkeypatch.setattr(
        verify_v0_3_phase_three,
        "_repository_identity",
        lambda: (COMMIT_SHA, "feature/v0.3-market-intelligence"),
    )
    monkeypatch.setattr(
        verify_v0_3_phase_three,
        "_load_prior_freeze",
        lambda path: prior_freeze(),
    )
    monkeypatch.setattr(
        verify_v0_3_phase_three,
        "_load_golden_evidence",
        lambda path, commit_sha: PhaseThreeGoldenEvidence.model_validate(
            {**golden_evidence().model_dump(), "report_generated_at": now}
        ),
    )
    monkeypatch.setattr(
        verify_v0_3_phase_three,
        "_load_background_job_evidence",
        lambda path, commit_sha: PhaseThreeBackgroundJobEvidence.model_validate(
            {**background_evidence().model_dump(), "report_generated_at": now}
        ),
    )
    monkeypatch.setattr(
        verify_v0_3_phase_three,
        "_run_gate",
        lambda *, gate_id, commands, environment: PhaseThreeGateEvidence(
            gate_id=gate_id,
            commands=(command(),),
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_v0_3_phase_three.py",
            "--database-url",
            database_url,
            "--confirm-destructive-migration-cycle",
            "trd_bot_test",
            "--golden-benchmark-report",
            str(tmp_path / "golden.json"),
            "--background-jobs-capacity-report",
            str(tmp_path / "background.json"),
            "--github-actions-run-url",
            "https://github.com/example/trd-bot/actions/runs/12345",
            "--github-actions-head-sha",
            COMMIT_SHA,
            "--github-actions-conclusion",
            "success",
            "--local-stack-smoke",
            "pass",
            "--context-generation-ui-smoke",
            "pass",
            "--stale-context-smoke",
            "pass",
            "--worker-restart-smoke",
            "pass",
            "--monitoring-recovery-smoke",
            "pass",
            "--security-network-smoke",
            "pass",
            "--environment-label",
            ENVIRONMENT,
            "--output",
            str(output),
        ],
    )

    assert verify_v0_3_phase_three.main() == 0
    serialized = output.read_text(encoding="utf-8")
    parsed = parse_phase_three_acceptance_record(serialized)
    assert parsed.ready_to_freeze_phase_three is True
    assert "secret" not in serialized


def test_python_executable_is_sanitized_in_command_evidence() -> None:
    sanitized = verify_v0_3_phase_three._sanitized_command((sys.executable, "-m", "pytest"))

    assert sanitized == ("python", "-m", "pytest")
