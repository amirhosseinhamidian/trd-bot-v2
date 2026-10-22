import itertools
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from scripts.verify_v0_3_phase_five import _specs

from trd_bot.decision_intelligence import (
    DecisionPipelineBenchmarkReport,
    run_decision_pipeline_benchmark,
)
from trd_bot.phase_five_acceptance import (
    PHASE_FIVE_GATE_IDS,
    PhaseFiveAcceptanceRecord,
    PhaseFiveCiEvidence,
    PhaseFiveCommandEvidence,
    PhaseFiveGateEvidence,
    PhaseFiveManualEvidence,
    PhaseFivePriorFreezeEvidence,
    evaluate_phase_five_benchmark,
    parse_phase_five_acceptance_record,
    serialize_phase_five_acceptance_record,
)

SHA = "a" * 40
NOW = datetime(2026, 10, 21, 7, tzinfo=UTC)


def _benchmark(*, runtime_p95_ms: Decimal = Decimal("1")) -> DecisionPipelineBenchmarkReport:
    report = run_decision_pipeline_benchmark(
        samples=100,
        commit_sha=SHA,
        environment_label="macbook-pro-reference",
    )
    return report.model_copy(update={"generated_at": NOW, "runtime_p95_ms": runtime_p95_ms})


def _gates(failed: str | None = None) -> tuple[PhaseFiveGateEvidence, ...]:
    return tuple(
        PhaseFiveGateEvidence(
            gate_id=gate_id,
            commands=(
                PhaseFiveCommandEvidence(
                    label="gate",
                    command=("python", "-m", "pytest"),
                    exit_code=1 if gate_id == failed else 0,
                    duration_ms=1,
                ),
            ),
        )
        for gate_id in PHASE_FIVE_GATE_IDS
    )


def _record(
    *, failed_gate: str | None = None, benchmark_failed: bool = False
) -> PhaseFiveAcceptanceRecord:
    report = _benchmark(runtime_p95_ms=Decimal("26") if benchmark_failed else Decimal("1"))
    return PhaseFiveAcceptanceRecord(
        commit_sha=SHA,
        branch="feature/v0.3-market-intelligence",
        environment_label="macbook-pro-reference",
        generated_at=NOW + timedelta(minutes=1),
        prior_freeze=PhaseFivePriorFreezeEvidence(
            phase_four_record_checksum="b" * 64,
            phase_four_commit_sha="c" * 40,
            phase_four_ready=True,
        ),
        benchmark=evaluate_phase_five_benchmark(report, report_checksum="d" * 64),
        ci=PhaseFiveCiEvidence(
            run_url="https://github.com/example/trd-bot/actions/runs/123",
            head_sha=SHA,
            conclusion="success",
        ),
        manual=PhaseFiveManualEvidence(
            strategy_signal_candidate_lineage="pass",
            risk_gate_fail_closed="pass",
            paper_shadow_portfolio_advisory="pass",
            worker_restart_and_idempotency="pass",
            api_ui_progressive_disclosure="pass",
            no_live_trading_security_inventory="pass",
        ),
        gates=_gates(failed_gate),
    )


def test_complete_evidence_freezes_phase_five() -> None:
    record = _record()
    assert record.ready_to_freeze_phase_five is True
    assert record.failed_gates == ()
    assert (
        parse_phase_five_acceptance_record(serialize_phase_five_acceptance_record(record)) == record
    )


@pytest.mark.parametrize("failed_gate,benchmark_failed", (("frontend", False), (None, True)))
def test_failed_gate_or_benchmark_blocks_freeze(
    failed_gate: str | None, benchmark_failed: bool
) -> None:
    assert (
        _record(
            failed_gate=failed_gate,
            benchmark_failed=benchmark_failed,
        ).ready_to_freeze_phase_five
        is False
    )


def test_record_rejects_missing_gate_sha_environment_and_stale_evidence() -> None:
    baseline = _record()
    with pytest.raises(ValueError, match="every Phase 5 gate"):
        PhaseFiveAcceptanceRecord.model_validate(
            {**baseline.model_dump(), "gates": [item.model_dump() for item in _gates()[:-1]]}
        )
    with pytest.raises(ValueError, match="head SHA"):
        PhaseFiveAcceptanceRecord.model_validate(
            {**baseline.model_dump(), "ci": {**baseline.ci.model_dump(), "head_sha": "1" * 40}}
        )
    with pytest.raises(ValueError, match="environment"):
        PhaseFiveAcceptanceRecord.model_validate(
            {
                **baseline.model_dump(),
                "benchmark": {
                    **baseline.benchmark.model_dump(),
                    "report_environment_label": "other",
                },
            }
        )
    with pytest.raises(ValueError, match="current"):
        PhaseFiveAcceptanceRecord.model_validate(
            {**baseline.model_dump(), "generated_at": NOW + timedelta(days=366)}
        )


@pytest.mark.parametrize(
    "field", ("ready_to_freeze_phase_five", "failed_gates", "benchmark", "gate")
)
def test_parser_rejects_tampered_derived_outcomes(field: str) -> None:
    payload = json.loads(serialize_phase_five_acceptance_record(_record()))
    if field == "ready_to_freeze_phase_five":
        payload[field] = False
    elif field == "failed_gates":
        payload[field] = ["backend"]
    elif field == "benchmark":
        payload["benchmark"]["passed"] = False
    else:
        payload["gates"][0]["passed"] = False
    with pytest.raises(ValueError, match="inconsistent"):
        parse_phase_five_acceptance_record(json.dumps(payload))


def test_command_evidence_rejects_database_credentials() -> None:
    with pytest.raises(ValueError, match="database URLs"):
        PhaseFiveCommandEvidence(
            label="unsafe",
            command=("tool", "postgresql+psycopg://user:secret@localhost/db"),
            exit_code=0,
            duration_ms=1,
        )


def test_benchmark_evidence_rejects_forged_failure_reasons() -> None:
    evidence = evaluate_phase_five_benchmark(_benchmark(), report_checksum="d" * 64)
    payload = evidence.model_dump()
    payload["observations"]["runtime_p95_ms"] = Decimal("26")

    with pytest.raises(ValueError, match="failure reasons are inconsistent"):
        type(evidence).model_validate(payload)


def test_postgresql_gate_runs_the_integration_marker() -> None:
    specs_by_gate = dict(_specs())
    commands = specs_by_gate["postgresql_resilience"]

    assert len(commands) == 1
    label, command, _ = commands[0]
    adjacent_arguments = tuple(itertools.pairwise(command))

    assert label == "PostgreSQL integration"
    assert ("-m", "integration") in adjacent_arguments
