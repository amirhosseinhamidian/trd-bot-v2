from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from trd_bot.api.dependencies import get_dataset_repository
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.research import DatasetRepository, DatasetSnapshot, DatasetSummary

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


@router.get(
    "",
    response_model=Page[DatasetSummary],
)
def list_datasets(
    repository: DatasetRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[DatasetSummary]:
    """List stored historical dataset metadata without candle payloads."""

    datasets = repository.list_page(
        limit=pagination.limit,
        offset=pagination.offset,
    )
    summaries = tuple(DatasetSummary.from_dataset(dataset) for dataset in datasets)
    return build_page(
        summaries,
        total=repository.count(),
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
    """Return one stored historical dataset including its candles."""

    dataset = repository.get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")

    return dataset
