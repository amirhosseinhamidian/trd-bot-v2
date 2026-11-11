from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from trd_bot.integration.nexora.snapshots import SourceReference

EXPORT_REQUEST_SCHEMA_VERSION = "nexora-export-request-v1"
EXPORT_STATUS_SCHEMA_VERSION = "nexora-export-status-v1"
EXPORT_MANIFEST_SCHEMA_VERSION = "nexora-export-manifest-v1"


class ExportProtocolError(ValueError):
    """Raised when an export request violates the frozen boundary."""


class ExportIdempotencyConflictError(ExportProtocolError):
    """Raised when an idempotency key is reused for a different request."""


class ExportNotFoundError(ExportProtocolError):
    """Raised when an export ID is unknown."""


class ExportNotCompleteError(ExportProtocolError):
    """Raised when a caller requests a manifest before atomic completion."""


class ExportResourceType(StrEnum):
    MARKET_CONTEXT = "market_context"
    DECISION_EVALUATION = "decision_evaluation"
    CANDIDATE = "candidate"
    RISK_GATE = "risk_gate"
    PORTFOLIO_INTELLIGENCE = "portfolio_intelligence"
    ALERT = "alert"
    ALERT_OUTCOME = "alert_outcome"
    PAPER_SHADOW_PORTFOLIO = "paper_shadow_portfolio"
    PAPER_SHADOW_POSITION = "paper_shadow_position"
    SIMULATION_OUTCOME = "simulation_outcome"


ExportFormat = Literal["json", "jsonl", "csv", "parquet", "zip_bundle"]


class ExportContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_SECRET_KEY = re.compile(
    r"(^|[_-])(authorization|token|secret|password|passwd|api[_-]?key|credential|cookie)([_-]|$)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(r"^(bearer\s+|-----BEGIN [A-Z ]*PRIVATE KEY-----)", re.IGNORECASE)


def contains_secret(value: JsonValue, *, key: str = "") -> bool:
    """Fail closed when request filters attempt to carry credentials or tokens."""

    if key and _SECRET_KEY.search(key):
        return True
    if isinstance(value, dict):
        return any(contains_secret(item, key=name) for name, item in value.items())
    if isinstance(value, list):
        return any(contains_secret(item, key=key) for item in value)
    return isinstance(value, str) and bool(_SECRET_VALUE.search(value.strip()))


class ExportRequest(ExportContractModel):
    schema_version: Literal["nexora-export-request-v1"] = "nexora-export-request-v1"
    mode: Literal["full", "incremental", "selected"]
    formats: tuple[ExportFormat, ...] = Field(min_length=1)
    profile: Literal["private", "ai_safe"]
    scope: tuple[ExportResourceType, ...] = Field(min_length=1)
    filters: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if len(set(self.formats)) != len(self.formats):
            raise ValueError("export formats must be unique")
        if len(set(self.scope)) != len(self.scope):
            raise ValueError("export scope must be unique")
        if contains_secret(self.filters):
            raise ValueError("export filters cannot contain credentials or secrets")
        supported_filters = {
            "base_currency",
            "from",
            "portfolio_mode",
            "resource_ids",
            "through",
        }
        unknown = sorted(set(self.filters) - supported_filters)
        if unknown:
            raise ValueError(f"unsupported export filters: {', '.join(unknown)}")
        base_currency = self.filters.get("base_currency", "USDT")
        if (
            not isinstance(base_currency, str)
            or re.fullmatch(r"[A-Z0-9]{2,12}", base_currency) is None
        ):
            raise ValueError("base_currency must be an uppercase currency code")
        portfolio_mode = self.filters.get("portfolio_mode")
        if portfolio_mode is not None and portfolio_mode not in {"paper", "shadow"}:
            raise ValueError("portfolio_mode must be paper or shadow")
        resource_ids = self.filters.get("resource_ids")
        if resource_ids is not None and (
            not isinstance(resource_ids, list)
            or not resource_ids
            or any(not isinstance(item, str) or not item for item in resource_ids)
        ):
            raise ValueError("resource_ids must be a non-empty string array")
        for field in ("from", "through"):
            timestamp = self.filters.get(field)
            if timestamp is None:
                continue
            if not isinstance(timestamp, str):
                raise ValueError(f"{field} must be an ISO-8601 UTC timestamp")
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError(f"{field} must be an ISO-8601 UTC timestamp") from error
            if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
                raise ValueError(f"{field} must be an ISO-8601 UTC timestamp")
        if self.mode == "incremental" and "from" not in self.filters:
            raise ValueError("incremental export requires a from filter")
        if self.mode == "selected" and resource_ids is None:
            raise ValueError("selected export requires resource_ids")
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def checksum(self) -> str:
        return f"sha256:{hashlib.sha256(self.canonical_json().encode()).hexdigest()}"


class ExportStatus(ExportContractModel):
    schema_version: Literal["nexora-export-status-v1"] = "nexora-export-status-v1"
    export_id: str = Field(pattern=r"^exp_[A-Za-z0-9_-]{16,64}$")
    status: Literal["accepted", "running", "complete", "failed"]
    requested_at: datetime
    completed_at: datetime | None = None

    @field_validator("requested_at", "completed_at")
    @classmethod
    def require_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("export timestamps must be UTC")
        return value.astimezone(UTC)


class CurrencyUnitContext(ExportContractModel):
    base_currency: str = Field(pattern=r"^[A-Z0-9]{2,12}$")
    quantity_units_explicit: Literal[True] = True


class ExportFile(ExportContractModel):
    path: str = Field(min_length=1, max_length=240)
    media_type: str = Field(min_length=1, max_length=120)
    row_count: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = Field(min_length=1, max_length=120)


class ExportManifest(ExportContractModel):
    schema_version: Literal["nexora-export-manifest-v1"] = "nexora-export-manifest-v1"
    export_id: str = Field(pattern=r"^exp_[A-Za-z0-9_-]{16,64}$")
    generated_at: datetime
    mode: Literal["full", "incremental", "selected"]
    profile: Literal["private", "ai_safe"]
    source_versions: dict[str, str] = Field(min_length=1)
    scope: tuple[str, ...] = Field(min_length=1)
    filters: dict[str, JsonValue]
    timezone: Literal["UTC"] = "UTC"
    currency_unit_context: CurrencyUnitContext
    lineage_references: tuple[SourceReference, ...]
    files: tuple[ExportFile, ...] = Field(min_length=1)
    redaction_profile: str = Field(min_length=1)
    completion_status: Literal["complete"] = "complete"

    @field_validator("generated_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("generated_at must be UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if len(set(self.scope)) != len(self.scope):
            raise ValueError("manifest scope must be unique")
        paths = [entry.path for entry in self.files]
        if len(set(paths)) != len(paths):
            raise ValueError("manifest file paths must be unique")
        return self


class NexoraExportJobPayload(ExportContractModel):
    export_id: str = Field(pattern=r"^exp_[A-Za-z0-9_-]{16,64}$")
    provider_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


def export_id_for(idempotency_key: str) -> str:
    return f"exp_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]}"
