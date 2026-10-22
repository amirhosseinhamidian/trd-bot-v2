from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from trd_bot.api.dependencies import get_background_job_repository
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.jobs import (
    BackgroundJob,
    BackgroundJobRepository,
    BackgroundJobStatus,
    BackgroundJobSummary,
)

router = APIRouter(prefix="/jobs", tags=["Background jobs"])

JobRepositoryDependency = Annotated[
    BackgroundJobRepository,
    Depends(get_background_job_repository),
]


def _get_job_or_404(job_id: str, repository: BackgroundJobRepository) -> BackgroundJob:
    job = repository.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="background job not found",
        )
    return job


@router.get("", response_model=Page[BackgroundJobSummary])
def list_background_jobs(
    repository: JobRepositoryDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    job_status: Annotated[list[BackgroundJobStatus] | None, Query(alias="status")] = None,
) -> Page[BackgroundJobSummary]:
    pagination = PaginationParams(limit=limit, offset=offset)
    statuses = None if not job_status else tuple(job_status)
    items = tuple(
        BackgroundJobSummary.from_job(job)
        for job in repository.list_page(
            limit=pagination.limit,
            offset=pagination.offset,
            statuses=statuses,
        )
    )
    return build_page(
        items,
        total=repository.count(statuses=statuses),
        pagination=pagination,
    )


@router.get("/{job_id}", response_model=BackgroundJobSummary)
def get_background_job(
    job_id: str,
    repository: JobRepositoryDependency,
) -> BackgroundJobSummary:
    return BackgroundJobSummary.from_job(_get_job_or_404(job_id, repository))


@router.post("/{job_id}/cancel", response_model=BackgroundJobSummary)
def cancel_background_job(
    job_id: str,
    repository: JobRepositoryDependency,
) -> BackgroundJobSummary:
    _get_job_or_404(job_id, repository)
    return BackgroundJobSummary.from_job(repository.request_cancel(job_id))


@router.post("/{job_id}/retry", response_model=BackgroundJobSummary)
def retry_background_job(
    job_id: str,
    repository: JobRepositoryDependency,
) -> BackgroundJobSummary:
    _get_job_or_404(job_id, repository)
    try:
        return BackgroundJobSummary.from_job(repository.retry_failed(job_id))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "job_not_retryable", "message": str(error)},
        ) from error
