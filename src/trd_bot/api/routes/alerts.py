from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from trd_bot.alerts import (
    AlertActionConflictError,
    AlertInboxItem,
    AlertInboxStatus,
    AlertInboxSummary,
    AlertSeverity,
)
from trd_bot.api.dependencies import get_alert_inbox_repository
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.db import SqlAlchemyAlertInboxRepository

router = APIRouter(prefix="/alerts", tags=["Alert Center"])

AlertInboxRepositoryDependency = Annotated[
    SqlAlchemyAlertInboxRepository,
    Depends(get_alert_inbox_repository),
]


class AlertCatalogParams(PaginationParams):
    status: AlertInboxStatus | None = None
    severity: AlertSeverity | None = None


class AlertActionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    acted_by: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")

    @field_validator("acted_by")
    @classmethod
    def normalize_actor(cls, value: str) -> str:
        return value.strip()


class AlertSnoozeRequest(AlertActionRequest):
    duration_seconds: int = Field(ge=300, le=86_400)


CatalogQuery = Annotated[AlertCatalogParams, Query()]


def _now() -> datetime:
    return datetime.now(UTC)


def _get_or_404(
    repository: SqlAlchemyAlertInboxRepository,
    alert_id: str,
    *,
    evaluated_at: datetime,
) -> AlertInboxItem:
    item = repository.get(alert_id, evaluated_at=evaluated_at)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="alert not found",
        )
    return item


def _raise_conflict(error: AlertActionConflictError) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": error.code, "message": error.message},
    ) from error


@router.get("", response_model=Page[AlertInboxItem])
def list_alerts(
    repository: AlertInboxRepositoryDependency,
    params: CatalogQuery,
) -> Page[AlertInboxItem]:
    evaluated_at = _now()
    items, total = repository.list_page(
        limit=params.limit,
        offset=params.offset,
        status=params.status,
        severity=params.severity,
        evaluated_at=evaluated_at,
    )
    return build_page(items, total=total, pagination=params)


@router.get("/summary", response_model=AlertInboxSummary)
def get_alert_summary(repository: AlertInboxRepositoryDependency) -> AlertInboxSummary:
    return repository.summary(evaluated_at=_now())


@router.get("/{alert_id}", response_model=AlertInboxItem)
def get_alert(
    alert_id: str,
    repository: AlertInboxRepositoryDependency,
) -> AlertInboxItem:
    return _get_or_404(repository, alert_id, evaluated_at=_now())


@router.post("/{alert_id}/acknowledge", response_model=AlertInboxItem)
def acknowledge_alert(
    alert_id: str,
    request: AlertActionRequest,
    repository: AlertInboxRepositoryDependency,
) -> AlertInboxItem:
    occurred_at = _now()
    try:
        item, _ = repository.acknowledge(
            alert_id,
            acted_by=request.acted_by,
            occurred_at=occurred_at,
        )
    except AlertActionConflictError as error:
        _raise_conflict(error)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")
    return item


@router.post("/{alert_id}/snooze", response_model=AlertInboxItem)
def snooze_alert(
    alert_id: str,
    request: AlertSnoozeRequest,
    repository: AlertInboxRepositoryDependency,
) -> AlertInboxItem:
    occurred_at = _now()
    try:
        item, _ = repository.snooze(
            alert_id,
            acted_by=request.acted_by,
            occurred_at=occurred_at,
            duration_seconds=request.duration_seconds,
        )
    except AlertActionConflictError as error:
        _raise_conflict(error)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")
    return item
