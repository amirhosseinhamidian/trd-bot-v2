from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from trd_bot.api.dependencies import get_dataset_repository
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research import (
    DatasetCatalogQuery,
    DatasetRepository,
    DatasetSnapshot,
    DatasetSummary,
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
            status_code=404,
            detail="dataset not found",
        )

    return dataset


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
