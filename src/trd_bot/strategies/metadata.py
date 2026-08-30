from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrategyParameterKind(StrEnum):
    """Supported scalar parameter kinds exposed by the research catalog."""

    INTEGER = "integer"
    DECIMAL = "decimal"


class StrategyParameterMetadata(BaseModel):
    """Read-only metadata for one versioned strategy parameter."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=100)
    kind: StrategyParameterKind
    default_value: str = Field(min_length=1, max_length=100)
    minimum: str | None = None
    maximum: str | None = None
    minimum_exclusive: bool = False
    maximum_exclusive: bool = False


class StrategyMetadata(BaseModel):
    """Read-only metadata for one historical research strategy."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    parameters: tuple[StrategyParameterMetadata, ...]
