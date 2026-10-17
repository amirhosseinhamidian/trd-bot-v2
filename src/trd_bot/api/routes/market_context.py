from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field, field_validator, model_validator

from trd_bot.api.dependencies import get_market_context_product_reader
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.domain.market_data import MarketType, TradingPair
from trd_bot.market_context import MarketContextProductReader, MarketContextProductView

router = APIRouter(
    prefix="/market-context",
    tags=["Market context"],
)

MarketContextProductReaderDependency = Annotated[
    MarketContextProductReader,
    Depends(get_market_context_product_reader),
]


class MarketContextCatalogParams(PaginationParams):
    """Optional stream filters for the latest product-facing context views."""

    source: str | None = Field(default=None, min_length=1, max_length=50)
    base_asset: str | None = Field(
        default=None,
        min_length=2,
        max_length=15,
        pattern=r"^[A-Z0-9]+$",
    )
    quote_asset: str | None = Field(
        default=None,
        min_length=2,
        max_length=15,
        pattern=r"^[A-Z0-9]+$",
    )
    market_type: MarketType | None = None

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @field_validator("base_asset", "quote_asset", mode="before")
    @classmethod
    def normalize_asset(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_pair_filter(self) -> Self:
        if (self.base_asset is None) != (self.quote_asset is None):
            raise ValueError("base_asset and quote_asset must be provided together")
        return self

    @property
    def pair(self) -> TradingPair | None:
        if self.base_asset is None or self.quote_asset is None:
            return None
        return TradingPair(
            base_asset=self.base_asset,
            quote_asset=self.quote_asset,
            market_type=self.market_type or MarketType.SPOT,
        )


CatalogQuery = Annotated[MarketContextCatalogParams, Query()]


@router.get("", response_model=Page[MarketContextProductView])
def list_latest_market_context(
    reader: MarketContextProductReaderDependency,
    params: CatalogQuery,
) -> Page[MarketContextProductView]:
    """List the latest explainable context per source/pair with fail-closed availability."""

    items, total = reader.list_latest(
        limit=params.limit,
        offset=params.offset,
        source=params.source,
        pair=params.pair,
        market_type=params.market_type,
    )
    return build_page(items, total=total, pagination=params)


@router.get("/{assessment_id}", response_model=MarketContextProductView)
def get_market_context_assessment(
    assessment_id: str,
    reader: MarketContextProductReaderDependency,
) -> MarketContextProductView:
    """Return one immutable assessment and its current consumption decision."""

    view = reader.get(assessment_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="market-context assessment not found",
        )
    return view
