from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from trd_bot.core.config import get_settings
from trd_bot.db.base import DatabaseBase
from trd_bot.db.models import (
    DecisionCandidateRankingRow,
    DecisionEvaluationIntentRow,
    DecisionRiskGateRow,
    MarketRegimeAssessmentRow,
)
from trd_bot.db.session import get_database_session
from trd_bot.integration.nexora.decision_snapshots import (
    DECISION_SNAPSHOT_RESOURCE_TYPES,
    DecisionSnapshotResourceReader,
)
from trd_bot.integration.nexora.snapshots import SnapshotPage, build_source_checksum
from trd_bot.main import create_app

SERVICE_TOKEN = "nexora-test-token-0123456789-abcdef"
SNAPSHOT_ROOT = "/api/v1/integration/nexora/snapshots"
CREATED_AT = datetime(2026, 11, 7, 5, tzinfo=UTC)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    DatabaseBase.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def client(
    factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    token_file = tmp_path / "nexora-service-token"
    token_file.write_text(SERVICE_TOKEN, encoding="ascii")
    token_file.chmod(0o600)
    monkeypatch.setenv("TRD_BOT_NEXORA_SERVICE_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("TRD_BOT_ENVIRONMENT", "development")
    monkeypatch.setenv("TRD_BOT_APP_VERSION", "0.3.0")
    get_settings.cache_clear()

    def session_override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_database_session] = session_override
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        yield test_client
    get_settings.cache_clear()


def headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {SERVICE_TOKEN}",
        "X-Correlation-ID": str(uuid4()),
    }


def seed_resources(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        session.add(
            MarketRegimeAssessmentRow(
                assessment_id="market-context-assessment-1",
                schema_version="market-regime-assessment-v1",
                manifest_id="market-context-manifest-1",
                feature_snapshot_id="market-context-features-1",
                source="fixture-public",
                base_asset="BTC",
                quote_asset="USDT",
                market_type="spot",
                as_of=CREATED_AT,
                input_checksum="1" * 64,
                feature_set_version="feature-set-v1",
                feature_set_checksum="2" * 64,
                feature_snapshot_checksum="3" * 64,
                algorithm_version="regime-v1",
                status="ready",
                trend="trending_up",
                volatility="normal",
                confidence=Decimal("0.875"),
                evidence_count=3,
                issue_count=0,
                payload_json='{"status":"ready","trend":"trending_up"}',
                assessed_at=CREATED_AT + timedelta(minutes=1),
                expires_at=CREATED_AT + timedelta(hours=1),
            )
        )
        for index in range(2):
            suffix = str(index + 1)
            observed_at = CREATED_AT + timedelta(minutes=10 + index)
            evaluation_id = f"decision-evaluation-snapshot-{suffix}"
            session.add(
                DecisionEvaluationIntentRow(
                    evaluation_id=evaluation_id,
                    schema_version="decision-evaluation-intent-v1",
                    stage="strategy_evaluation",
                    mode="paper",
                    dataset_id=f"dataset-snapshot-{suffix}",
                    dataset_reference_id=f"dataset-reference-{suffix}",
                    dataset_reference_checksum=suffix * 64,
                    strategy_reference_id=f"strategy-reference-{suffix}",
                    strategy_name="ema-crossover",
                    strategy_version="1",
                    strategy_behavior_fingerprint="sha256:" + suffix * 64,
                    strategy_reference_checksum=(str(index + 3)) * 64,
                    market_context_reference_id="market-context-reference-1",
                    market_context_assessment_id="market-context-assessment-1",
                    market_context_reference_checksum=(str(index + 5)) * 64,
                    policy_id="decision-policy-default",
                    policy_version=1,
                    policy_definition_checksum=(str(index + 7)) * 64,
                    source="fixture-public",
                    base_asset="BTC",
                    quote_asset="USDT",
                    market_type="spot",
                    timeframe="1h",
                    requested_at=observed_at,
                    offline_only=True,
                    external_order_submission_allowed=False,
                    idempotency_key=f"decision-snapshot-idempotency-{suffix}",
                    intent_checksum=(str(index + 1)) * 63 + "a",
                    payload_json=(
                        '{"schema_version":"decision-evaluation-intent-v1",'
                        f'"evaluation_id":"{evaluation_id}","offline_only":true,'
                        '"external_order_submission_allowed":false}'
                    ),
                )
            )
            session.add(
                DecisionCandidateRankingRow(
                    evaluation_id=evaluation_id,
                    outcome_id=f"candidate-outcome-{suffix}",
                    schema_version="decision-candidate-ranking-v1",
                    policy_version="1",
                    policy_checksum=(str(index + 2)) * 64,
                    disposition="accepted",
                    source_signal_count=1,
                    candidate_count=1,
                    excluded_signal_count=0,
                    top_candidate_id=f"candidate-snapshot-{suffix}",
                    ranked_at=observed_at + timedelta(seconds=1),
                    offline_only=True,
                    external_order_submission_allowed=False,
                    record_checksum=(str(index + 4)) * 64,
                    payload_json=(
                        '{"schema_version":"decision-candidate-ranking-v1",'
                        f'"top_candidate_id":"candidate-snapshot-{suffix}",'
                        '"offline_only":true,"external_order_submission_allowed":false}'
                    ),
                )
            )
            session.add(
                DecisionRiskGateRow(
                    evaluation_id=evaluation_id,
                    outcome_id=f"risk-outcome-{suffix}",
                    schema_version="decision-risk-gate-v1",
                    candidate_ranking_checksum=(str(index + 4)) * 64,
                    policy_version="1",
                    policy_checksum=(str(index + 6)) * 64,
                    disposition="accepted",
                    decision="approved",
                    assessment_id=f"risk-assessment-{suffix}",
                    assessment_checksum=(str(index + 8)) * 64,
                    approved_candidate_id=f"candidate-snapshot-{suffix}",
                    has_position_sizing=True,
                    evaluated_at=observed_at + timedelta(seconds=2),
                    offline_only=True,
                    external_order_submission_allowed=False,
                    record_checksum=(str(index + 5)) * 63 + "b",
                    payload_json=(
                        '{"schema_version":"decision-risk-gate-v1","decision":"approved",'
                        '"offline_only":true,"external_order_submission_allowed":false}'
                    ),
                )
            )
        session.commit()


def test_reader_exposes_exact_decision_resource_allowlist(
    factory: sessionmaker[Session],
) -> None:
    seed_resources(factory)
    with factory() as session:
        reader = DecisionSnapshotResourceReader(session)
        for resource_type in DECISION_SNAPSHOT_RESOURCE_TYPES:
            boundary = reader.capture_boundary(
                resource_type=resource_type,
                captured_at=CREATED_AT + timedelta(days=1),
            )
            records = reader.list_records(
                resource_type=resource_type,
                boundary_key=boundary,
                after_sort_key=None,
                limit=10,
            )
            assert records
            assert all(record.resource_type == resource_type for record in records)
            assert all(record.payload["offline_only"] is True for record in records)
            assert all(
                record.payload["external_order_submission_allowed"] is False for record in records
            )


def test_authenticated_decision_endpoint_pages_with_source_checksums(
    factory: sessionmaker[Session],
    client: TestClient,
) -> None:
    seed_resources(factory)
    first_headers = headers()
    first = client.get(
        f"{SNAPSHOT_ROOT}/decision_evaluation?limit=1",
        headers=first_headers,
    )

    assert first.status_code == 200
    assert first.headers["x-correlation-id"] == first_headers["X-Correlation-ID"]
    assert first.headers["cache-control"] == "private, no-store"
    first_page = SnapshotPage.model_validate(first.json())
    assert first_page.has_more is True
    assert first_page.next_cursor is not None
    item = first_page.items[0]
    assert item.payload["offline_only"] is True
    assert item.payload["external_order_submission_allowed"] is False
    assert item.source_reference.checksum == build_source_checksum(
        resource_type=item.source_reference.resource_type,
        resource_id=item.source_reference.resource_id,
        resource_schema_version=item.source_reference.resource_schema_version,
        observed_at=item.source_reference.observed_at,
        payload=item.payload,
    )

    second = client.get(
        f"{SNAPSHOT_ROOT}/decision_evaluation",
        params={"cursor": first_page.next_cursor},
        headers=headers(),
    )
    second_page = SnapshotPage.model_validate(second.json())
    assert second.status_code == 200
    assert second_page.has_more is False
    assert second_page.items[0].source_reference.resource_id != (
        first_page.items[0].source_reference.resource_id
    )


def test_decision_resources_fail_closed_for_cross_resource_cursor_and_unknown_type(
    factory: sessionmaker[Session],
    client: TestClient,
) -> None:
    seed_resources(factory)
    first = client.get(
        f"{SNAPSHOT_ROOT}/decision_evaluation?limit=1",
        headers=headers(),
    )
    cursor = SnapshotPage.model_validate(first.json()).next_cursor
    assert cursor is not None

    conflict = client.get(
        f"{SNAPSHOT_ROOT}/risk_gate",
        params={"cursor": cursor},
        headers=headers(),
    )
    unavailable = client.get(f"{SNAPSHOT_ROOT}/event", headers=headers())

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CURSOR_CONFLICT"
    assert unavailable.status_code == 400
    assert SERVICE_TOKEN not in conflict.text
