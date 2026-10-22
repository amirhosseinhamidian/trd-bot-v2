from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from tests.test_market_context_features import AS_OF, PAIR, SOURCE, complete_input
from trd_bot.api.dependencies import get_market_context_product_reader
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyMarketContextEvaluationRunner,
    SqlAlchemyMarketContextProductReader,
    SqlAlchemyMarketDataEventStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain.market_data import MarketType, TradingPair
from trd_bot.main import app
from trd_bot.market_context import (
    MarketContextEvaluationJobPayload,
    MarketContextProductView,
    MarketContextUnavailableReason,
    MarketRegimeAssessment,
)

REQUESTED_AT = AS_OF + timedelta(minutes=5)
CURRENT_AT = AS_OF + timedelta(minutes=30)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def _seed_assessment(factory: sessionmaker[Session]) -> MarketRegimeAssessment:
    windows, _ = complete_input()
    with factory.begin() as session:
        store = SqlAlchemyMarketDataEventStore(session)
        for window in windows:
            store.stage_window_version(window)

    return SqlAlchemyMarketContextEvaluationRunner(factory).run(
        MarketContextEvaluationJobPayload.build(
            source=SOURCE,
            pair=PAIR,
            as_of=AS_OF,
            requested_at=REQUESTED_AT,
        )
    )


def test_product_view_is_consumable_only_for_current_ready_unexpired_assessment(
    factory: sessionmaker[Session],
) -> None:
    assessment = _seed_assessment(factory)

    current = MarketContextProductView.from_assessment(
        assessment,
        evaluated_at=CURRENT_AT,
    )
    stale = MarketContextProductView.from_assessment(
        assessment,
        evaluated_at=AS_OF + timedelta(hours=1, minutes=10),
    )

    assert current.consumable is True
    assert current.unavailable_reasons == ()
    assert current.expected_as_of == AS_OF
    assert current.boundary_lag_seconds == 0
    assert current.seconds_until_expiry == int((assessment.expires_at - CURRENT_AT).total_seconds())

    assert stale.consumable is False
    assert stale.unavailable_reasons == (
        MarketContextUnavailableReason.ASSESSMENT_EXPIRED,
        MarketContextUnavailableReason.BOUNDARY_MISMATCH,
    )
    assert stale.boundary_lag_seconds == 3600
    assert stale.seconds_until_expiry == 0

    invalid = current.model_dump()
    invalid["consumable"] = False
    with pytest.raises(ValidationError, match="consumption decision is inconsistent"):
        MarketContextProductView.model_validate(invalid)


def test_reader_lists_latest_context_with_filters_and_returns_immutable_detail(
    factory: sessionmaker[Session],
) -> None:
    assessment = _seed_assessment(factory)

    with factory() as session:
        reader = SqlAlchemyMarketContextProductReader(session)
        items, total = reader.list_latest(
            limit=20,
            offset=0,
            source=f"  {SOURCE}  ",
            pair=PAIR,
            evaluated_at=CURRENT_AT,
        )
        missing, missing_total = reader.list_latest(
            limit=20,
            offset=0,
            source="binance-public",
            market_type=MarketType.SPOT,
            evaluated_at=CURRENT_AT,
        )
        detail = reader.get(assessment.assessment_id, evaluated_at=CURRENT_AT)

    assert total == 1
    assert items == (detail,)
    assert items[0].assessment.evidence == assessment.evidence
    assert items[0].assessment.input_checksum == assessment.input_checksum
    assert missing == ()
    assert missing_total == 0


class StaticMarketContextProductReader:
    def __init__(self, view: MarketContextProductView) -> None:
        self.view = view

    def list_latest(
        self,
        *,
        limit: int,
        offset: int,
        source: str | None = None,
        pair: TradingPair | None = None,
        market_type: MarketType | None = None,
        evaluated_at: datetime | None = None,
    ) -> tuple[tuple[MarketContextProductView, ...], int]:
        del source, pair, market_type, evaluated_at
        return ((self.view,) if offset == 0 and limit > 0 else (), 1)

    def get(
        self,
        assessment_id: str,
        *,
        evaluated_at: datetime | None = None,
    ) -> MarketContextProductView | None:
        del evaluated_at
        return self.view if assessment_id == self.view.assessment.assessment_id else None


@pytest.fixture
def market_context_api(
    factory: sessionmaker[Session],
) -> Iterator[tuple[TestClient, MarketContextProductView]]:
    assessment = _seed_assessment(factory)
    view = MarketContextProductView.from_assessment(assessment, evaluated_at=CURRENT_AT)
    app.dependency_overrides[get_market_context_product_reader] = lambda: (
        StaticMarketContextProductReader(view)
    )
    try:
        yield TestClient(app), view
    finally:
        app.dependency_overrides.pop(get_market_context_product_reader, None)


def test_api_exposes_filtered_catalog_and_assessment_detail_as_read_only(
    market_context_api: tuple[TestClient, MarketContextProductView],
) -> None:
    client, expected = market_context_api

    catalog = client.get(
        "/api/v1/market-context",
        params={
            "source": SOURCE,
            "base_asset": "btc",
            "quote_asset": "usdt",
            "market_type": "spot",
        },
    )
    detail = client.get(f"/api/v1/market-context/{expected.assessment.assessment_id}")

    assert catalog.status_code == 200
    assert catalog.json()["items"] == [expected.model_dump(mode="json")]
    assert catalog.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json() == expected.model_dump(mode="json")
    assert client.get("/api/v1/market-context/market-regime-0000000000000000").status_code == 404
    assert client.post("/api/v1/market-context").status_code == 405


def test_api_rejects_partial_pair_filter(
    market_context_api: tuple[TestClient, MarketContextProductView],
) -> None:
    client, _ = market_context_api

    response = client.get("/api/v1/market-context", params={"base_asset": "BTC"})

    assert response.status_code == 422
    assert "input" not in str(response.json())
    assert "base_asset and quote_asset must be provided together" in str(response.json())
