from typing import Annotated, NoReturn, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from trd_bot.api.dependencies import (
    get_market_data_connection_repository,
    get_market_data_provider_catalog,
)
from trd_bot.api.pagination import Page, PaginationParams, build_page
from trd_bot.domain.market_data import MarketType, Timeframe
from trd_bot.market_data import (
    MarketDataConnection,
    MarketDataConnectionManager,
    MarketDataConnectionNotFoundError,
    MarketDataConnectionRepository,
    MarketDataConnectionStateError,
    MarketDataProviderCatalog,
    MarketDataProviderMetadata,
    MarketDataProviderUnavailableError,
)

router = APIRouter(
    prefix="/market-data",
    tags=["Read-only market-data connections"],
)

ConnectionRepositoryDependency = Annotated[
    MarketDataConnectionRepository,
    Depends(get_market_data_connection_repository),
]
ProviderCatalogDependency = Annotated[
    MarketDataProviderCatalog,
    Depends(get_market_data_provider_catalog),
]
PaginationQuery = Annotated[
    PaginationParams,
    Query(),
]


class MarketDataProviderSummary(BaseModel):
    """Public capability summary for an allowlisted market-data provider."""

    model_config = ConfigDict(frozen=True)

    provider_id: str
    display_name: str
    requires_credentials: bool
    supported_market_types: tuple[MarketType, ...]
    supported_timeframes: tuple[Timeframe, ...]

    @classmethod
    def from_metadata(cls, metadata: MarketDataProviderMetadata) -> Self:
        return cls(
            provider_id=metadata.provider_id,
            display_name=metadata.display_name,
            requires_credentials=metadata.requires_credentials,
            supported_market_types=metadata.supported_market_types,
            supported_timeframes=metadata.supported_timeframes,
        )


class MarketDataConnectionCreateRequest(BaseModel):
    """Configuration for a new read-only market-data connection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("provider_id", "display_name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("connection fields cannot be empty")
        return normalized


def _manager(
    *,
    connections: MarketDataConnectionRepository,
    providers: MarketDataProviderCatalog,
) -> MarketDataConnectionManager:
    return MarketDataConnectionManager(
        repository=connections,
        providers=providers,
    )


def _raise_not_found(exc: MarketDataConnectionNotFoundError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    ) from exc


@router.get(
    "/providers",
    response_model=tuple[MarketDataProviderSummary, ...],
)
def list_market_data_providers(
    providers: ProviderCatalogDependency,
) -> tuple[MarketDataProviderSummary, ...]:
    """List provider implementations that this research server can configure."""

    return tuple(
        MarketDataProviderSummary.from_metadata(metadata) for metadata in providers.list_metadata()
    )


@router.post(
    "/connections",
    response_model=MarketDataConnection,
    status_code=status.HTTP_201_CREATED,
)
def create_market_data_connection(
    request: MarketDataConnectionCreateRequest,
    connections: ConnectionRepositoryDependency,
    providers: ProviderCatalogDependency,
) -> MarketDataConnection:
    """Create a disabled connection that must be tested before use."""

    try:
        return _manager(connections=connections, providers=providers).create(
            provider_id=request.provider_id,
            display_name=request.display_name,
        )
    except MarketDataProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/connections",
    response_model=Page[MarketDataConnection],
)
def list_market_data_connections(
    connections: ConnectionRepositoryDependency,
    pagination: PaginationQuery,
) -> Page[MarketDataConnection]:
    """List configured connections newest first."""

    items = connections.list_page(
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return build_page(
        items,
        total=connections.count(),
        pagination=pagination,
    )


@router.get(
    "/connections/{connection_id}",
    response_model=MarketDataConnection,
)
def get_market_data_connection(
    connection_id: str,
    connections: ConnectionRepositoryDependency,
    providers: ProviderCatalogDependency,
) -> MarketDataConnection:
    """Return one configured connection and its latest health state."""

    try:
        return _manager(connections=connections, providers=providers).get(connection_id)
    except MarketDataConnectionNotFoundError as exc:
        _raise_not_found(exc)


@router.post(
    "/connections/{connection_id}/test",
    response_model=MarketDataConnection,
)
async def test_market_data_connection(
    connection_id: str,
    connections: ConnectionRepositoryDependency,
    providers: ProviderCatalogDependency,
) -> MarketDataConnection:
    """Run one read-only provider health check and persist the result."""

    try:
        return await _manager(
            connections=connections,
            providers=providers,
        ).test_connection(connection_id)
    except MarketDataConnectionNotFoundError as exc:
        _raise_not_found(exc)


@router.post(
    "/connections/{connection_id}/enable",
    response_model=MarketDataConnection,
)
def enable_market_data_connection(
    connection_id: str,
    connections: ConnectionRepositoryDependency,
    providers: ProviderCatalogDependency,
) -> MarketDataConnection:
    """Enable a connection only after its latest health check succeeded."""

    try:
        return _manager(connections=connections, providers=providers).enable(connection_id)
    except MarketDataConnectionNotFoundError as exc:
        _raise_not_found(exc)
    except MarketDataConnectionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/connections/{connection_id}/disable",
    response_model=MarketDataConnection,
)
def disable_market_data_connection(
    connection_id: str,
    connections: ConnectionRepositoryDependency,
    providers: ProviderCatalogDependency,
) -> MarketDataConnection:
    """Disable a configured connection without deleting its audit state."""

    try:
        return _manager(connections=connections, providers=providers).disable(connection_id)
    except MarketDataConnectionNotFoundError as exc:
        _raise_not_found(exc)
