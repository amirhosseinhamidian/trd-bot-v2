from pathlib import Path

from trd_bot.phase_five_acceptance import parse_phase_five_acceptance_record

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_v0_3_release_cut_requires_the_committed_phase_five_freeze() -> None:
    record_path = REPOSITORY_ROOT / "artifacts/p5-09/phase-five-acceptance.json"
    record = parse_phase_five_acceptance_record(record_path.read_bytes())

    assert record.ready_to_freeze_phase_five is True
    assert record.failed_gates == ()
    assert record.benchmark.passed is True
    assert record.ci.conclusion == "success"


def test_v0_3_release_notes_preserve_the_operating_boundary() -> None:
    changelog = (REPOSITORY_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release_runbook = (REPOSITORY_ROOT / "docs/v0.3/47-v0.3.0-release-cut.md").read_text(
        encoding="utf-8"
    )

    assert "## 0.3.0 - 2026-10-22" in changelog
    assert "Status: frozen and release-approved" in changelog
    assert "`RESEARCH`, `BACKTEST`, `PAPER`, and `SHADOW`" in changelog
    assert "no exchange credentials or private account APIs exist" in changelog
    assert "tag، GitHub Release، deploy، merge به `main`" in release_runbook
