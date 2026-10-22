from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrategyParameterKind(StrEnum):
    """Supported scalar parameter kinds exposed by the research catalog."""

    INTEGER = "integer"
    DECIMAL = "decimal"


class StrategyLifecycleStatus(StrEnum):
    """Lifecycle state of one immutable strategy version."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"


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
    lifecycle_status: StrategyLifecycleStatus = StrategyLifecycleStatus.ACTIVE
    supersedes_version: str | None = Field(default=None, min_length=1, max_length=50)
    behavior_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_version_contract(self) -> Self:
        parameter_names = [parameter.name for parameter in self.parameters]
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("strategy parameter names must be unique")
        if self.supersedes_version == self.version:
            raise ValueError("strategy version cannot supersede itself")
        return self
