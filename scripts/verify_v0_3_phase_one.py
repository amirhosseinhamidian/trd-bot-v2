#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from sqlalchemy.engine import make_url

from trd_bot.phase_one_acceptance import (
    PhaseOneAcceptanceRecord,
    PhaseOneCiEvidence,
    PhaseOneCommandEvidence,
    PhaseOneGateEvidence,
    PhaseOneManualEvidence,
    serialize_phase_one_acceptance_record,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_ROOT = _REPOSITORY_ROOT / "frontend"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fail-closed P1-07 release gates on a clean commit and write sanitized "
            "Phase 1 acceptance evidence."
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
    parser.add_argument("--github-actions-run-url", required=True)
    parser.add_argument("--github-actions-head-sha", required=True)
    parser.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    parser.add_argument("--local-stack-smoke", choices=("pass",), required=True)
    parser.add_argument("--durable-restart-smoke", choices=("pass",), required=True)
    parser.add_argument("--monitoring-recovery-smoke", choices=("pass",), required=True)
    parser.add_argument("--security-network-smoke", choices=("pass",), required=True)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _git(*args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        check=True,
        capture_output=True,
        cwd=_REPOSITORY_ROOT,
        text=True,
    )
    return result.stdout.strip()


def _repository_identity() -> tuple[str, str]:
    commit_sha = _git("rev-parse", "HEAD").lower()
    branch = _git("branch", "--show-current")
    if not branch:
        raise ValueError("Phase 1 acceptance cannot run from a detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("Phase 1 acceptance requires a clean worktree")
    return commit_sha, branch


def _validate_database_url(database_url: str | None) -> str:
    if not database_url:
        raise ValueError("--database-url or TRD_BOT_TEST_DATABASE_URL is required")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Phase 1 acceptance requires PostgreSQL")
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


def _run_command(
    *,
    label: str,
    command: tuple[str, ...],
    cwd: Path,
    environment: dict[str, str],
) -> PhaseOneCommandEvidence:
    started_at = monotonic()
    try:
        completed = subprocess.run(command, check=False, cwd=cwd, env=environment)
        exit_code = completed.returncode
    except OSError as exc:
        print(f"Unable to run {label}: {exc}", file=sys.stderr)
        exit_code = 127
    return PhaseOneCommandEvidence(
        label=label,
        command=command,
        exit_code=exit_code,
        duration_ms=round((monotonic() - started_at) * 1000),
    )


def _run_gate(
    *,
    gate_id: str,
    commands: tuple[tuple[str, tuple[str, ...], Path], ...],
    environment: dict[str, str],
) -> PhaseOneGateEvidence:
    evidence: list[PhaseOneCommandEvidence] = []
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
    return PhaseOneGateEvidence(gate_id=gate_id, commands=tuple(evidence))


def _gate_specs() -> tuple[tuple[str, tuple[tuple[str, tuple[str, ...], Path], ...]], ...]:
    python = sys.executable
    return (
        (
            "repository_contract",
            (
                (
                    "Focused release contract tests",
                    (
                        python,
                        "-m",
                        "pytest",
                        "tests/test_release_version.py",
                        "tests/test_release_security_boundary.py",
                        "tests/test_mvp_acceptance.py",
                        "tests/test_minimum_export_baseline.py",
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
            "postgresql_recovery",
            (
                (
                    "PostgreSQL integration and recovery",
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
    record = PhaseOneAcceptanceRecord(
        commit_sha=commit_sha,
        branch=branch,
        environment_label=args.environment_label,
        generated_at=datetime.now(UTC),
        ci=PhaseOneCiEvidence(
            run_url=run_url,
            head_sha=ci_head_sha,
            conclusion=args.github_actions_conclusion,
        ),
        manual=PhaseOneManualEvidence(
            local_api_worker_frontend=args.local_stack_smoke,
            durable_workload_restart=args.durable_restart_smoke,
            monitoring_recovery=args.monitoring_recovery_smoke,
            security_network_inventory=args.security_network_smoke,
        ),
        gates=gates,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_phase_one_acceptance_record(record) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote Phase 1 acceptance record to {args.output}")
    return 0 if record.ready_to_enter_phase_two else 2


if __name__ == "__main__":
    raise SystemExit(main())
