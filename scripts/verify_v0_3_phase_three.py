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

from trd_bot.market_context import parse_market_context_golden_benchmark_report
from trd_bot.market_data import parse_capacity_benchmark_report
from trd_bot.phase_three_acceptance import (
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
    serialize_phase_three_acceptance_record,
)
from trd_bot.phase_two_acceptance import parse_phase_two_acceptance_record

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_ROOT = _REPOSITORY_ROOT / "frontend"
_DEFAULT_PHASE_TWO_RECORD = _REPOSITORY_ROOT / "artifacts/p2-08/phase-two-acceptance.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fail-closed P3-10 gates on a clean commit and write sanitized "
            "Phase 3 freeze evidence."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("TRD_BOT_TEST_DATABASE_URL"),
        help="Disposable PostgreSQL URL; defaults to TRD_BOT_TEST_DATABASE_URL.",
    )
    parser.add_argument(
        "--confirm-destructive-migration-cycle",
        choices=("trd_bot_test",),
        required=True,
        help="Confirms that downgrade-to-base may erase the disposable trd_bot_test database.",
    )
    parser.add_argument(
        "--phase-two-record",
        type=Path,
        default=_DEFAULT_PHASE_TWO_RECORD,
    )
    parser.add_argument("--golden-benchmark-report", type=Path, required=True)
    parser.add_argument("--background-jobs-capacity-report", type=Path, required=True)
    parser.add_argument("--github-actions-run-url", required=True)
    parser.add_argument("--github-actions-head-sha", required=True)
    parser.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    parser.add_argument("--local-stack-smoke", choices=("pass",), required=True)
    parser.add_argument("--context-generation-ui-smoke", choices=("pass",), required=True)
    parser.add_argument("--stale-context-smoke", choices=("pass",), required=True)
    parser.add_argument("--worker-restart-smoke", choices=("pass",), required=True)
    parser.add_argument("--monitoring-recovery-smoke", choices=("pass",), required=True)
    parser.add_argument("--security-network-smoke", choices=("pass",), required=True)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        check=check,
        capture_output=True,
        cwd=_REPOSITORY_ROOT,
        text=True,
    )


def _repository_identity() -> tuple[str, str]:
    commit_sha = _git("rev-parse", "HEAD").stdout.strip().lower()
    branch = _git("branch", "--show-current").stdout.strip()
    if not branch:
        raise ValueError("Phase 3 acceptance cannot run from a detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("Phase 3 acceptance requires a clean worktree")
    return commit_sha, branch


def _validate_database_url(database_url: str | None) -> str:
    if not database_url:
        raise ValueError("--database-url or TRD_BOT_TEST_DATABASE_URL is required")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Phase 3 acceptance requires PostgreSQL")
    if url.database != "trd_bot_test":
        raise ValueError("destructive migration cycle may run only against trd_bot_test")
    return database_url


def _validate_ci_url(value: str) -> str:
    normalized = value.strip()
    if not re.fullmatch(
        r"https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+",
        normalized,
    ):
        raise ValueError("GitHub Actions URL must identify one actions/runs/<id> page")
    return normalized


def _checksum(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_ancestor(commit_sha: str, *, label: str) -> None:
    result = _git("merge-base", "--is-ancestor", commit_sha, "HEAD", check=False)
    if result.returncode == 1:
        raise ValueError(f"accepted {label} commit is not an ancestor of the candidate")
    if result.returncode != 0:
        raise ValueError(f"unable to verify accepted {label} commit ancestry")


def _load_prior_freeze(path: Path) -> PhaseThreePriorFreezeEvidence:
    record_bytes = path.read_bytes()
    record = parse_phase_two_acceptance_record(record_bytes)
    if not record.ready_to_freeze_phase_two:
        raise ValueError("Phase 2 freeze record is not accepted")
    _require_ancestor(record.commit_sha, label="Phase 2")
    return PhaseThreePriorFreezeEvidence(
        phase_two_record_checksum=_checksum(record_bytes),
        phase_two_commit_sha=record.commit_sha,
        phase_two_ready=True,
    )


def _load_golden_evidence(path: Path, *, commit_sha: str) -> PhaseThreeGoldenEvidence:
    report_bytes = path.read_bytes()
    report = parse_market_context_golden_benchmark_report(report_bytes)
    if report.commit_sha != commit_sha:
        raise ValueError("golden benchmark report SHA does not match the checked-out commit")
    return evaluate_phase_three_golden_evidence(
        report,
        report_checksum=_checksum(report_bytes),
    )


def _load_background_job_evidence(
    path: Path,
    *,
    commit_sha: str,
) -> PhaseThreeBackgroundJobEvidence:
    report_bytes = path.read_bytes()
    report = parse_capacity_benchmark_report(report_bytes)
    if report.commit_sha != commit_sha:
        raise ValueError("background-job report SHA does not match the checked-out commit")
    return evaluate_phase_three_background_job_evidence(
        report,
        report_checksum=_checksum(report_bytes),
    )


def _sanitized_command(command: tuple[str, ...]) -> tuple[str, ...]:
    if command and command[0] == sys.executable:
        return ("python", *command[1:])
    return command


def _run_command(
    *,
    label: str,
    command: tuple[str, ...],
    cwd: Path,
    environment: dict[str, str],
) -> PhaseThreeCommandEvidence:
    started_at = monotonic()
    try:
        completed = subprocess.run(command, check=False, cwd=cwd, env=environment)
        exit_code = completed.returncode
    except OSError as exc:
        print(f"Unable to run {label}: {exc}", file=sys.stderr)
        exit_code = 127
    return PhaseThreeCommandEvidence(
        label=label,
        command=_sanitized_command(command),
        exit_code=exit_code,
        duration_ms=round((monotonic() - started_at) * 1_000),
    )


def _run_gate(
    *,
    gate_id: str,
    commands: tuple[tuple[str, tuple[str, ...], Path], ...],
    environment: dict[str, str],
) -> PhaseThreeGateEvidence:
    evidence: list[PhaseThreeCommandEvidence] = []
    for label, command, cwd in commands:
        outcome = _run_command(
            label=label,
            command=command,
            cwd=cwd,
            environment=environment,
        )
        evidence.append(outcome)
        if not outcome.passed:
            break
    return PhaseThreeGateEvidence(gate_id=gate_id, commands=tuple(evidence))


def _gate_specs() -> tuple[tuple[str, tuple[tuple[str, tuple[str, ...], Path], ...]], ...]:
    python = sys.executable
    return (
        (
            "repository_contract",
            (
                (
                    "Repository and freeze contract tests",
                    (
                        python,
                        "-m",
                        "pytest",
                        "tests/test_release_version.py",
                        "tests/test_release_security_boundary.py",
                        "tests/test_phase_zero_acceptance.py",
                        "tests/test_phase_one_acceptance.py",
                        "tests/test_phase_two_acceptance.py",
                        "tests/test_phase_three_acceptance.py",
                        "tests/test_market_context_benchmark.py",
                        "-q",
                    ),
                    _REPOSITORY_ROOT,
                ),
            ),
        ),
        (
            "market_context_contract",
            (
                (
                    "Phase 3 market-context contract tests",
                    (
                        python,
                        "-m",
                        "pytest",
                        "tests/test_market_context_contracts.py",
                        "tests/test_market_context_persistence.py",
                        "tests/test_market_context_alignment.py",
                        "tests/test_market_context_features.py",
                        "tests/test_market_context_regimes.py",
                        "tests/test_market_context_jobs.py",
                        "tests/test_market_context_monitoring.py",
                        "tests/test_market_context_product.py",
                        "tests/test_market_context_benchmark.py",
                        "-q",
                    ),
                    _REPOSITORY_ROOT,
                ),
            ),
        ),
        (
            "backend",
            (
                (
                    "Backend format",
                    (python, "-m", "ruff", "format", "--check", "."),
                    _REPOSITORY_ROOT,
                ),
                ("Backend lint", (python, "-m", "ruff", "check", "."), _REPOSITORY_ROOT),
                ("Backend typing", (python, "-m", "mypy"), _REPOSITORY_ROOT),
                (
                    "Backend tests",
                    (python, "-m", "pytest", "-m", "not integration"),
                    _REPOSITORY_ROOT,
                ),
            ),
        ),
        (
            "migration_cycle",
            (
                (
                    "Alembic upgrade",
                    (python, "-m", "alembic", "upgrade", "head"),
                    _REPOSITORY_ROOT,
                ),
                (
                    "Alembic downgrade",
                    (python, "-m", "alembic", "downgrade", "base"),
                    _REPOSITORY_ROOT,
                ),
                (
                    "Alembic rebuild",
                    (python, "-m", "alembic", "upgrade", "head"),
                    _REPOSITORY_ROOT,
                ),
                (
                    "Alembic drift check",
                    (python, "-m", "alembic", "check"),
                    _REPOSITORY_ROOT,
                ),
            ),
        ),
        (
            "postgresql_resilience",
            (
                (
                    "PostgreSQL race, recovery, deduplication and context durability",
                    (python, "-m", "pytest", "-m", "integration", "-v"),
                    _REPOSITORY_ROOT,
                ),
            ),
        ),
        (
            "frontend",
            (
                ("Frontend format", ("npm", "run", "format:check"), _FRONTEND_ROOT),
                ("Frontend lint", ("npm", "run", "lint"), _FRONTEND_ROOT),
                ("Frontend typing", ("npm", "run", "typecheck"), _FRONTEND_ROOT),
                ("Frontend tests", ("npm", "run", "test"), _FRONTEND_ROOT),
                ("Frontend build", ("npm", "run", "build"), _FRONTEND_ROOT),
            ),
        ),
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")

    try:
        database_url = _validate_database_url(args.database_url)
        run_url = _validate_ci_url(args.github_actions_run_url)
        commit_sha, branch = _repository_identity()
        ci_head_sha = args.github_actions_head_sha.strip().lower()
        if ci_head_sha != commit_sha:
            raise ValueError("GitHub Actions head SHA does not match the checked-out commit")
        prior_freeze = _load_prior_freeze(args.phase_two_record)
        golden = _load_golden_evidence(args.golden_benchmark_report, commit_sha=commit_sha)
        background_jobs = _load_background_job_evidence(
            args.background_jobs_capacity_report,
            commit_sha=commit_sha,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))

    environment = dict(os.environ)
    environment.update(
        {
            "TRD_BOT_DATABASE_URL": database_url,
            "TRD_BOT_TEST_DATABASE_URL": database_url,
            "TRD_BOT_ENVIRONMENT": "test",
            "TRD_BOT_DEBUG": "false",
        }
    )
    gates = tuple(
        _run_gate(gate_id=gate_id, commands=commands, environment=environment)
        for gate_id, commands in _gate_specs()
    )
    record = PhaseThreeAcceptanceRecord(
        commit_sha=commit_sha,
        branch=branch,
        environment_label=args.environment_label,
        generated_at=datetime.now(UTC),
        prior_freeze=prior_freeze,
        golden=golden,
        background_jobs=background_jobs,
        ci=PhaseThreeCiEvidence(
            run_url=run_url,
            head_sha=ci_head_sha,
            conclusion=args.github_actions_conclusion,
        ),
        manual=PhaseThreeManualEvidence(
            local_api_worker_frontend=args.local_stack_smoke,
            context_generation_and_ui=args.context_generation_ui_smoke,
            stale_context_fail_closed=args.stale_context_smoke,
            worker_restart_deduplication=args.worker_restart_smoke,
            monitoring_freshness_recovery=args.monitoring_recovery_smoke,
            security_network_inventory=args.security_network_smoke,
        ),
        gates=gates,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_phase_three_acceptance_record(record) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote Phase 3 acceptance record to {args.output}")
    return 0 if record.ready_to_freeze_phase_three else 2


if __name__ == "__main__":
    raise SystemExit(main())
