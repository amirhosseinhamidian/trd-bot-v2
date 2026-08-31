from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.market_data.providers import (
    BinancePublicMarketDataProvider,
    MarketDataProvider,
    MarketDataProviderError,
    MarketDataProviderMetadata,
)


class MarketDataConnectionState(StrEnum):
    """Administrative state of one configured read-only market-data connection."""

    DISABLED = "disabled"
    ENABLED = "enabled"


class MarketDataConnectionHealth(StrEnum):
    """Most recent provider health-check outcome."""

    UNTESTED = "untested"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class MarketDataProviderUnavailableError(ValueError):
    """Raised when a configured provider cannot be created safely."""


class MarketDataConnectionNotFoundError(LookupError):
    """Raised when a requested connection does not exist."""


class MarketDataConnectionStateError(ValueError):
    """Raised when a requested lifecycle transition is not allowed."""


class MarketDataConnection(BaseModel):
    """Persistent configuration and health state for one read-only data connection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connection_id: str = Field(min_length=1, max_length=100)
    provider_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)
    state: MarketDataConnectionState = MarketDataConnectionState.DISABLED
    health_status: MarketDataConnectionHealth = MarketDataConnectionHealth.UNTESTED
    created_at: datetime
    updated_at: datetime
    last_tested_at: datetime | None = None
    last_error: str | None = Field(default=None, max_length=500)

    @field_validator("connection_id", "provider_id", "display_name")
    @classmethod
    def normalize_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("connection text fields cannot be empty")
        return normalized

    @field_validator("created_at", "updated_at", "last_tested_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("connection timestamps must include timezone information")
        return value.astimezone(UTC)

    @field_validator("last_error")
    @classmethod
    def normalize_last_error(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("last error cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("connection update time cannot precede creation time")

        if self.last_tested_at is not None:
            if self.last_tested_at < self.created_at:
                raise ValueError("connection test time cannot precede creation time")
            if self.last_tested_at > self.updated_at:
                raise ValueError("connection test time cannot exceed update time")

        if self.health_status is MarketDataConnectionHealth.UNTESTED:
            if self.last_tested_at is not None or self.last_error is not None:
                raise ValueError("untested connection cannot contain health-check details")

        elif self.health_status is MarketDataConnectionHealth.HEALTHY:
            if self.last_tested_at is None or self.last_error is not None:
                raise ValueError("healthy connection requires a successful test timestamp")

        else:
            if self.last_tested_at is None or self.last_error is None:
                raise ValueError("unhealthy connection requires failed test details")

        if (
            self.state is MarketDataConnectionState.ENABLED
            and self.health_status is not MarketDataConnectionHealth.HEALTHY
        ):
            raise ValueError("enabled connection must have a healthy test result")

        return self


class MarketDataConnectionRepository(Protocol):
    """Persistence contract for configured market-data connections."""

    def save(self, connection: MarketDataConnection) -> MarketDataConnection: ...

    def get(self, connection_id: str) -> MarketDataConnection | None: ...

    def count(self) -> int: ...

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[MarketDataConnection, ...]: ...


class InMemoryMarketDataConnectionRepository:
    """Isolated-test repository with production-equivalent ordering semantics."""

    def __init__(self) -> None:
        self._items: dict[str, MarketDataConnection] = {}

    def save(self, connection: MarketDataConnection) -> MarketDataConnection:
        self._items[connection.connection_id] = connection
        return connection

    def get(self, connection_id: str) -> MarketDataConnection | None:
        return self._items.get(connection_id)

    def count(self) -> int:
        return len(self._items)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[MarketDataConnection, ...]:
        _validate_pagination(limit=limit, offset=offset)
        ordered = sorted(
            self._items.values(),
            key=lambda item: (item.created_at, item.connection_id),
            reverse=True,
        )
        return tuple(ordered[offset : offset + limit])


MarketDataProviderFactory = Callable[[], MarketDataProvider]


class MarketDataProviderCatalog:
    """Explicit allowlist of market-data provider implementations exposed to users."""

    def __init__(
        self,
        factories: Mapping[str, MarketDataProviderFactory] | None = None,
    ) -> None:
        configured_factories: dict[str, MarketDataProviderFactory] = dict(
            factories
            if factories is not None
            else {
                "binance-public": BinancePublicMarketDataProvider,
            }
        )
        if not configured_factories:
            raise ValueError("provider catalog cannot be empty")

        metadata_by_id: dict[str, MarketDataProviderMetadata] = {}
        for provider_id, factory in configured_factories.items():
            provider = factory()
            metadata = provider.metadata
            if metadata.provider_id != provider_id:
                raise ValueError("provider factory identity does not match catalog key")
            metadata_by_id[provider_id] = metadata

        self._factories = configured_factories
        self._metadata_by_id = metadata_by_id

    def list_metadata(self) -> tuple[MarketDataProviderMetadata, ...]:
        return tuple(
            self._metadata_by_id[provider_id]
            for provider_id in sorted(self._metadata_by_id)
        )

    def get_metadata(self, provider_id: str) -> MarketDataProviderMetadata | None:
        return self._metadata_by_id.get(provider_id)

    def create(self, provider_id: str) -> MarketDataProvider:
        factory = self._factories.get(provider_id)
        if factory is None:
            raise MarketDataProviderUnavailableError("market-data provider is not available")
        return factory()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _validate_pagination(*, limit: int, offset: int) -> None:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if offset < 0:
        raise ValueError("offset cannot be negative")


class MarketDataConnectionManager:
    """Lifecycle service for read-only provider configuration and health checks."""

    def __init__(
        self,
        *,
        repository: MarketDataConnectionRepository,
        providers: MarketDataProviderCatalog,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._repository = repository
        self._providers = providers
        self._clock = clock

    def create(
        self,
        *,
        provider_id: str,
        display_name: str,
    ) -> MarketDataConnection:
        metadata = self._providers.get_metadata(provider_id)
        if metadata is None:
            raise MarketDataProviderUnavailableError("market-data provider is not available")
        if metadata.requires_credentials:
            raise MarketDataProviderUnavailableError(
                "credentialed market-data providers are not supported yet"
            )

        now = self._now()
        connection = MarketDataConnection(
            connection_id=f"market-data-connection-{uuid4().hex}",
            provider_id=provider_id,
            display_name=display_name,
            created_at=now,
            updated_at=now,
        )
        return self._repository.save(connection)

    def get(self, connection_id: str) -> MarketDataConnection:
        connection = self._repository.get(connection_id)
        if connection is None:
            raise MarketDataConnectionNotFoundError("market-data connection not found")
        return connection

    async def test_connection(self, connection_id: str) -> MarketDataConnection:
        connection = self.get(connection_id)
        tested_at = self._now()

        try:
            provider = self._providers.create(connection.provider_id)
            await provider.test_connection()
        except (MarketDataProviderError, MarketDataProviderUnavailableError) as exc:
            safe_error = str(exc).strip() or "market-data provider health check failed"
            updated = connection.model_copy(
                update={
                    "state": MarketDataConnectionState.DISABLED,
                    "health_status": MarketDataConnectionHealth.UNHEALTHY,
                    "updated_at": tested_at,
                    "last_tested_at": tested_at,
                    "last_error": safe_error[:500],
                }
            )
        else:
            updated = connection.model_copy(
                update={
                    "health_status": MarketDataConnectionHealth.HEALTHY,
                    "updated_at": tested_at,
                    "last_tested_at": tested_at,
                    "last_error": None,
                }
            )

        validated = MarketDataConnection.model_validate(updated.model_dump())
        return self._repository.save(validated)

    def enable(self, connection_id: str) -> MarketDataConnection:
        connection = self.get(connection_id)
        if self._providers.get_metadata(connection.provider_id) is None:
            raise MarketDataConnectionStateError(
                "connection provider implementation is not available"
            )
        if connection.health_status is not MarketDataConnectionHealth.HEALTHY:
            raise MarketDataConnectionStateError(
                "connection must pass a health check before it can be enabled"
            )

        if connection.state is MarketDataConnectionState.ENABLED:
            return connection

        updated = connection.model_copy(
            update={
                "state": MarketDataConnectionState.ENABLED,
                "updated_at": self._now(),
            }
        )
        validated = MarketDataConnection.model_validate(updated.model_dump())
        return self._repository.save(validated)

    def disable(self, connection_id: str) -> MarketDataConnection:
        connection = self.get(connection_id)
        if connection.state is MarketDataConnectionState.DISABLED:
            return connection

        updated = connection.model_copy(
            update={
                "state": MarketDataConnectionState.DISABLED,
                "updated_at": self._now(),
            }
        )
        validated = MarketDataConnection.model_validate(updated.model_dump())
        return self._repository.save(validated)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("connection clock must return timezone-aware timestamps")
        return value.astimezone(UTC)
