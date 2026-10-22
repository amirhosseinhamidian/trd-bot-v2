#!/usr/bin/env python3
import argparse
import hashlib
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from sqlalchemy.engine import make_url

from trd_bot.decision_intelligence import parse_decision_pipeline_benchmark_report
from trd_bot.phase_five_acceptance import (
    PhaseFiveAcceptanceRecord,
    PhaseFiveCiEvidence,
    PhaseFiveCommandEvidence,
    PhaseFiveGateEvidence,
    PhaseFiveManualEvidence,
    PhaseFivePriorFreezeEvidence,
    evaluate_phase_five_benchmark,
    serialize_phase_five_acceptance_record,
)
from trd_bot.phase_four_acceptance import parse_phase_four_acceptance_record

_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND = _ROOT / "frontend"
_DEFAULT_PRIOR = _ROOT / "artifacts/p4-08/phase-four-acceptance.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the fail-closed P5-09 freeze gates.")
    parser.add_argument("--database-url", default=os.environ.get("TRD_BOT_TEST_DATABASE_URL"))
    parser.add_argument(
        "--confirm-destructive-migration-cycle", choices=("trd_bot_test",), required=True
    )
    parser.add_argument("--phase-four-record", type=Path, default=_DEFAULT_PRIOR)
    parser.add_argument("--decision-benchmark-report", type=Path, required=True)
    parser.add_argument("--github-actions-run-url", required=True)
    parser.add_argument("--github-actions-head-sha", required=True)
    parser.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    parser.add_argument(
        "--strategy-signal-candidate-lineage-smoke", choices=("pass",), required=True
    )
    parser.add_argument("--risk-gate-fail-closed-smoke", choices=("pass",), required=True)
    parser.add_argument("--paper-shadow-portfolio-advisory-smoke", choices=("pass",), required=True)
    parser.add_argument("--worker-restart-idempotency-smoke", choices=("pass",), required=True)
    parser.add_argument("--api-ui-progressive-disclosure-smoke", choices=("pass",), required=True)
    parser.add_argument("--security-network-smoke", choices=("pass",), required=True)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args=("git", *args), cwd=_ROOT, check=check, capture_output=True, text=True
    )


def _identity() -> tuple[str, str]:
    sha = _git("rev-parse", "HEAD").stdout.strip().lower()
    branch = _git("branch", "--show-current").stdout.strip()
    if not branch:
        raise ValueError("Phase 5 acceptance cannot run from detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("Phase 5 acceptance requires a clean worktree")
    return sha, branch


def _database_url(value: str | None) -> str:
    if not value:
        raise ValueError("--database-url or TRD_BOT_TEST_DATABASE_URL is required")
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or url.database != "trd_bot_test":
        raise ValueError("Phase 5 destructive gates require PostgreSQL database trd_bot_test")
    return value


def _prior(path: Path) -> PhaseFivePriorFreezeEvidence:
    data = path.read_bytes()
    record = parse_phase_four_acceptance_record(data)
    if not record.ready_to_freeze_phase_four:
        raise ValueError("Phase 4 freeze record is not accepted")
    outcome = _git("merge-base", "--is-ancestor", record.commit_sha, "HEAD", check=False)
    if outcome.returncode != 0:
        raise ValueError("accepted Phase 4 commit is not an ancestor of the candidate")
    return PhaseFivePriorFreezeEvidence(
        phase_four_record_checksum=hashlib.sha256(data).hexdigest(),
        phase_four_commit_sha=record.commit_sha,
        phase_four_ready=True,
    )


def _command(
    label: str, command: tuple[str, ...], cwd: Path, env: dict[str, str]
) -> PhaseFiveCommandEvidence:
    started = monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, env=env, check=False)
        code = result.returncode
    except OSError:
        code = 127
    safe = ("python", *command[1:]) if command and command[0] == sys.executable else command
    return PhaseFiveCommandEvidence(
        label=label,
        command=safe,
        exit_code=code,
        duration_ms=round((monotonic() - started) * 1000),
    )


def _gate(
    gate_id: str, specs: tuple[tuple[str, tuple[str, ...], Path], ...], env: dict[str, str]
) -> PhaseFiveGateEvidence:
    evidence: list[PhaseFiveCommandEvidence] = []
    for label, command, cwd in specs:
        item = _command(label, command, cwd, env)
        evidence.append(item)
        if not item.passed:
            break
    return PhaseFiveGateEvidence(gate_id=gate_id, commands=tuple(evidence))


def _specs() -> tuple[tuple[str, tuple[tuple[str, tuple[str, ...], Path], ...]], ...]:
    py = sys.executable
    decision_tests = tuple(
        str(path.relative_to(_ROOT))
        for path in sorted((_ROOT / "tests").glob("test_decision_*.py"))
    )
    return (
        (
            "repository_contract",
            (
                (
                    "Freeze contract tests",
                    (
                        py,
                        "-m",
                        "pytest",
                        "tests/test_release_security_boundary.py",
                        "tests/test_phase_four_acceptance.py",
                        "tests/test_phase_five_acceptance.py",
                        "-q",
                    ),
                    _ROOT,
                ),
            ),
        ),
        (
            "decision_contract",
            (
                (
                    "Phase 5 decision tests",
                    (
                        py,
                        "-m",
                        "pytest",
                        "tests/test_context_aware_strategy_evaluation.py",
                        *decision_tests,
                        "-m",
                        "not integration",
                        "-q",
                    ),
                    _ROOT,
                ),
            ),
        ),
        (
            "backend",
            (
                ("Backend format", (py, "-m", "ruff", "format", "--check", "."), _ROOT),
                ("Backend lint", (py, "-m", "ruff", "check", "."), _ROOT),
                ("Backend typing", (py, "-m", "mypy"), _ROOT),
                ("Backend tests", (py, "-m", "pytest", "-m", "not integration"), _ROOT),
            ),
        ),
        (
            "migration_cycle",
            (
                ("Alembic upgrade", (py, "-m", "alembic", "upgrade", "head"), _ROOT),
                ("Alembic downgrade", (py, "-m", "alembic", "downgrade", "base"), _ROOT),
                ("Alembic rebuild", (py, "-m", "alembic", "upgrade", "head"), _ROOT),
                ("Alembic drift", (py, "-m", "alembic", "check"), _ROOT),
            ),
        ),
        (
            "postgresql_resilience",
            (
                (
                    "PostgreSQL integration",
                    (py, "-m", "pytest", "-m", "integration", "-q"),
                    _ROOT,
                ),
            ),
        ),
        (
            "frontend",
            (
                ("Frontend format", ("pnpm", "format:check"), _FRONTEND),
                ("Frontend lint", ("pnpm", "lint"), _FRONTEND),
                ("Frontend typecheck", ("pnpm", "typecheck"), _FRONTEND),
                ("Frontend tests", ("pnpm", "test", "--", "--run"), _FRONTEND),
                ("Frontend build", ("pnpm", "build"), _FRONTEND),
            ),
        ),
    )


def main() -> int:
    args = build_parser().parse_args()
    if args.output.exists():
        raise FileExistsError("Phase 5 acceptance output already exists")
    database_url = _database_url(args.database_url)
    commit_sha, branch = _identity()
    if not re.fullmatch(
        r"https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+", args.github_actions_run_url
    ):
        raise ValueError("GitHub Actions URL must identify actions/runs/<id>")
    report_bytes = args.decision_benchmark_report.read_bytes()
    report = parse_decision_pipeline_benchmark_report(report_bytes)
    if report.commit_sha != commit_sha:
        raise ValueError("decision benchmark SHA does not match checked-out commit")
    env = os.environ.copy()
    env["TRD_BOT_DATABASE_URL"] = database_url
    env["TRD_BOT_TEST_DATABASE_URL"] = database_url
    env["PYTHONPATH"] = str(_ROOT / "src")
    gates = tuple(_gate(gate_id, specs, env) for gate_id, specs in _specs())
    record = PhaseFiveAcceptanceRecord(
        commit_sha=commit_sha,
        branch=branch,
        environment_label=args.environment_label,
        generated_at=datetime.now(UTC),
        prior_freeze=_prior(args.phase_four_record),
        benchmark=evaluate_phase_five_benchmark(
            report,
            report_checksum=hashlib.sha256(report_bytes).hexdigest(),
        ),
        ci=PhaseFiveCiEvidence(
            run_url=args.github_actions_run_url,
            head_sha=args.github_actions_head_sha,
            conclusion=args.github_actions_conclusion,
        ),
        manual=PhaseFiveManualEvidence(
            strategy_signal_candidate_lineage=args.strategy_signal_candidate_lineage_smoke,
            risk_gate_fail_closed=args.risk_gate_fail_closed_smoke,
            paper_shadow_portfolio_advisory=args.paper_shadow_portfolio_advisory_smoke,
            worker_restart_and_idempotency=args.worker_restart_idempotency_smoke,
            api_ui_progressive_disclosure=args.api_ui_progressive_disclosure_smoke,
            no_live_trading_security_inventory=args.security_network_smoke,
        ),
        gates=gates,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialize_phase_five_acceptance_record(record) + "\n")
    print(f"Wrote Phase 5 acceptance record to {args.output}")
    return 0 if record.ready_to_freeze_phase_five else 2


if __name__ == "__main__":
    raise SystemExit(main())
