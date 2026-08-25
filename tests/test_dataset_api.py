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


def create_dataset(
    *,
    day: int,
    created_at: datetime,
    source: str = "test-exchange",
    pair: TradingPair = PAIR,
    timeframe: Timeframe = Timeframe.HOUR_1,
) -> DatasetSnapshot:
    start = datetime(
        2026,
        8,
        day,
        10,
        tzinfo=UTC,
    )

    interval = {
        Timeframe.MINUTES_15: timedelta(minutes=15),
        Timeframe.HOUR_1: timedelta(hours=1),
        Timeframe.HOURS_4: timedelta(hours=4),
        Timeframe.DAY_1: timedelta(days=1),
    }[timeframe]

    candles = []

    for index, price_text in enumerate(("5", "6", "7")):
        price = Decimal(price_text) + Decimal(day)
        open_time = start + interval * index

        candles.append(
            OHLCVCandle(
                source=source,
                pair=pair,
                timeframe=timeframe,
                open_time=open_time,
                close_time=open_time + interval,
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


def test_api_filters_dataset_catalog(
    repository: InMemoryDatasetRepository,
) -> None:
    repository.save(
        create_dataset(
            day=1,
            created_at=CREATED_AT,
        )
    )

    repository.save(
        create_dataset(
            day=2,
            created_at=CREATED_AT + timedelta(hours=1),
            source="historical-archive",
            pair=TradingPair(
                base_asset="ETH",
                quote_asset="USDT",
            ),
            timeframe=Timeframe.HOURS_4,
        )
    )

    repository.save(
        create_dataset(
            day=3,
            created_at=CREATED_AT + timedelta(hours=2),
            pair=TradingPair(
                base_asset="BTC",
                quote_asset="USDC",
            ),
        )
    )

    response = client.get(
        "/api/v1/research/datasets",
        params={
            "source": "test-exchange",
            "base_asset": "btc",
            "quote_asset": "usdt",
            "timeframe": "1h",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["count"] == 1
    assert data["items"][0]["pair"]["base_asset"] == "BTC"
    assert data["items"][0]["pair"]["quote_asset"] == "USDT"


def test_api_sorts_dataset_catalog_descending(
    repository: InMemoryDatasetRepository,
) -> None:
    for index, day in enumerate((1, 2, 3)):
        repository.save(
            create_dataset(
                day=day,
                created_at=(CREATED_AT + timedelta(hours=index)),
            )
        )

    response = client.get(
        "/api/v1/research/datasets",
        params={
            "sort_by": "created_at",
            "sort_direction": "desc",
        },
    )

    assert response.status_code == 200

    assert [item["name"] for item in response.json()["items"]] == [
        "Historical dataset 3",
        "Historical dataset 2",
        "Historical dataset 1",
    ]


def test_filtered_total_is_calculated_before_pagination(
    repository: InMemoryDatasetRepository,
) -> None:
    repository.save(
        create_dataset(
            day=1,
            created_at=CREATED_AT,
        )
    )

    repository.save(
        create_dataset(
            day=2,
            created_at=CREATED_AT + timedelta(hours=1),
        )
    )

    repository.save(
        create_dataset(
            day=3,
            created_at=CREATED_AT + timedelta(hours=2),
            pair=TradingPair(
                base_asset="ETH",
                quote_asset="USDT",
            ),
        )
    )

    response = client.get(
        "/api/v1/research/datasets",
        params={
            "base_asset": "BTC",
            "limit": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert data["count"] == 1
    assert data["has_next"] is True


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


@pytest.mark.parametrize(
    "params",
    [
        {"timeframe": "2h"},
        {"sort_by": "unsupported"},
        {"sort_direction": "sideways"},
        {"base_asset": "$"},
    ],
)
def test_api_rejects_invalid_dataset_catalog_query(
    repository: InMemoryDatasetRepository,
    params: dict[str, str],
) -> None:
    response = client.get(
        "/api/v1/research/datasets",
        params=params,
    )

    assert response.status_code == 422


def test_api_returns_lightweight_dataset_summary(
    repository: InMemoryDatasetRepository,
) -> None:
    dataset = create_dataset(
        day=1,
        created_at=CREATED_AT,
    )
    repository.save(dataset)

    response = client.get(f"/api/v1/research/datasets/{dataset.dataset_id}/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["dataset_id"] == dataset.dataset_id
    assert data["name"] == dataset.name
    assert data["candle_count"] == dataset.candle_count
    assert data["checksum"] == dataset.checksum
    assert "candles" not in data


def test_api_paginates_dataset_candles(
    repository: InMemoryDatasetRepository,
) -> None:
    dataset = create_dataset(
        day=1,
        created_at=CREATED_AT,
    )
    repository.save(dataset)

    response = client.get(
        f"/api/v1/research/datasets/{dataset.dataset_id}/candles",
        params={
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert data["count"] == 2
    assert data["has_previous"] is True
    assert data["has_next"] is False

    assert [item["open_price"] for item in data["items"]] == [
        "7",
        "8",
    ]


def test_api_preserves_chronological_candle_order(
    repository: InMemoryDatasetRepository,
) -> None:
    dataset = create_dataset(
        day=1,
        created_at=CREATED_AT,
    )
    repository.save(dataset)

    response = client.get(
        f"/api/v1/research/datasets/{dataset.dataset_id}/candles",
        params={
            "limit": 3,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    open_times = [item["open_time"] for item in response.json()["items"]]

    assert open_times == sorted(open_times)


@pytest.mark.parametrize(
    "path_suffix",
    [
        "summary",
        "candles",
    ],
)
def test_api_returns_404_for_unknown_dataset_resource(
    repository: InMemoryDatasetRepository,
    path_suffix: str,
) -> None:
    response = client.get(f"/api/v1/research/datasets/dataset-0000000000000000/{path_suffix}")

    assert response.status_code == 404
    assert response.json()["detail"] == "dataset not found"


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ],
)
def test_api_rejects_invalid_candle_pagination(
    repository: InMemoryDatasetRepository,
    params: dict[str, int],
) -> None:
    dataset = create_dataset(
        day=1,
        created_at=CREATED_AT,
    )
    repository.save(dataset)

    response = client.get(
        f"/api/v1/research/datasets/{dataset.dataset_id}/candles",
        params=params,
    )

    assert response.status_code == 422


def dataset_import_payload(
    *,
    candle_offsets: tuple[int, ...] = (0, 1, 2),
    is_closed: bool = True,
) -> dict[str, object]:
    start_time = datetime(
        2026,
        8,
        20,
        10,
        tzinfo=UTC,
    )

    candles: list[dict[str, object]] = []

    for index, offset in enumerate(candle_offsets):
        open_time = start_time + timedelta(hours=offset)
        price = Decimal("100") + Decimal(index)

        candles.append(
            {
                "open_time": open_time.isoformat(),
                "close_time": (open_time + timedelta(hours=1)).isoformat(),
                "open_price": str(price),
                "high_price": str(price + Decimal("2")),
                "low_price": str(price - Decimal("2")),
                "close_price": str(price + Decimal("1")),
                "volume": "1500",
                "is_closed": is_closed,
            }
        )

    return {
        "name": "Imported historical BTC dataset",
        "source": "manual-import",
        "pair": {
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "market_type": "spot",
        },
        "timeframe": "1h",
        "candles": candles,
    }


def test_api_imports_historical_dataset(
    repository: InMemoryDatasetRepository,
) -> None:
    response = client.post(
        "/api/v1/research/datasets",
        json=dataset_import_payload(),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Imported historical BTC dataset"
    assert data["source"] == "manual-import"
    assert data["pair"] == {
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "market_type": "spot",
    }
    assert data["timeframe"] == "1h"
    assert data["candle_count"] == 3
    assert "candles" not in data

    stored_dataset = repository.get(data["dataset_id"])

    assert stored_dataset is not None
    assert stored_dataset.candle_count == 3


def test_api_import_is_idempotent_for_same_candles(
    repository: InMemoryDatasetRepository,
) -> None:
    payload = dataset_import_payload()

    first_response = client.post(
        "/api/v1/research/datasets",
        json=payload,
    )

    second_response = client.post(
        "/api/v1/research/datasets",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    assert first_response.json()["dataset_id"] == second_response.json()["dataset_id"]

    assert repository.count() == 1
    stored_dataset = repository.get(first_response.json()["dataset_id"])

    assert stored_dataset is not None
    assert stored_dataset.candle_count == 3


def test_api_rejects_dataset_with_missing_candle(
    repository: InMemoryDatasetRepository,
) -> None:
    response = client.post(
        "/api/v1/research/datasets",
        json=dataset_import_payload(
            candle_offsets=(0, 2),
        ),
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail["message"] == "dataset failed quality checks"
    assert detail["candles_checked"] == 2

    assert any(issue["code"] == "missing_candle" for issue in detail["issues"])

    assert repository.count() == 0


def test_api_rejects_unclosed_historical_candles(
    repository: InMemoryDatasetRepository,
) -> None:
    response = client.post(
        "/api/v1/research/datasets",
        json=dataset_import_payload(
            is_closed=False,
        ),
    )

    assert response.status_code == 422

    issue_codes = {issue["code"] for issue in response.json()["detail"]["issues"]}

    assert "open_candle" in issue_codes
    assert repository.count() == 0
