from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Final
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from trd_bot.api.dependencies import DatabaseSessionDependency
from trd_bot.core.config import get_settings
from trd_bot.db.nexora_decision_reviews import (
    DecisionReviewError,
    DecisionReviewIdempotencyConflictError,
    DecisionReviewSourceEvidenceError,
    SqlAlchemyNexoraDecisionReviewStore,
)
from trd_bot.db.nexora_events import SqlAlchemyNexoraEventStore
from trd_bot.db.nexora_exports import SqlAlchemyNexoraExportStore
from trd_bot.db.nexora_snapshot_scans import SqlAlchemyNexoraSnapshotScanStore
from trd_bot.integration.nexora.alert_snapshots import (
    ALERT_SNAPSHOT_RESOURCE_TYPES,
    AlertSnapshotResourceReader,
)
from trd_bot.integration.nexora.auth import (
    ServiceTokenConfigurationError,
    bearer_token_matches,
    load_service_token,
)
from trd_bot.integration.nexora.contracts import (
    CAPABILITIES_SCHEMA_VERSION,
    COMMANDS,
    CONTRACT_VERSION,
    EVENT_ENVELOPE_VERSION,
    EXPORT_MANIFEST_VERSION,
    SOURCE_REFERENCE_VERSION,
    CapabilitiesResponse,
    IntegrationErrorCode,
    IntegrationErrorDetail,
    IntegrationErrorEnvelope,
)
from trd_bot.integration.nexora.decision_reviews import CommandReceipt, DecisionReviewCommand
from trd_bot.integration.nexora.decision_snapshots import (
    DECISION_SNAPSHOT_RESOURCE_TYPES,
    DecisionSnapshotResourceReader,
)
from trd_bot.integration.nexora.events import (
    EventCursorConflictError,
    EventCursorExpiredError,
    EventCursorNotFoundError,
    EventFeedError,
    ProviderEventEnvelope,
    ProviderEventPage,
    to_provider_event,
    to_provider_event_page,
)
from trd_bot.integration.nexora.exports import (
    ExportIdempotencyConflictError,
    ExportManifest,
    ExportNotCompleteError,
    ExportNotFoundError,
    ExportRequest,
    ExportStatus,
)
from trd_bot.integration.nexora.portfolio_snapshots import (
    PORTFOLIO_SNAPSHOT_RESOURCE_TYPES,
    PortfolioSnapshotResourceReader,
)
from trd_bot.integration.nexora.resync import resync_required_details
from trd_bot.integration.nexora.snapshots import (
    SnapshotCursorConflictError,
    SnapshotCursorExpiredError,
    SnapshotCursorNotFoundError,
    SnapshotPage,
    SnapshotProtocolError,
    SnapshotResourceReader,
    StableSnapshotPager,
)

CAPABILITIES_CACHE_TTL_SECONDS: Final = 300
MAXIMUM_CORRELATION_ID_LENGTH: Final = 36

router = APIRouter(tags=["nexora-integration"])
SNAPSHOT_RESOURCE_TYPES: Final = (
    *PORTFOLIO_SNAPSHOT_RESOURCE_TYPES,
    *DECISION_SNAPSHOT_RESOURCE_TYPES,
    *ALERT_SNAPSHOT_RESOURCE_TYPES,
)


@dataclass(frozen=True, slots=True)
class _AuthorizedRequest:
    correlation_id: UUID
    correlation_header: str
    provider_version: str


def _response_headers(correlation_id: str, provider_version: str) -> dict[str, str]:
    return {
        "X-Contract-Version": CONTRACT_VERSION,
        "X-Correlation-ID": correlation_id,
        "X-TRD-Bot-Version": provider_version,
    }


def _error_response(
    *,
    status_code: int,
    correlation_id: UUID,
    provider_version: str,
    code: IntegrationErrorCode,
    message: str,
    retryable: bool,
    details: dict[str, Any] | None = None,
    authenticate: bool = False,
) -> JSONResponse:
    envelope = IntegrationErrorEnvelope(
        schema_version="nexora-integration-error-v1",
        correlation_id=correlation_id,
        occurred_at=datetime.now(UTC),
        error=IntegrationErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
            details={} if details is None else details,
        ),
    )
    headers = _response_headers(str(correlation_id), provider_version)
    if authenticate:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
        headers=headers,
    )


def _request_correlation_id(request: Request) -> tuple[UUID, str] | None:
    raw_value = request.headers.get("X-Correlation-ID")
    if raw_value is None or len(raw_value) > MAXIMUM_CORRELATION_ID_LENGTH:
        return None
    try:
        parsed = UUID(raw_value)
    except ValueError:
        return None
    if str(parsed) != raw_value.lower():
        return None
    return parsed, raw_value


def _accepts_json(request: Request) -> bool:
    accepted = request.headers.get("Accept")
    if accepted is None:
        return False
    media_types = {item.split(";", 1)[0].strip().lower() for item in accepted.split(",")}
    return "application/json" in media_types or "*/*" in media_types


def _has_json_content_type(request: Request) -> bool:
    content_type = request.headers.get("Content-Type")
    if content_type is None:
        return False
    return content_type.split(";", 1)[0].strip().lower() == "application/json"


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _transport_allowed(request: Request, environment: str) -> bool:
    if request.url.scheme == "https":
        return True
    return (
        environment in {"development", "test"}
        and request.url.scheme == "http"
        and _is_loopback_host(request.url.hostname)
    )


def _authorize_request(request: Request) -> _AuthorizedRequest | JSONResponse:
    settings = get_settings()
    correlation = _request_correlation_id(request)
    if correlation is None:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            correlation_id=uuid4(),
            provider_version=settings.app_version,
            code="INVALID_REQUEST",
            message="a canonical UUID X-Correlation-ID header is required",
            retryable=False,
        )
    correlation_id, correlation_header = correlation
    if not _accepts_json(request):
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            correlation_id=correlation_id,
            provider_version=settings.app_version,
            code="INVALID_REQUEST",
            message="Accept must allow application/json",
            retryable=False,
        )
    if not _transport_allowed(request, settings.environment):
        return _error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            correlation_id=correlation_id,
            provider_version=settings.app_version,
            code="FORBIDDEN",
            message="the integration transport is not permitted",
            retryable=False,
        )

    authorization = request.headers.get("Authorization")
    if authorization is None or not authorization.startswith("Bearer "):
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            correlation_id=correlation_id,
            provider_version=settings.app_version,
            code="UNAUTHORIZED",
            message="service authentication failed",
            retryable=False,
            authenticate=True,
        )
    try:
        expected_token = load_service_token(settings.nexora_service_token_file)
    except ServiceTokenConfigurationError:
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            correlation_id=correlation_id,
            provider_version=settings.app_version,
            code="SOURCE_UNAVAILABLE",
            message="service authentication is unavailable",
            retryable=False,
        )
    if not bearer_token_matches(authorization, expected_token):
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            correlation_id=correlation_id,
            provider_version=settings.app_version,
            code="UNAUTHORIZED",
            message="service authentication failed",
            retryable=False,
            authenticate=True,
        )
    return _AuthorizedRequest(
        correlation_id=correlation_id,
        correlation_header=correlation_header,
        provider_version=settings.app_version,
    )


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    responses={
        400: {"model": IntegrationErrorEnvelope},
        401: {"model": IntegrationErrorEnvelope},
        403: {"model": IntegrationErrorEnvelope},
        503: {"model": IntegrationErrorEnvelope},
    },
)
def get_capabilities(request: Request) -> Response:
    """Authenticate Nexora and return the frozen integration capability matrix."""

    authorized = _authorize_request(request)
    if isinstance(authorized, JSONResponse):
        return authorized

    capabilities = CapabilitiesResponse(
        schema_version=CAPABILITIES_SCHEMA_VERSION,
        provider="trd_bot",
        provider_version=authorized.provider_version,
        contract_versions=(CONTRACT_VERSION,),
        event_envelopes=(EVENT_ENVELOPE_VERSION,),
        export_manifests=(EXPORT_MANIFEST_VERSION,),
        source_references=(SOURCE_REFERENCE_VERSION,),
        commands=COMMANDS,
        generated_at=datetime.now(UTC),
    )
    headers = _response_headers(authorized.correlation_header, authorized.provider_version)
    headers["Cache-Control"] = f"private, max-age={CAPABILITIES_CACHE_TTL_SECONDS}"
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=capabilities.model_dump(mode="json"),
        headers=headers,
    )


@router.get(
    "/snapshots/{resource_type}",
    response_model=SnapshotPage,
    responses={
        400: {"model": IntegrationErrorEnvelope},
        401: {"model": IntegrationErrorEnvelope},
        403: {"model": IntegrationErrorEnvelope},
        409: {"model": IntegrationErrorEnvelope},
        410: {"model": IntegrationErrorEnvelope},
        503: {"model": IntegrationErrorEnvelope},
    },
)
def get_snapshot_page(
    resource_type: str,
    request: Request,
    session: DatabaseSessionDependency,
    cursor: str | None = None,
    limit: int | None = None,
) -> Response:
    """Return one authenticated stable page from an allowlisted snapshot resource."""

    authorized = _authorize_request(request)
    if isinstance(authorized, JSONResponse):
        return authorized
    if resource_type not in SNAPSHOT_RESOURCE_TYPES:
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="snapshot resource type is not available",
            retryable=False,
        )

    reader: SnapshotResourceReader
    if resource_type in PORTFOLIO_SNAPSHOT_RESOURCE_TYPES:
        reader = PortfolioSnapshotResourceReader(session)
    elif resource_type in DECISION_SNAPSHOT_RESOURCE_TYPES:
        reader = DecisionSnapshotResourceReader(session)
    else:
        reader = AlertSnapshotResourceReader(session)
    pager = StableSnapshotPager(
        reader=reader,
        store=SqlAlchemyNexoraSnapshotScanStore(session),
        source_version=authorized.provider_version,
    )
    try:
        page = pager.page(
            resource_type=resource_type,
            now=datetime.now(UTC),
            cursor=cursor,
            limit=limit,
        )
        session.commit()
    except SnapshotCursorExpiredError:
        session.rollback()
        return _error_response(
            status_code=status.HTTP_410_GONE,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="CURSOR_EXPIRED",
            message="snapshot cursor expired; full resync is required",
            retryable=False,
            details=resync_required_details("cursor_expired_response"),
        )
    except SnapshotCursorConflictError:
        session.rollback()
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="CURSOR_CONFLICT",
            message="snapshot cursor does not match this request",
            retryable=False,
        )
    except (SnapshotCursorNotFoundError, SnapshotProtocolError):
        session.rollback()
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="snapshot request is invalid",
            retryable=False,
        )
    except (SQLAlchemyError, ValueError):
        session.rollback()
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="SOURCE_UNAVAILABLE",
            message="snapshot source is unavailable",
            retryable=True,
        )

    headers = _response_headers(authorized.correlation_header, authorized.provider_version)
    headers["Cache-Control"] = "private, no-store"
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=page.model_dump(mode="json"),
        headers=headers,
    )


@router.get(
    "/events",
    response_model=ProviderEventPage,
    responses={
        400: {"model": IntegrationErrorEnvelope},
        401: {"model": IntegrationErrorEnvelope},
        403: {"model": IntegrationErrorEnvelope},
        409: {"model": IntegrationErrorEnvelope},
        410: {"model": IntegrationErrorEnvelope},
        503: {"model": IntegrationErrorEnvelope},
    },
)
def get_event_page(
    request: Request,
    session: DatabaseSessionDependency,
    cursor: str | None = None,
    limit: int | None = None,
) -> Response:
    """Replay one authenticated page from the durable at-least-once event feed."""

    authorized = _authorize_request(request)
    if isinstance(authorized, JSONResponse):
        return authorized
    try:
        page = SqlAlchemyNexoraEventStore(session).page(
            now=datetime.now(UTC), cursor=cursor, limit=limit
        )
        provider_page = to_provider_event_page(page, source_version=authorized.provider_version)
        session.commit()
    except EventCursorExpiredError:
        session.rollback()
        return _error_response(
            status_code=status.HTTP_410_GONE,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="CURSOR_EXPIRED",
            message="event cursor expired; full snapshot resync is required",
            retryable=False,
            details=resync_required_details("cursor_expired_response"),
        )
    except EventCursorConflictError:
        session.rollback()
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="CURSOR_CONFLICT",
            message="event cursor does not match this request",
            retryable=False,
        )
    except (EventCursorNotFoundError, EventFeedError):
        session.rollback()
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="event feed request is invalid",
            retryable=False,
        )
    except (SQLAlchemyError, ValueError):
        session.rollback()
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="SOURCE_UNAVAILABLE",
            message="event feed is unavailable",
            retryable=True,
        )
    headers = _response_headers(authorized.correlation_header, authorized.provider_version)
    headers["Cache-Control"] = "private, no-store"
    return JSONResponse(
        status_code=200,
        content=provider_page.model_dump(mode="json"),
        headers=headers,
    )


@router.get(
    "/events/{event_id}",
    response_model=ProviderEventEnvelope,
    responses={
        400: {"model": IntegrationErrorEnvelope},
        401: {"model": IntegrationErrorEnvelope},
        403: {"model": IntegrationErrorEnvelope},
        404: {"model": IntegrationErrorEnvelope},
        503: {"model": IntegrationErrorEnvelope},
    },
)
def get_event(
    event_id: str,
    request: Request,
    session: DatabaseSessionDependency,
) -> Response:
    """Return the exact envelope used by the feed for one event ID."""

    authorized = _authorize_request(request)
    if isinstance(authorized, JSONResponse):
        return authorized
    if len(event_id) != 68 or not event_id.startswith("evt_"):
        return _error_response(
            status_code=400,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="event ID is invalid",
            retryable=False,
        )
    try:
        event = SqlAlchemyNexoraEventStore(session).get(event_id)
        provider_event = (
            None
            if event is None
            else to_provider_event(event, source_version=authorized.provider_version)
        )
    except (SQLAlchemyError, ValueError):
        return _error_response(
            status_code=503,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="SOURCE_UNAVAILABLE",
            message="event lookup is unavailable",
            retryable=True,
        )
    if provider_event is None:
        return _error_response(
            status_code=404,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="event was not found",
            retryable=False,
        )
    headers = _response_headers(authorized.correlation_header, authorized.provider_version)
    headers["Cache-Control"] = "private, no-store"
    return JSONResponse(
        status_code=200,
        content=provider_event.model_dump(mode="json"),
        headers=headers,
    )


@router.post(
    "/commands/decision-reviews",
    response_model=CommandReceipt,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": IntegrationErrorEnvelope},
        401: {"model": IntegrationErrorEnvelope},
        403: {"model": IntegrationErrorEnvelope},
        409: {"model": IntegrationErrorEnvelope},
        412: {"model": IntegrationErrorEnvelope},
        422: {"model": IntegrationErrorEnvelope},
        503: {"model": IntegrationErrorEnvelope},
    },
)
def submit_decision_review(
    command: DecisionReviewCommand,
    request: Request,
    session: DatabaseSessionDependency,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=160),
    ],
) -> Response:
    """Durably accept idempotent Paper/Shadow feedback from the Nexora owner review."""

    authorized = _authorize_request(request)
    if isinstance(authorized, JSONResponse):
        return authorized
    if not _has_json_content_type(request):
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="Content-Type must be application/json",
            retryable=False,
        )
    try:
        receipt = SqlAlchemyNexoraDecisionReviewStore(session).submit(
            command=command,
            idempotency_key=idempotency_key,
            correlation_id=authorized.correlation_id,
            accepted_at=datetime.now(UTC),
            source_version=authorized.provider_version,
        )
        session.commit()
    except DecisionReviewIdempotencyConflictError:
        session.rollback()
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="IDEMPOTENCY_CONFLICT",
            message="Idempotency-Key belongs to a different decision review",
            retryable=False,
        )
    except DecisionReviewSourceEvidenceError:
        session.rollback()
        return _error_response(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="CHECKSUM_MISMATCH",
            message="decision review source evidence is missing, stale, or mismatched",
            retryable=False,
        )
    except DecisionReviewError:
        session.rollback()
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="decision review command is invalid",
            retryable=False,
        )
    except (SQLAlchemyError, ValueError):
        session.rollback()
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="SOURCE_UNAVAILABLE",
            message="decision review journal is unavailable",
            retryable=True,
        )
    headers = _response_headers(authorized.correlation_header, authorized.provider_version)
    headers["Cache-Control"] = "private, no-store"
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=receipt.model_dump(mode="json"),
        headers=headers,
    )


@router.post(
    "/exports",
    response_model=ExportStatus,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": IntegrationErrorEnvelope},
        401: {"model": IntegrationErrorEnvelope},
        403: {"model": IntegrationErrorEnvelope},
        409: {"model": IntegrationErrorEnvelope},
        422: {"model": IntegrationErrorEnvelope},
        503: {"model": IntegrationErrorEnvelope},
    },
)
def create_export(
    export_request: ExportRequest,
    request: Request,
    session: DatabaseSessionDependency,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=160),
    ],
) -> Response:
    """Atomically enqueue one private or AI-safe export."""

    authorized = _authorize_request(request)
    if isinstance(authorized, JSONResponse):
        return authorized
    if not _has_json_content_type(request):
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="Content-Type must be application/json",
            retryable=False,
        )
    try:
        export_status = SqlAlchemyNexoraExportStore(session).submit(
            request=export_request,
            idempotency_key=idempotency_key,
            provider_version=authorized.provider_version,
            requested_at=datetime.now(UTC),
        )
        session.commit()
    except ExportIdempotencyConflictError:
        session.rollback()
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="IDEMPOTENCY_CONFLICT",
            message="Idempotency-Key belongs to a different export request",
            retryable=False,
        )
    except (SQLAlchemyError, ValueError):
        session.rollback()
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="SOURCE_UNAVAILABLE",
            message="export queue is unavailable",
            retryable=True,
        )
    headers = _response_headers(authorized.correlation_header, authorized.provider_version)
    headers["Cache-Control"] = "private, no-store"
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=export_status.model_dump(mode="json"),
        headers=headers,
    )


@router.get(
    "/exports/{export_id}",
    response_model=ExportStatus,
    responses={
        400: {"model": IntegrationErrorEnvelope},
        401: {"model": IntegrationErrorEnvelope},
        403: {"model": IntegrationErrorEnvelope},
        404: {"model": IntegrationErrorEnvelope},
        503: {"model": IntegrationErrorEnvelope},
    },
)
def get_export_status(
    export_id: str,
    request: Request,
    session: DatabaseSessionDependency,
) -> Response:
    """Return the durable export lifecycle without exposing file contents."""

    authorized = _authorize_request(request)
    if isinstance(authorized, JSONResponse):
        return authorized
    try:
        export_status = SqlAlchemyNexoraExportStore(session).get_status(export_id)
    except ExportNotFoundError:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="export was not found",
            retryable=False,
        )
    except (SQLAlchemyError, ValueError):
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="SOURCE_UNAVAILABLE",
            message="export status is unavailable",
            retryable=True,
        )
    headers = _response_headers(authorized.correlation_header, authorized.provider_version)
    headers["Cache-Control"] = "private, no-store"
    return JSONResponse(
        status_code=200,
        content=export_status.model_dump(mode="json"),
        headers=headers,
    )


@router.get(
    "/exports/{export_id}/manifest",
    response_model=ExportManifest,
    responses={
        400: {"model": IntegrationErrorEnvelope},
        401: {"model": IntegrationErrorEnvelope},
        403: {"model": IntegrationErrorEnvelope},
        404: {"model": IntegrationErrorEnvelope},
        409: {"model": IntegrationErrorEnvelope},
        503: {"model": IntegrationErrorEnvelope},
    },
)
def get_export_manifest(
    export_id: str,
    request: Request,
    session: DatabaseSessionDependency,
) -> Response:
    """Expose a manifest only after every file is durably checksum-bound."""

    authorized = _authorize_request(request)
    if isinstance(authorized, JSONResponse):
        return authorized
    try:
        manifest = SqlAlchemyNexoraExportStore(session).get_manifest(export_id)
    except ExportNotCompleteError:
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="SOURCE_UNAVAILABLE",
            message="export manifest is not complete",
            retryable=True,
        )
    except ExportNotFoundError:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="INVALID_REQUEST",
            message="export was not found",
            retryable=False,
        )
    except (SQLAlchemyError, ValueError):
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            correlation_id=authorized.correlation_id,
            provider_version=authorized.provider_version,
            code="SOURCE_UNAVAILABLE",
            message="export manifest is unavailable",
            retryable=True,
        )
    headers = _response_headers(authorized.correlation_header, authorized.provider_version)
    headers["Cache-Control"] = "private, no-store"
    return JSONResponse(
        status_code=200,
        content=manifest.model_dump(mode="json"),
        headers=headers,
    )
