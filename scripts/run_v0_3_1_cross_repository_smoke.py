#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2 as httpx
from sqlalchemy import select

from trd_bot.db import (
    DatabaseBase,
    NexoraEventCursorRow,
    NexoraExportArtifactRow,
    SqlAlchemyNexoraEventStore,
    create_database_engine,
    create_session_factory,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"
SCHEMA_VERSION = "trd-bot-v031-cross-repository-smoke-v1"
PROVIDER_VERSION = "0.3.1"
EVENT_TIME = datetime(2026, 11, 11, 10, tzinfo=UTC)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the v0.3.1 real local Nexora provider smoke.")
    parser.add_argument("--nexora-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trd-commit-sha", default=os.environ.get("GITHUB_SHA", "local"))
    parser.add_argument("--trd-tree-sha", default="local")
    parser.add_argument("--nexora-commit-sha", required=True)
    parser.add_argument("--nexora-tree-sha", required=True)
    parser.add_argument("--workflow-run-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--workflow-run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT"))
    return parser.parse_args()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_until_ready(origin: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"provider exited before readiness with code {process.returncode}")
        try:
            response = httpx.get(f"{origin}/api/v1/health", timeout=0.5, trust_env=False)
        except httpx.HTTPError:
            time.sleep(0.1)
            continue
        if response.status_code == 200:
            return
        time.sleep(0.1)
    raise RuntimeError("provider did not become ready")


def request_headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json", "X-Correlation-ID": str(uuid4())}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def seed_provider(database_url: str) -> Any:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.test_nexora_decision_snapshots import seed_resources

    engine = create_database_engine(database_url)
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    seed_resources(factory)
    with factory.begin() as session:
        store = SqlAlchemyNexoraEventStore(session)
        for version in (1, 2):
            store.append(
                event_type="decision.evaluation.completed.v1",
                aggregate_type="decision_evaluation",
                aggregate_id="decision-evaluation-snapshot-1",
                aggregate_version=version,
                idempotency_key=f"stage10-decision-evaluation-event-{version:04d}",
                payload_schema_version="decision-evaluation-intent-v1",
                occurred_at=EVENT_TIME + timedelta(minutes=version),
                published_at=EVENT_TIME + timedelta(minutes=version, seconds=1),
                payload={
                    "decision_id": "decision-evaluation-snapshot-1",
                    "offline_only": True,
                    "external_order_submission_allowed": False,
                },
            )
    return engine, factory


def scan_resource(client: Any, resource_type: Any) -> tuple[tuple[str, str], ...]:
    cursor: str | None = None
    collected: list[tuple[str, str]] = []
    while True:
        page = client.list_snapshots(resource_type, cursor=cursor, limit=1)
        collected.extend(
            (item["source_reference"]["resource_id"], item["source_reference"]["checksum"])
            for item in page.items
        )
        if not page.has_more:
            break
        if page.next_cursor is None:
            raise AssertionError("continuing snapshot page has no cursor")
        cursor = page.next_cursor
    return tuple(collected)


def scenario_record(name: str, *, mode: str = "real_local_provider") -> dict[str, str]:
    return {"scenario": name, "mode": mode, "status": "passed"}


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    nexora_root = args.nexora_root.resolve()
    consumer_src = nexora_root / "apps/server/src"
    consumer_profile = nexora_root / "contracts/integration/v1/trd-bot-v0.3.1-provider-profile.json"
    if not consumer_src.is_dir() or not consumer_profile.is_file():
        raise RuntimeError("pinned Nexora consumer checkout is incomplete")
    if PROFILE_PATH.read_bytes() != consumer_profile.read_bytes():
        raise RuntimeError("TRD Bot and Nexora provider profiles are not byte-identical")
    # Nexora's pinned adapter imports the httpx API name. TRD Bot intentionally uses
    # the maintained httpx2 distribution, whose public client surface is compatible.
    sys.modules.setdefault("httpx", httpx)
    sys.path.insert(0, str(consumer_src))
    from nexora.adapters.trd_bot.client import TrdBotClient
    from nexora.adapters.trd_bot.config import TrdBotSettings
    from nexora.adapters.trd_bot.errors import CursorExpiredError
    from nexora.adapters.trd_bot.models import (
        CommandType,
        DecisionReviewCommand,
        ExportRequest,
        ResourceType,
    )
    from pydantic import SecretStr

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    required_scenarios = profile["acceptance_smoke"]["required_scenarios"]
    results: list[dict[str, str]] = []
    token = "stage10-local-token-" + "a" * 48

    with tempfile.TemporaryDirectory(prefix="trd-v031-stage10-") as temp_name:
        temp = Path(temp_name)
        token_file = temp / "service-token"
        token_file.write_text(token, encoding="ascii")
        token_file.chmod(0o600)
        base_url_file = temp / "base-url"
        database_url = f"sqlite+pysqlite:///{temp / 'provider.db'}"
        engine, factory = seed_provider(database_url)
        port = free_port()
        origin = f"http://127.0.0.1:{port}"
        base_url_file.write_text(origin + "\n", encoding="ascii")
        base_url_file.chmod(0o600)
        log_path = temp / "provider.log"
        environment = {
            **os.environ,
            "TRD_BOT_APP_VERSION": PROVIDER_VERSION,
            "TRD_BOT_DATABASE_URL": database_url,
            "TRD_BOT_ENVIRONMENT": "development",
            "TRD_BOT_NEXORA_SERVICE_TOKEN_FILE": str(token_file),
        }
        with log_path.open("w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "trd_bot.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "warning",
                ],
                cwd=ROOT,
                env=environment,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                wait_until_ready(origin, process)
                endpoint = f"{origin}/api/v1/integration/nexora/capabilities"
                missing = httpx.get(endpoint, headers=request_headers(), trust_env=False)
                assert missing.status_code == 401
                results.append(scenario_record("missing_service_token_returns_401"))
                invalid = httpx.get(
                    endpoint,
                    headers=request_headers("invalid-stage10-token-" + "b" * 48),
                    trust_env=False,
                )
                assert invalid.status_code == 401, (invalid.status_code, invalid.text)
                results.append(scenario_record("invalid_service_token_returns_401"))

                settings = TrdBotSettings(
                    base_url=origin,
                    token=SecretStr(token),
                    base_url_file=base_url_file,
                    token_file=token_file,
                )
                with TrdBotClient(
                    settings, sleep=lambda _: None, jitter=lambda _a, _b: 0.0
                ) as client:
                    capabilities = client.negotiate()
                    assert capabilities.provider_version == PROVIDER_VERSION
                    assert set(capabilities.contract_versions) == {profile["contract_version"]}
                    results.append(scenario_record("capabilities_match_exactly"))

                    scans = {
                        resource.value: scan_resource(client, resource) for resource in ResourceType
                    }
                    repeated = {
                        resource.value: scan_resource(client, resource) for resource in ResourceType
                    }
                    assert scans == repeated
                    assert set(scans) == {
                        item for group in profile["snapshot_groups"].values() for item in group
                    }
                    results.append(
                        scenario_record("portfolio_decision_and_alert_snapshots_page_stably")
                    )

                    first_page = client.list_events(limit=1)
                    assert first_page.has_more and first_page.next_cursor
                    continuation = client.list_events(cursor=first_page.next_cursor, limit=1)
                    replay = client.list_events(cursor=first_page.next_cursor, limit=1)
                    assert continuation.events == replay.events
                    assert (
                        len(
                            {event.event_id for event in (*first_page.events, *continuation.events)}
                        )
                        == 2
                    )
                    results.append(
                        scenario_record("event_cursor_replay_is_at_least_once_and_deduplicable")
                    )
                    event = client.get_event(continuation.events[0].event_id)
                    assert event == continuation.events[0]
                    results.append(scenario_record("event_lookup_matches_feed_envelope"))

                    with factory.begin() as session:
                        cursor_row = session.get(NexoraEventCursorRow, first_page.next_cursor)
                        assert cursor_row is not None
                        cursor_row.created_at = datetime.now(UTC) - timedelta(seconds=2)
                        cursor_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                    try:
                        client.list_events(cursor=first_page.next_cursor, limit=1)
                    except CursorExpiredError as error:
                        assert error.status_code == 410
                    else:
                        raise AssertionError("expired cursor was accepted")
                    results.append(
                        scenario_record("expired_cursor_returns_410_and_triggers_full_resync")
                    )

                    decision_page = client.list_snapshots(ResourceType.DECISION_EVALUATION, limit=1)
                    evidence = decision_page.items[0]["source_reference"]
                    command = DecisionReviewCommand(
                        command_type=CommandType.ACCEPT,
                        decision_id=evidence["resource_id"],
                        portfolio_mode="paper",
                        reviewed_at=datetime.now(UTC) - timedelta(seconds=1),
                        reason="Stage 10 owner review fixture",
                        evidence=evidence,
                    )
                    review_key = "stage10-review-idempotency-0001"
                    accepted = client.submit_decision_review(command, idempotency_key=review_key)
                    duplicate = client.submit_decision_review(command, idempotency_key=review_key)
                    assert accepted.status == "accepted" and duplicate.status == "duplicate"
                    assert accepted.command_id == duplicate.command_id
                    results.append(
                        scenario_record("review_command_replay_returns_duplicate_receipt")
                    )
                    conflicting = command.model_copy(
                        update={"reason": "Different Stage 10 evidence"}
                    )
                    conflict = httpx.post(
                        f"{origin}/api/v1/integration/nexora/commands/decision-reviews",
                        json=conflicting.model_dump(mode="json"),
                        headers={
                            **request_headers(token),
                            "Content-Type": "application/json",
                            "Idempotency-Key": review_key,
                        },
                        trust_env=False,
                    )
                    assert conflict.status_code == 409
                    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
                    results.append(scenario_record("review_idempotency_conflict_returns_409"))

                    concurrency = profile["decision_review_command"]["optimistic_concurrency"]
                    assert concurrency == {
                        "enforced_by": "nexora_local_owner_review",
                        "expected_version_required_locally": True,
                        "provider_guard": "immutable_source_evidence_checksum",
                        "provider_expected_version_field_required": False,
                    }
                    assert "expected_version" not in command.model_dump(mode="json")
                    results.append(
                        scenario_record(
                            "local_review_expected_version_conflict_is_rejected_before_provider_command",
                            mode="cross_repository_fixture_contract",
                        )
                    )

                    export_request = ExportRequest(
                        mode="full",
                        formats=("json", "jsonl", "csv", "parquet", "zip_bundle"),
                        profile="ai_safe",
                        scope=(ResourceType.DECISION_EVALUATION, ResourceType.ALERT),
                        filters={"base_currency": "USDT", "portfolio_mode": "paper"},
                    )
                    export_status = client.create_export(
                        export_request,
                        idempotency_key="stage10-export-idempotency-0001",
                    )
                    subprocess.run(
                        [sys.executable, "scripts/run_background_worker.py", "--once"],
                        cwd=ROOT,
                        env=environment,
                        check=True,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    completed = client.get_export(export_status.export_id)
                    manifest = client.get_export_manifest(export_status.export_id)
                    assert completed.status == "complete"
                    assert manifest.completion_status == "complete"
                    with factory() as session:
                        artifacts = tuple(
                            session.scalars(
                                select(NexoraExportArtifactRow).where(
                                    NexoraExportArtifactRow.export_id == export_status.export_id
                                )
                            ).all()
                        )
                    files = {item.path: item for item in manifest.files}
                    assert len(files) == len(artifacts) == 5
                    for artifact in artifacts:
                        declared = files[artifact.path]
                        assert hashlib.sha256(artifact.content).hexdigest() == declared.sha256
                        assert len(artifact.content) == declared.size_bytes
                    results.append(
                        scenario_record("complete_export_manifest_verifies_all_checksums")
                    )

                log_file.flush()
                secret_haystack = log_path.read_text(encoding="utf-8")
                with factory() as session:
                    artifact_bytes = b"".join(
                        row.content for row in session.scalars(select(NexoraExportArtifactRow))
                    )
                assert token not in secret_haystack
                assert token.encode() not in artifact_bytes
                results.append(scenario_record("secrets_never_appear_in_payload_log_or_export"))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                engine.dispose()

    actual_names = [item["scenario"] for item in results]
    if actual_names != required_scenarios:
        raise RuntimeError("smoke scenario order or coverage drifted from the frozen profile")
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage_id": "TRD-V031-10",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "trd_bot": {"commit_sha": args.trd_commit_sha, "tree_sha": args.trd_tree_sha},
        "nexora": {
            "commit_sha": args.nexora_commit_sha,
            "tree_sha": args.nexora_tree_sha,
        },
        "workflow": {
            "run_id": args.workflow_run_id,
            "run_attempt": args.workflow_run_attempt,
        },
        "provider_profile_sha256": sha256_file(PROFILE_PATH),
        "provider_version": PROVIDER_VERSION,
        "transport": "http_loopback_only",
        "external_network_required": False,
        "scenarios": results,
        "passed": True,
        "provider_compatibility_evidence": True,
        "live_execution_enabled": False,
        "external_order_submission_allowed": False,
        "secrets_recorded": False,
    }
    report["report_checksum"] = hashlib.sha256(canonical_json(report)).hexdigest()
    return report


def main() -> int:
    args = parse_args()
    report = run_smoke(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json(report) + b"\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
