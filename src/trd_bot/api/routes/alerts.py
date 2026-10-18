from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from trd_bot.alerts import (
    AlertActionConflictError,
    AlertExpirySummary,
    AlertExpirySweepResult,
    AlertInboxItem,
    AlertInboxStatus,
    AlertInboxSummary,
    AlertPublicationPolicy,
    AlertSeverity,
    AlertSimulationMode,
    AlertSimulationStartResult,
    AlertSimulationStatus,
    AlertSimulationSummary,
    AlertSimulationView,
)
from trd_bot.api.dependencies import (
    get_alert_inbox_repository,
    get_alert_publication_repository,
    get_alert_simulation_repository,
)
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.db import (
    AlertSimulationConflictError,
    SqlAlchemyAlertInboxRepository,
    SqlAlchemyAlertPublicationRepository,
    SqlAlchemyAlertSimulationRepository,
)

router = APIRouter(prefix="/alerts", tags=["Alert Center"])

AlertInboxRepositoryDependency = Annotated[
    SqlAlchemyAlertInboxRepository,
    Depends(get_alert_inbox_repository),
]
AlertPublicationRepositoryDependency = Annotated[
    SqlAlchemyAlertPublicationRepository,
    Depends(get_alert_publication_repository),
]
AlertSimulationRepositoryDependency = Annotated[
    SqlAlchemyAlertSimulationRepository,
    Depends(get_alert_simulation_repository),
]


class AlertCatalogParams(PaginationParams):
    status: AlertInboxStatus | None = None
    severity: AlertSeverity | None = None


class AlertSimulationCatalogParams(PaginationParams):
    alert_id: str | None = Field(default=None, pattern=r"^alert-[a-f0-9]{16}$")
    mode: AlertSimulationMode | None = None
    status: AlertSimulationStatus | None = None


class AlertActionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    acted_by: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")

    @field_validator("acted_by")
    @classmethod
    def normalize_actor(cls, value: str) -> str:
        return value.strip()


class AlertSnoozeRequest(AlertActionRequest):
    duration_seconds: int = Field(ge=300, le=86_400)


class AlertPublicationPolicyRequest(AlertActionRequest):
    quiet_hours_enabled: bool
    quiet_hours_start_minute: int = Field(ge=0, le=1439)
    quiet_hours_end_minute: int = Field(ge=0, le=1439)
    timezone_name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_+./-]+$",
    )
    critical_bypass_quiet_hours: bool = True


class AlertExpirySweepRequest(AlertActionRequest):
    limit: int = Field(default=100, ge=1, le=1000)


class AlertSimulationStartRequest(AlertActionRequest):
    mode: AlertSimulationMode
    horizon_seconds: int = Field(ge=900, le=2_592_000)


CatalogQuery = Annotated[AlertCatalogParams, Query()]
SimulationCatalogQuery = Annotated[AlertSimulationCatalogParams, Query()]


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


@router.get("/publication-policy", response_model=AlertPublicationPolicy)
def get_publication_policy(
    repository: AlertPublicationRepositoryDependency,
) -> AlertPublicationPolicy:
    return repository.get_policy()


@router.post("/publication-policy", response_model=AlertPublicationPolicy)
def update_publication_policy(
    request: AlertPublicationPolicyRequest,
    repository: AlertPublicationRepositoryDependency,
) -> AlertPublicationPolicy:
    return repository.update_policy(
        quiet_hours_enabled=request.quiet_hours_enabled,
        quiet_hours_start_minute=request.quiet_hours_start_minute,
        quiet_hours_end_minute=request.quiet_hours_end_minute,
        timezone_name=request.timezone_name,
        critical_bypass_quiet_hours=request.critical_bypass_quiet_hours,
        updated_by=request.acted_by,
        updated_at=_now(),
    )


@router.get("/expiry", response_model=AlertExpirySummary)
def get_expiry_summary(
    repository: AlertPublicationRepositoryDependency,
) -> AlertExpirySummary:
    return repository.expiry_summary(evaluated_at=_now())


@router.post("/expiry/sweep", response_model=AlertExpirySweepResult)
def sweep_expired_alerts(
    request: AlertExpirySweepRequest,
    repository: AlertPublicationRepositoryDependency,
) -> AlertExpirySweepResult:
    return repository.sweep_expired(
        evaluated_at=_now(),
        recorded_by=request.acted_by,
        limit=request.limit,
    )


@router.get("/simulations", response_model=Page[AlertSimulationView])
def list_alert_simulations(
    repository: AlertSimulationRepositoryDependency,
    params: SimulationCatalogQuery,
) -> Page[AlertSimulationView]:
    evaluated_at = _now()
    items, total = repository.list_page(
        limit=params.limit,
        offset=params.offset,
        alert_id=params.alert_id,
        mode=params.mode,
        status=params.status,
        evaluated_at=evaluated_at,
    )
    return build_page(items, total=total, pagination=params)


@router.get("/simulations/summary", response_model=AlertSimulationSummary)
def get_alert_simulation_summary(
    repository: AlertSimulationRepositoryDependency,
) -> AlertSimulationSummary:
    return repository.summary(evaluated_at=_now())


@router.get("/simulations/{simulation_id}", response_model=AlertSimulationView)
def get_alert_simulation(
    simulation_id: str,
    repository: AlertSimulationRepositoryDependency,
) -> AlertSimulationView:
    view = repository.get(simulation_id, evaluated_at=_now())
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="alert simulation not found",
        )
    return view


@router.post("/{alert_id}/simulations", response_model=AlertSimulationStartResult)
def start_alert_simulation(
    alert_id: str,
    request: AlertSimulationStartRequest,
    repository: AlertSimulationRepositoryDependency,
) -> AlertSimulationStartResult:
    try:
        result = repository.start(
            alert_id=alert_id,
            mode=request.mode,
            horizon_seconds=request.horizon_seconds,
            started_by=request.acted_by,
            started_at=_now(),
        )
    except AlertSimulationConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "message": error.message},
        ) from error
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")
    view, created = result
    return AlertSimulationStartResult(created=created, view=view)


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
