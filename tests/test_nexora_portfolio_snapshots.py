from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from trd_bot.backtesting import PositionSide
from trd_bot.core.config import get_settings
from trd_bot.db.base import DatabaseBase
from trd_bot.db.models import (
    DecisionPortfolioIntelligenceRow,
    NexoraSnapshotCursorRow,
    NexoraSnapshotScanRow,
)
from trd_bot.db.session import get_database_session
from trd_bot.db.simulated_portfolio_repositories import (
    SqlAlchemySimulatedPortfolioRepository,
)
from trd_bot.domain.market_data import TradingPair
from trd_bot.integration.nexora.portfolio_snapshots import (
    PORTFOLIO_SNAPSHOT_RESOURCE_TYPES,
    PortfolioSnapshotResourceReader,
)
from trd_bot.integration.nexora.snapshots import (
    SnapshotPage,
    build_source_checksum,
)
from trd_bot.main import create_app
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode

SERVICE_TOKEN = "nexora-test-token-0123456789-abcdef"
SNAPSHOT_ROOT = "/api/v1/integration/nexora/snapshots"
CREATED_AT = datetime(2026, 11, 1, 10, tzinfo=UTC)


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


def headers(*, token: str = SERVICE_TOKEN) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": str(uuid4()),
    }


def seed_resources(factory: sessionmaker[Session]) -> None:
    pair = TradingPair(base_asset="BTC", quote_asset="USDT")
    ledger = SimulatedPortfolioLedger()
    with factory() as session:
        repository = SqlAlchemySimulatedPortfolioRepository(session)
        for index, mode in enumerate((SimulationMode.PAPER, SimulationMode.SHADOW)):
            created_at = CREATED_AT + timedelta(minutes=index)
            portfolio = ledger.create(
                mode=mode,
                dataset_id=f"dataset-{index}",
                starting_cash=Decimal("10000"),
                fee_rate=Decimal("0.001"),
                created_at=created_at,
            )
            opened = ledger.open_position(
                portfolio,
                pair=pair,
                side=PositionSide.LONG,
                price=Decimal("100"),
                quantity=Decimal("1"),
                occurred_at=created_at + timedelta(minutes=1),
            )
            closed = ledger.close_position(
                opened,
                position_id=opened.positions[0].position_id,
                price=Decimal("110"),
                occurred_at=created_at + timedelta(minutes=2),
            )
            repository.save(
                ledger.complete(closed, occurred_at=created_at + timedelta(minutes=3)),
                commit=False,
            )
        session.add(
            DecisionPortfolioIntelligenceRow(
                evaluation_id="evaluation-snapshot-1",
                outcome_id="outcome-snapshot-1",
                schema_version="decision-portfolio-intelligence-v1",
                risk_gate_checksum="a" * 64,
                policy_version="1",
                policy_checksum="b" * 64,
                disposition="accepted",
                recommendation="accept",
                has_analysis=True,
                snapshot_id="snapshot-1",
                candidate_id="candidate-1",
                analyzed_at=CREATED_AT + timedelta(minutes=10),
                offline_only=True,
                external_order_submission_allowed=False,
                record_checksum="c" * 64,
                payload_json=(
                    '{"schema_version":"decision-portfolio-intelligence-v1",'
                    '"evaluation_id":"evaluation-snapshot-1","offline_only":true,'
                    '"external_order_submission_allowed":false}'
                ),
            )
        )
        session.commit()


def test_reader_exposes_exact_portfolio_resource_allowlist(
    factory: sessionmaker[Session],
) -> None:
    seed_resources(factory)
    with factory() as session:
        reader = PortfolioSnapshotResourceReader(session)
        for resource_type in PORTFOLIO_SNAPSHOT_RESOURCE_TYPES:
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
            assert all(
                record.payload["resource_schema_version"] == record.resource_schema_version
                for record in records
            )


def test_authenticated_endpoint_pages_deterministically_with_checksums(
    factory: sessionmaker[Session],
    client: TestClient,
) -> None:
    seed_resources(factory)
    request_headers = headers()
    first = client.get(
        f"{SNAPSHOT_ROOT}/paper_shadow_portfolio?limit=1",
        headers=request_headers,
    )

    assert first.status_code == 200
    assert first.headers["x-contract-version"] == "nexora-trd-integration-v1"
    assert first.headers["x-correlation-id"] == request_headers["X-Correlation-ID"]
    assert first.headers["x-trd-bot-version"] == "0.3.0"
    assert first.headers["cache-control"] == "private, no-store"
    first_page = SnapshotPage.model_validate(first.json())
    assert first_page.has_more is True
    assert first_page.next_cursor is not None
    item = first_page.items[0]
    assert item.source_reference.checksum == build_source_checksum(
        resource_type=item.source_reference.resource_type,
        resource_id=item.source_reference.resource_id,
        resource_schema_version=item.source_reference.resource_schema_version,
        observed_at=item.source_reference.observed_at,
        payload=item.payload,
    )

    second = client.get(
        f"{SNAPSHOT_ROOT}/paper_shadow_portfolio",
        params={"cursor": first_page.next_cursor},
        headers=headers(),
    )
    second_page = SnapshotPage.model_validate(second.json())
    assert second.status_code == 200
    assert second_page.has_more is False
    assert second_page.next_cursor is None
    assert second_page.items[0].source_reference.resource_id != (
        first_page.items[0].source_reference.resource_id
    )


def test_resource_auth_allowlist_and_cursor_fail_closed(
    factory: sessionmaker[Session],
    client: TestClient,
) -> None:
    seed_resources(factory)
    unauthorized = client.get(
        f"{SNAPSHOT_ROOT}/paper_shadow_position",
        headers={"Accept": "application/json", "X-Correlation-ID": str(uuid4())},
    )
    unavailable = client.get(f"{SNAPSHOT_ROOT}/event", headers=headers())
    unknown_cursor = client.get(
        f"{SNAPSHOT_ROOT}/paper_shadow_position",
        params={"cursor": "snp_" + "0" * 64},
        headers=headers(),
    )

    assert unauthorized.status_code == 401
    assert unavailable.status_code == 400
    assert unknown_cursor.status_code == 400
    assert SERVICE_TOKEN not in unauthorized.text


def test_expired_cursor_returns_410_and_requires_full_resync(
    factory: sessionmaker[Session],
    client: TestClient,
) -> None:
    seed_resources(factory)
    first = client.get(
        f"{SNAPSHOT_ROOT}/paper_shadow_portfolio?limit=1",
        headers=headers(),
    )
    cursor = SnapshotPage.model_validate(first.json()).next_cursor
    assert cursor is not None
    with factory.begin() as session:
        cursor_row = session.get(NexoraSnapshotCursorRow, cursor)
        assert cursor_row is not None
        scan_row = session.scalar(
            select(NexoraSnapshotScanRow).where(NexoraSnapshotScanRow.scan_id == cursor_row.scan_id)
        )
        assert scan_row is not None
        opened_at = datetime.now(UTC) - timedelta(hours=2)
        expired_at = datetime.now(UTC) - timedelta(hours=1)
        cursor_row.created_at = opened_at
        cursor_row.expires_at = expired_at
        scan_row.boundary_at = opened_at
        scan_row.opened_at = opened_at
        scan_row.expires_at = expired_at

    expired = client.get(
        f"{SNAPSHOT_ROOT}/paper_shadow_portfolio",
        params={"cursor": cursor},
        headers=headers(),
    )

    assert expired.status_code == 410
    assert expired.json()["error"]["code"] == "CURSOR_EXPIRED"
    assert "full resync" in expired.json()["error"]["message"]
    assert expired.json()["error"]["details"] == {
        "action": "full_snapshot_resync",
        "partial_snapshot_publish_allowed": False,
        "projection_publication": "pause",
        "stale_or_degraded_state_visible": True,
        "trigger": "cursor_expired_response",
    }
