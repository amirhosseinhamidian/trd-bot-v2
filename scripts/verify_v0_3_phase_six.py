#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic

from sqlalchemy.engine import make_url

from trd_bot.outcome_learning import parse_outcome_learning_review
from trd_bot.phase_five_acceptance import parse_phase_five_acceptance_record
from trd_bot.phase_six_acceptance import (
    PHASE_SIX_MAX_EVIDENCE_AGE,
    PhaseSixAcceptanceRecord,
    PhaseSixCiEvidence,
    PhaseSixCommandEvidence,
    PhaseSixGateEvidence,
    PhaseSixManualEvidence,
    PhaseSixPriorFreezeEvidence,
    capacity_evidence,
    installation_evidence,
    inventory_evidence,
    maintenance_evidence,
    outcome_learning_evidence,
    serialize_phase_six_acceptance_record,
    sha256_bytes,
)
from trd_bot.release_capacity import parse_release_capacity_report
from trd_bot.release_hardening import build_release_hardening_report
from trd_bot.release_installation import parse_release_installation_report
from trd_bot.release_maintenance import parse_release_maintenance_plan

_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND = _ROOT / "frontend"
_DEFAULT_PRIOR = _ROOT / "artifacts/p5-09/phase-five-acceptance.json"
_DEFAULT_OUTPUT = _ROOT / "artifacts/p6-07/v0.3-final-acceptance.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the fail-closed final v0.3 acceptance gates.")
    parser.add_argument("--database-url", default=os.environ.get("TRD_BOT_TEST_DATABASE_URL"))
    parser.add_argument(
        "--confirm-destructive-migration-cycle",
        choices=("trd_bot_test",),
        required=True,
    )
    parser.add_argument("--phase-five-record", type=Path, default=_DEFAULT_PRIOR)
    parser.add_argument("--capacity-report", type=Path, required=True)
    parser.add_argument("--outcome-learning-review", type=Path, required=True)
    parser.add_argument("--maintenance-plan", type=Path, required=True)
    parser.add_argument("--installation-report", type=Path, required=True)
    parser.add_argument("--github-actions-run-url", required=True)
    parser.add_argument("--github-actions-head-sha", required=True)
    parser.add_argument("--github-actions-conclusion", choices=("success",), required=True)
    parser.add_argument("--fresh-install-upgrade-restore-smoke", choices=("pass",), required=True)
    parser.add_argument("--api-worker-ui-lifecycle-smoke", choices=("pass",), required=True)
    parser.add_argument("--outcome-learning-review-smoke", choices=("pass",), required=True)
    parser.add_argument("--retention-maintenance-smoke", choices=("pass",), required=True)
    parser.add_argument("--paper-shadow-lineage-smoke", choices=("pass",), required=True)
    parser.add_argument("--security-network-smoke", choices=("pass",), required=True)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    return parser


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args=("git", *args),
        cwd=_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _identity() -> tuple[str, str]:
    sha = _git("rev-parse", "HEAD").stdout.strip().casefold()
    branch = _git("branch", "--show-current").stdout.strip()
    if not branch:
        raise ValueError("final v0.3 acceptance cannot run from detached HEAD")
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("final v0.3 acceptance requires a clean worktree")
    return sha, branch


def _database_url(value: str | None) -> str:
    if not value:
        raise ValueError("--database-url or TRD_BOT_TEST_DATABASE_URL is required")
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or url.database != "trd_bot_test":
        raise ValueError("final destructive gates require PostgreSQL database trd_bot_test")
    return value


def _prior(path: Path) -> PhaseSixPriorFreezeEvidence:
    data = path.read_bytes()
    record = parse_phase_five_acceptance_record(data)
    if not record.ready_to_freeze_phase_five:
        raise ValueError("Phase 5 freeze record is not accepted")
    outcome = _git("merge-base", "--is-ancestor", record.commit_sha, "HEAD", check=False)
    if outcome.returncode != 0:
        raise ValueError("accepted Phase 5 commit is not an ancestor of the v0.3 candidate")
    return PhaseSixPriorFreezeEvidence(
        phase_five_record_checksum=sha256_bytes(data),
        phase_five_commit_sha=record.commit_sha,
        phase_five_ready=True,
    )


def _command(
    label: str,
    command: tuple[str, ...],
    cwd: Path,
    env: dict[str, str],
) -> PhaseSixCommandEvidence:
    started = monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, env=env, check=False)
        code = result.returncode
    except OSError:
        code = 127
    safe = ("python", *command[1:]) if command and command[0] == sys.executable else command
    return PhaseSixCommandEvidence(
        label=label,
        command=safe,
        exit_code=code,
        duration_ms=round((monotonic() - started) * 1000),
    )


def _gate(
    gate_id: str,
    specs: tuple[tuple[str, tuple[str, ...], Path], ...],
    env: dict[str, str],
) -> PhaseSixGateEvidence:
    evidence: list[PhaseSixCommandEvidence] = []
    for label, command, cwd in specs:
        item = _command(label, command, cwd, env)
        evidence.append(item)
        if not item.passed:
            break
    return PhaseSixGateEvidence(gate_id=gate_id, commands=tuple(evidence))


def _specs() -> tuple[tuple[str, tuple[tuple[str, tuple[str, ...], Path], ...]], ...]:
    py = sys.executable
    return (
        (
            "release_contract",
            (
                (
                    "Final release contract tests",
                    (
                        py,
                        "-m",
                        "pytest",
                        "tests/test_release_security_boundary.py",
                        "tests/test_release_version.py",
                        "tests/test_v0_3_release_cut.py",
                        "tests/test_v0_3_documentation.py",
                        "tests/test_phase_five_acceptance.py",
                        "tests/test_phase_six_acceptance.py",
                        "-q",
                    ),
                    _ROOT,
                ),
            ),
        ),
        (
            "phase_six_contract",
            (
                (
                    "Phase 6 hardening and operations tests",
                    (
                        py,
                        "-m",
                        "pytest",
                        "tests/test_release_hardening.py",
                        "tests/test_release_capacity.py",
                        "tests/test_release_capacity_postgresql.py",
                        "tests/test_outcome_learning_review.py",
                        "tests/test_release_maintenance.py",
                        "tests/test_release_installation.py",
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
                ("Frontend install", ("npm", "ci"), _FRONTEND),
                ("Frontend format", ("npm", "run", "format:check"), _FRONTEND),
                ("Frontend lint", ("npm", "run", "lint"), _FRONTEND),
                ("Frontend typecheck", ("npm", "run", "typecheck"), _FRONTEND),
                ("Frontend tests", ("npm", "run", "test"), _FRONTEND),
                ("Frontend build", ("npm", "run", "build"), _FRONTEND),
            ),
        ),
    )


def _artifact(path: Path) -> tuple[bytes, str]:
    value = path.read_bytes()
    return value, sha256_bytes(value)


def main() -> int:
    args = build_parser().parse_args()
    if args.output.exists():
        raise FileExistsError("final v0.3 acceptance output already exists")
    database_url = _database_url(args.database_url)
    candidate_sha, branch = _identity()
    if not re.fullmatch(
        r"https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+",
        args.github_actions_run_url,
    ):
        raise ValueError("GitHub Actions URL must identify actions/runs/<id>")

    capacity_bytes, capacity_checksum = _artifact(args.capacity_report)
    outcome_bytes, outcome_checksum = _artifact(args.outcome_learning_review)
    maintenance_bytes, maintenance_checksum = _artifact(args.maintenance_plan)
    installation_bytes, installation_checksum = _artifact(args.installation_report)
    inventory = build_release_hardening_report(_ROOT)
    prior = _prior(args.phase_five_record)
    capacity = capacity_evidence(
        parse_release_capacity_report(capacity_bytes),
        artifact_checksum=capacity_checksum,
    )
    outcome_learning = outcome_learning_evidence(
        parse_outcome_learning_review(outcome_bytes),
        artifact_checksum=outcome_checksum,
    )
    maintenance = maintenance_evidence(
        parse_release_maintenance_plan(maintenance_bytes),
        artifact_checksum=maintenance_checksum,
    )
    installation = installation_evidence(
        parse_release_installation_report(installation_bytes),
        artifact_checksum=installation_checksum,
    )
    inventory_item = inventory_evidence(inventory)
    artifact_items = (capacity, outcome_learning, maintenance, installation)
    if any(item.commit_sha != candidate_sha for item in artifact_items):
        raise ValueError("every Phase 6 artifact SHA must match the checked-out candidate")
    if any(item.environment_label != args.environment_label for item in artifact_items):
        raise ValueError("every Phase 6 artifact environment must match --environment-label")
    if installation.release_inventory_checksum != inventory_item.definition_checksum:
        raise ValueError("installation report does not match the current release inventory")
    preflight_at = datetime.now(UTC)
    for item in artifact_items:
        age = preflight_at - item.generated_at
        if age < timedelta() or age > PHASE_SIX_MAX_EVIDENCE_AGE:
            raise ValueError("Phase 6 artifact evidence must be current before running gates")
    ci_head_sha = args.github_actions_head_sha.strip().casefold()
    if ci_head_sha != candidate_sha:
        raise ValueError("GitHub Actions head SHA must match the checked-out candidate")

    env = os.environ.copy()
    env["TRD_BOT_DATABASE_URL"] = database_url
    env["TRD_BOT_TEST_DATABASE_URL"] = database_url
    env["PYTHONPATH"] = str(_ROOT / "src")
    gates = tuple(_gate(gate_id, specs, env) for gate_id, specs in _specs())
    if _git("status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        raise ValueError("final v0.3 gates changed the candidate worktree")

    record = PhaseSixAcceptanceRecord(
        candidate_commit_sha=candidate_sha,
        branch=branch,
        environment_label=args.environment_label,
        generated_at=datetime.now(UTC),
        prior_freeze=prior,
        capacity=capacity,
        outcome_learning=outcome_learning,
        maintenance=maintenance,
        installation=installation,
        inventory=inventory_item,
        ci=PhaseSixCiEvidence(
            run_url=args.github_actions_run_url,
            head_sha=ci_head_sha,
            conclusion=args.github_actions_conclusion,
        ),
        manual=PhaseSixManualEvidence(
            fresh_install_upgrade_and_restore=args.fresh_install_upgrade_restore_smoke,
            api_worker_ui_lifecycle=args.api_worker_ui_lifecycle_smoke,
            outcome_learning_human_review=args.outcome_learning_review_smoke,
            retention_maintenance_closed=args.retention_maintenance_smoke,
            paper_shadow_decision_lineage=args.paper_shadow_lineage_smoke,
            no_live_trading_security_inventory=args.security_network_smoke,
        ),
        gates=gates,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output_file:
        output_file.write(serialize_phase_six_acceptance_record(record) + "\n")
    print(f"Wrote final v0.3 acceptance record to {args.output}")
    return 0 if record.ready_to_freeze_v0_3 else 2


if __name__ == "__main__":
    raise SystemExit(main())
