from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from trd_bot.api.dependencies import get_dataset_repository
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.main import app
from trd_bot.research import DatasetBuilder, DatasetSnapshot, InMemoryDatasetRepository

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
CREATED_AT = datetime(2026, 8, 22, 10, tzinfo=UTC)
client = TestClient(app)


@pytest.fixture
def repository() -> Iterator[InMemoryDatasetRepository]:
    dataset_repository = InMemoryDatasetRepository()

    def override_repository() -> InMemoryDatasetRepository:
        return dataset_repository

    app.dependency_overrides[get_dataset_repository] = override_repository

    try:
        yield dataset_repository
    finally:
        app.dependency_overrides.pop(get_dataset_repository, None)


def create_dataset(*, day: int, created_at: datetime) -> DatasetSnapshot:
    start = datetime(2026, 8, day, 10, tzinfo=UTC)
    candles = []

    for index, price_text in enumerate(("5", "6", "7")):
        price = Decimal(price_text) + Decimal(day)
        open_time = start + timedelta(hours=index)

        candles.append(
            OHLCVCandle(
                source="test-exchange",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                received_at=CREATED_AT,
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    return DatasetBuilder().build(
        name=f"Historical dataset {day}",
        candles=candles,
        created_at=created_at,
    )


def test_api_lists_empty_dataset_catalog(
    repository: InMemoryDatasetRepository,
) -> None:
    response = client.get("/api/v1/research/datasets")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
        "count": 0,
        "has_next": False,
        "has_previous": False,
    }


def test_api_lists_dataset_summaries_without_candles(
    repository: InMemoryDatasetRepository,
) -> None:
    dataset = create_dataset(day=1, created_at=CREATED_AT)
    repository.save(dataset)

    response = client.get("/api/v1/research/datasets")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["count"] == 1
    assert data["items"][0]["dataset_id"] == dataset.dataset_id
    assert data["items"][0]["candle_count"] == 3
    assert data["items"][0]["checksum"] == dataset.checksum
    assert "candles" not in data["items"][0]


def test_api_returns_dataset_with_candles(
    repository: InMemoryDatasetRepository,
) -> None:
    dataset = create_dataset(day=1, created_at=CREATED_AT)
    repository.save(dataset)

    response = client.get(f"/api/v1/research/datasets/{dataset.dataset_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["dataset_id"] == dataset.dataset_id
    assert len(data["candles"]) == dataset.candle_count


def test_api_returns_404_for_unknown_dataset(
    repository: InMemoryDatasetRepository,
) -> None:
    response = client.get("/api/v1/research/datasets/dataset-0000000000000000")

    assert response.status_code == 404
    assert response.json()["detail"] == "dataset not found"


def test_api_paginates_dataset_catalog(
    repository: InMemoryDatasetRepository,
) -> None:
    for index, day in enumerate((1, 2, 3)):
        repository.save(
            create_dataset(
                day=day,
                created_at=CREATED_AT + timedelta(hours=index),
            )
        )

    response = client.get(
        "/api/v1/research/datasets",
        params={
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["count"] == 2
    assert data["has_next"] is False
    assert data["has_previous"] is True
    assert [item["name"] for item in data["items"]] == [
        "Historical dataset 2",
        "Historical dataset 3",
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ],
)
def test_api_rejects_invalid_dataset_pagination(
    repository: InMemoryDatasetRepository,
    params: dict[str, int],
) -> None:
    response = client.get(
        "/api/v1/research/datasets",
        params=params,
    )

    assert response.status_code == 422
