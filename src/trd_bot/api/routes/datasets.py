from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from trd_bot.api.dependencies import get_dataset_repository
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.domain.market_data import (
    OHLCVCandle,
    Timeframe,
    TradingPair,
)
from trd_bot.research import (
    DatasetBuilder,
    DatasetCatalogQuery,
    DatasetRepository,
    DatasetSnapshot,
    DatasetSummary,
    InvalidDatasetError,
)

router = APIRouter(
    prefix="/research/datasets",
    tags=["Research datasets"],
)

DatasetRepositoryDependency = Annotated[
    DatasetRepository,
    Depends(get_dataset_repository),
]

PaginationQuery = Annotated[
    PaginationParams,
    Query(),
]


class DatasetImportCandle(BaseModel):
    """One historical OHLCV candle supplied during dataset import."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    open_time: AwareDatetime
    close_time: AwareDatetime

    open_price: Decimal = Field(gt=0)
    high_price: Decimal = Field(gt=0)
    low_price: Decimal = Field(gt=0)
    close_price: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)

    is_closed: bool = True

    @model_validator(mode="after")
    def validate_price_and_time_ranges(self) -> Self:
        if self.close_time <= self.open_time:
            raise ValueError("close time must be after open time")

        if self.high_price < self.low_price:
            raise ValueError("high price cannot be lower than low price")

        highest_body_price = max(
            self.open_price,
            self.close_price,
        )

        lowest_body_price = min(
            self.open_price,
            self.close_price,
        )

        if self.high_price < highest_body_price:
            raise ValueError("high price cannot be lower than open or close price")

        if self.low_price > lowest_body_price:
            raise ValueError("low price cannot be higher than open or close price")

        return self


class DatasetImportRequest(BaseModel):
    """Historical OHLCV payload used to build an immutable dataset."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    source: str = Field(
        min_length=1,
        max_length=50,
    )

    pair: TradingPair
    timeframe: Timeframe

    candles: list[DatasetImportCandle] = Field(
        min_length=1,
        max_length=100_000,
    )

    @field_validator("name", "source")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("value cannot be empty")

        return normalized


class DatasetCatalogParams(DatasetCatalogQuery):
    """Combined filters, ordering, and pagination for the HTTP API."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )

    offset: int = Field(
        default=0,
        ge=0,
    )

    def catalog_query(self) -> DatasetCatalogQuery:
        return DatasetCatalogQuery.model_validate(
            self.model_dump(
                exclude={
                    "limit",
                    "offset",
                }
            )
        )


DatasetCatalogParamsQuery = Annotated[
    DatasetCatalogParams,
    Query(),
]


def _get_dataset_or_404(
    dataset_id: str,
    repository: DatasetRepository,
) -> DatasetSnapshot:
    dataset = repository.get(dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="dataset not found",
        )

    return dataset


@router.post(
    "",
    response_model=DatasetSummary,
    status_code=status.HTTP_201_CREATED,
)
def import_dataset(
    request: DatasetImportRequest,
    repository: DatasetRepositoryDependency,
) -> DatasetSummary:
    """Validate and store one immutable historical OHLCV dataset."""

    received_at = datetime.now(UTC)

    candles = tuple(
        OHLCVCandle(
            source=request.source,
            pair=request.pair,
            timeframe=request.timeframe,
            open_time=candle.open_time,
            close_time=candle.close_time,
            received_at=received_at,
            open_price=candle.open_price,
            high_price=candle.high_price,
            low_price=candle.low_price,
            close_price=candle.close_price,
            volume=candle.volume,
            is_closed=candle.is_closed,
        )
        for candle in request.candles
    )

    try:
        dataset = DatasetBuilder().build(
            name=request.name,
            candles=candles,
        )
    except InvalidDatasetError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "dataset failed quality checks",
                "candles_checked": error.report.candles_checked,
                "issues": [issue.model_dump(mode="json") for issue in error.report.issues],
            },
        ) from error

    stored_dataset = repository.save(dataset)

    return DatasetSummary.from_dataset(stored_dataset)


@router.get(
    "",
    response_model=Page[DatasetSummary],
)
def list_datasets(
    repository: DatasetRepositoryDependency,
    params: DatasetCatalogParamsQuery,
) -> Page[DatasetSummary]:
    """List stored historical dataset metadata without candle payloads."""

    query = params.catalog_query()

    pagination = PaginationParams(
        limit=params.limit,
        offset=params.offset,
    )

    datasets = repository.search_page(
        query=query,
        limit=params.limit,
        offset=params.offset,
    )

    summaries = tuple(DatasetSummary.from_dataset(dataset) for dataset in datasets)

    return build_page(
        summaries,
        total=repository.count_matching(query),
        pagination=pagination,
    )


@router.get(
    "/{dataset_id}/summary",
    response_model=DatasetSummary,
)
def get_dataset_summary(
    dataset_id: str,
    repository: DatasetRepositoryDependency,
) -> DatasetSummary:
    """Return lightweight metadata for one historical dataset."""

    dataset = _get_dataset_or_404(
        dataset_id=dataset_id,
        repository=repository,
    )

    return DatasetSummary.from_dataset(dataset)


@router.get(
    "/{dataset_id}/candles",
    response_model=Page[OHLCVCandle],
)
def list_dataset_candles(
    dataset_id: str,
    repository: DatasetRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[OHLCVCandle]:
    """Return one chronological page of stored historical candles."""

    dataset = _get_dataset_or_404(
        dataset_id=dataset_id,
        repository=repository,
    )

    candles = dataset.candles[pagination.offset : pagination.offset + pagination.limit]

    return build_page(
        candles,
        total=len(dataset.candles),
        pagination=pagination,
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetSnapshot,
)
def get_dataset(
    dataset_id: str,
    repository: DatasetRepositoryDependency,
) -> DatasetSnapshot:
    """Return one stored historical dataset including all candles."""

    return _get_dataset_or_404(
        dataset_id=dataset_id,
        repository=repository,
    )
