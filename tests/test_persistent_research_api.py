from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db import (
    DatabaseBase,
    DatasetSnapshotRow,
    ResearchExperimentRow,
    WalkForwardRunRow,
    create_database_engine,
    create_session_factory,
    get_database_session,
)
from trd_bot.main import app


@pytest.fixture
def persistent_client(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api-persistence.db'}"
    engine = create_database_engine(database_url)
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    def override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_database_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        engine.dispose()


def create_candle_payload(index: int) -> dict[str, object]:
    prices = ("5", "4", "3", "4", "6", "5", "3", "4", "6", "8")
    price = Decimal(prices[index])
    hour = 10 + index
    return {
        "source": "test-exchange",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": "1h",
        "open_time": datetime(2026, 8, 21, hour, tzinfo=UTC).isoformat(),
        "close_time": datetime(2026, 8, 21, hour + 1, tzinfo=UTC).isoformat(),
        "received_at": datetime(2026, 8, 22, 10, tzinfo=UTC).isoformat(),
        "open_price": str(price),
        "high_price": str(price + Decimal("1")),
        "low_price": str(price - Decimal("1")),
        "close_price": str(price),
        "volume": "1000",
        "is_closed": True,
    }


def create_research_payload() -> dict[str, object]:
    return {
        "dataset_name": "Persistent API dataset",
        "candles": [create_candle_payload(index) for index in range(10)],
        "fast_period": 2,
        "slow_period": 3,
        "horizon_candles": 1,
    }


def test_experiment_survives_new_database_sessions(
    persistent_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = persistent_client
    create_response = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=create_research_payload(),
    )
    assert create_response.status_code == 200
    experiment_id = create_response.json()["experiment_id"]

    get_response = client.get(f"/api/v1/research/experiments/{experiment_id}")
    assert get_response.status_code == 200
    assert get_response.json()["experiment_id"] == experiment_id

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DatasetSnapshotRow)) == 1
        assert session.scalar(select(func.count()).select_from(ResearchExperimentRow)) == 1


def test_api_persists_one_dataset_for_idempotent_research_runs(
    persistent_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = persistent_client
    payload = create_research_payload()

    first_experiment = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=payload,
    )
    second_experiment = client.post(
        "/api/v1/research/experiments/ema-crossover",
        json=payload,
    )

    walk_forward_payload = {
        **payload,
        "train_candles": 4,
        "test_candles": 2,
        "step_candles": 2,
        "gap_candles": 0,
        "mode": "rolling",
    }
    walk_forward = client.post(
        "/api/v1/research/walk-forward/runs/ema-crossover",
        json=walk_forward_payload,
    )

    assert first_experiment.status_code == 200
    assert second_experiment.status_code == 200
    assert walk_forward.status_code == 200
    assert first_experiment.json()["experiment_id"] == second_experiment.json()["experiment_id"]

    execution_id = walk_forward.json()["execution_id"]
    get_run = client.get(f"/api/v1/research/walk-forward/runs/{execution_id}")
    assert get_run.status_code == 200

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DatasetSnapshotRow)) == 1
        assert session.scalar(select(func.count()).select_from(ResearchExperimentRow)) == 1
        assert session.scalar(select(func.count()).select_from(WalkForwardRunRow)) == 1
