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

from trd_bot.market_data import parse_capacity_benchmark_report
from trd_bot.phase_one_acceptance import parse_phase_one_acceptance_record
from trd_bot.phase_two_acceptance import (
    PhaseTwoAcceptanceRecord,
    PhaseTwoCiEvidence,
    PhaseTwoCommandEvidence,
    PhaseTwoGateEvidence,
    PhaseTwoManualEvidence,
    PhaseTwoPriorFreezeEvidence,
    PhaseTwoProviderEvidence,
    evaluate_phase_two_provider_evidence,
    serialize_phase_two_acceptance_record,
)
from trd_bot.phase_zero_acceptance import parse_phase_zero_freeze_record

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_ROOT = _REPOSITORY_ROOT / "frontend"
_DEFAULT_PHASE_ZERO_RECORD = _REPOSITORY_ROOT / "artifacts/p0-05/phase-zero-freeze.json"
_DEFAULT_PHASE_ONE_RECORD = _REPOSITORY_ROOT / "artifacts/p1-07/phase-one-acceptance.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fail-closed P2-08 gates on a clean commit and write sanitized "
            "Phase 2 freeze evidence."
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
        "--phase-zero-record",
        type=Path,
        default=_DEFAULT_PHASE_ZERO_RECORD,
    )
    parser.add_argument(
        "--phase-one-record",
        type=Path,
        default=_DEFAULT_PHASE_ONE_RECORD,
    )
    parser.add_argument("--provider-capacity-report", type=Path, required=True)
    parser.add_argument("--github-actions-run-url", required=True)
    parser.add_argument("--github-actions-head-sha", required=True)
    parser.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    parser.add_argument("--local-stack-smoke", choices=("pass",), required=True)
    parser.add_argument("--watchlist-fallback-smoke", choices=("pass",), required=True)
    parser.add_argument("--worker-restart-smoke", choices=("pass",), required=True)
    parser.add_argument("--late-data-replay-smoke", choices=("pass",), required=True)
    parser.add_argument("--retention-hold-smoke", choices=("pass",), required=True)
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
        raise ValueError("Phase 2 acceptance cannot run from a detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("Phase 2 acceptance requires a clean worktree")
    return commit_sha, branch


def _validate_database_url(database_url: str | None) -> str:
    if not database_url:
        raise ValueError("--database-url or TRD_BOT_TEST_DATABASE_URL is required")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Phase 2 acceptance requires PostgreSQL")
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


def _load_prior_freezes(
    phase_zero_path: Path,
    phase_one_path: Path,
) -> PhaseTwoPriorFreezeEvidence:
    phase_zero_bytes = phase_zero_path.read_bytes()
    phase_one_bytes = phase_one_path.read_bytes()
    phase_zero = parse_phase_zero_freeze_record(phase_zero_bytes)
    phase_one = parse_phase_one_acceptance_record(phase_one_bytes)
    if not phase_zero.ready_to_freeze:
        raise ValueError("Phase 0 freeze record is not accepted")
    if not phase_one.ready_to_enter_phase_two:
        raise ValueError("Phase 1 acceptance record is not accepted")
    _require_ancestor(phase_zero.commit_sha, label="Phase 0")
    _require_ancestor(phase_one.commit_sha, label="Phase 1")
    return PhaseTwoPriorFreezeEvidence(
        phase_zero_record_checksum=_checksum(phase_zero_bytes),
        phase_zero_commit_sha=phase_zero.commit_sha,
        phase_zero_ready=True,
        phase_one_record_checksum=_checksum(phase_one_bytes),
        phase_one_commit_sha=phase_one.commit_sha,
        phase_one_ready=True,
    )


def _load_provider_evidence(path: Path, *, commit_sha: str) -> PhaseTwoProviderEvidence:
    report_bytes = path.read_bytes()
    report = parse_capacity_benchmark_report(report_bytes)
    if report.commit_sha != commit_sha:
        raise ValueError("provider capacity report SHA does not match the checked-out commit")
    return evaluate_phase_two_provider_evidence(
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
) -> PhaseTwoCommandEvidence:
    started_at = monotonic()
    try:
        completed = subprocess.run(command, check=False, cwd=cwd, env=environment)
        exit_code = completed.returncode
    except OSError as exc:
        print(f"Unable to run {label}: {exc}", file=sys.stderr)
        exit_code = 127
    return PhaseTwoCommandEvidence(
        label=label,
        command=_sanitized_command(command),
        exit_code=exit_code,
        duration_ms=round((monotonic() - started_at) * 1000),
    )


def _run_gate(
    *,
    gate_id: str,
    commands: tuple[tuple[str, tuple[str, ...], Path], ...],
    environment: dict[str, str],
) -> PhaseTwoGateEvidence:
    evidence: list[PhaseTwoCommandEvidence] = []
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
    return PhaseTwoGateEvidence(gate_id=gate_id, commands=tuple(evidence))


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
                        "-q",
                    ),
                    _REPOSITORY_ROOT,
                ),
            ),
        ),
        (
            "market_data_contract",
            (
                (
                    "Phase 2 market-data contract tests",
                    (
                        python,
                        "-m",
                        "pytest",
                        "tests/test_market_data_service_levels.py",
                        "tests/test_market_data_event_storage.py",
                        "tests/test_market_data_ingestion.py",
                        "tests/test_market_data_polling.py",
                        "tests/test_market_data_finalization.py",
                        "tests/test_market_data_replay.py",
                        "tests/test_market_data_retention.py",
                        "tests/test_market_data_monitoring.py",
                        "tests/test_market_data_security.py",
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
                ("Alembic upgrade", (python, "-m", "alembic", "upgrade", "head"), _REPOSITORY_ROOT),
                (
                    "Alembic downgrade",
                    (python, "-m", "alembic", "downgrade", "base"),
                    _REPOSITORY_ROOT,
                ),
                ("Alembic rebuild", (python, "-m", "alembic", "upgrade", "head"), _REPOSITORY_ROOT),
                ("Alembic drift check", (python, "-m", "alembic", "check"), _REPOSITORY_ROOT),
            ),
        ),
        (
            "postgresql_resilience",
            (
                (
                    "PostgreSQL race, recovery, deduplication and retention",
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
        prior_freezes = _load_prior_freezes(args.phase_zero_record, args.phase_one_record)
        provider = _load_provider_evidence(
            args.provider_capacity_report,
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
    record = PhaseTwoAcceptanceRecord(
        commit_sha=commit_sha,
        branch=branch,
        environment_label=args.environment_label,
        generated_at=datetime.now(UTC),
        prior_freezes=prior_freezes,
        provider=provider,
        ci=PhaseTwoCiEvidence(
            run_url=run_url,
            head_sha=ci_head_sha,
            conclusion=args.github_actions_conclusion,
        ),
        manual=PhaseTwoManualEvidence(
            local_api_worker_frontend=args.local_stack_smoke,
            watchlist_fallback_freshness=args.watchlist_fallback_smoke,
            worker_restart_deduplication=args.worker_restart_smoke,
            late_data_replay_monitoring=args.late_data_replay_smoke,
            retention_hold_and_dry_run=args.retention_hold_smoke,
            security_network_inventory=args.security_network_smoke,
        ),
        gates=gates,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_phase_two_acceptance_record(record) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote Phase 2 acceptance record to {args.output}")
    return 0 if record.ready_to_freeze_phase_two else 2


if __name__ == "__main__":
    raise SystemExit(main())
