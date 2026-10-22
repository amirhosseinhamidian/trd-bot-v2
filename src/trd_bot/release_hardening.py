import hashlib
import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self

from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot import __version__
from trd_bot.db import DatabaseBase
from trd_bot.jobs import BACKGROUND_JOB_POLICIES
from trd_bot.main import create_app
from trd_bot.market_data import MarketDataProviderCatalog
from trd_bot.market_data.provider_probes import MARKET_DATA_PROBE_USER_AGENT
from trd_bot.market_data.providers import MARKET_DATA_PROVIDER_USER_AGENT

RELEASE_SCOPE = "crypto-spot-public-read-only-research-shadow-paper"
RELEASE_INVENTORY_SCHEMA_VERSION = "v0.3-release-inventory-v1"
V0_3_RELEASE_VERSION = "0.3.0"

PROHIBITED_LIVE_ROUTE_SEGMENTS = frozenset(
    {
        "brokerage",
        "deposit",
        "deposits",
        "exchange-account",
        "exchange-accounts",
        "live-order",
        "live-orders",
        "order",
        "orders",
        "trade",
        "trades",
        "trading",
        "wallet",
        "wallets",
        "withdraw",
        "withdrawal",
        "withdrawals",
    }
)
PROHIBITED_CREDENTIAL_FIELDS = frozenset(
    {
        "access_token",
        "api_key",
        "api_secret",
        "client_secret",
        "passphrase",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "withdrawal_address",
    }
)
_OPENAPI_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)
_ALLOWED_RELEASE_API_METHODS = frozenset({"GET", "POST"})


class ReleaseApiOperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: str = Field(pattern=r"^[A-Z]+$")
    path: str = Field(pattern=r"^/api/v1(?:/.*)?$")


class ReleaseProviderSurface(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    requires_credentials: bool
    market_types: tuple[str, ...] = Field(min_length=1)
    access_mode: str = Field(min_length=1)


class ReleaseJobSurface(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    max_attempts: int = Field(ge=1)
    payload_versions: tuple[int, ...] = Field(min_length=1)
    cancellation_mode: str = Field(min_length=1)


class ReleaseSurfaceInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["v0.3-release-inventory-v1"] = "v0.3-release-inventory-v1"
    product_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    scope: Literal["crypto-spot-public-read-only-research-shadow-paper"] = (
        "crypto-spot-public-read-only-research-shadow-paper"
    )
    version_sources: tuple[tuple[str, str], ...] = Field(min_length=1)
    api_operations: tuple[ReleaseApiOperation, ...] = Field(min_length=1)
    openapi_property_names: tuple[str, ...] = Field(min_length=1)
    frontend_page_files: tuple[str, ...] = Field(min_length=1)
    providers: tuple[ReleaseProviderSurface, ...] = Field(min_length=1)
    jobs: tuple[ReleaseJobSurface, ...] = Field(min_length=1)
    database_tables: tuple[str, ...] = Field(min_length=1)
    migration_revisions: tuple[str, ...] = Field(min_length=1)
    migration_heads: tuple[str, ...] = Field(min_length=1)
    network_user_agents: tuple[tuple[str, str], ...] = Field(min_length=1)
    deferred_capabilities: tuple[str, ...] = (
        "exchange-account-connectivity",
        "live-execution",
        "private-provider-credentials",
        "real-asset-portfolio-management",
        "wallet-and-fund-transfer",
    )

    @model_validator(mode="after")
    def validate_canonical_order(self) -> Self:
        ordered_string_fields = {
            "OpenAPI property names": self.openapi_property_names,
            "frontend pages": self.frontend_page_files,
            "providers": tuple(item.provider_id for item in self.providers),
            "jobs": tuple(item.kind for item in self.jobs),
            "database tables": self.database_tables,
            "migration revisions": self.migration_revisions,
            "migration heads": self.migration_heads,
            "deferred capabilities": self.deferred_capabilities,
        }
        for label, values in ordered_string_fields.items():
            if tuple(values) != tuple(sorted(values)) or len(values) != len(set(values)):
                raise ValueError(f"release inventory {label} must be sorted and unique")
        ordered_pair_fields = {
            "version sources": self.version_sources,
            "API operations": tuple((item.path, item.method) for item in self.api_operations),
            "network user agents": self.network_user_agents,
        }
        for label, pair_values in ordered_pair_fields.items():
            if tuple(pair_values) != tuple(sorted(pair_values)) or len(pair_values) != len(
                set(pair_values)
            ):
                raise ValueError(f"release inventory {label} must be sorted and unique")
        return self

    @property
    def definition_checksum(self) -> str:
        serialized = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @property
    def counts(self) -> dict[str, int]:
        return {
            "api_operations": len(self.api_operations),
            "database_tables": len(self.database_tables),
            "frontend_pages": len(self.frontend_page_files),
            "jobs": len(self.jobs),
            "migration_heads": len(self.migration_heads),
            "migration_revisions": len(self.migration_revisions),
            "providers": len(self.providers),
        }


class ReleaseHardeningReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    inventory: ReleaseSurfaceInventory
    failure_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        expected = evaluate_release_inventory(self.inventory)
        if self.failure_reasons != expected:
            raise ValueError("release hardening failure reasons are inconsistent")
        return self

    @property
    def passed(self) -> bool:
        return not self.failure_reasons


def _collect_property_names(value: object) -> set[str]:
    names: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key == "properties" and isinstance(nested, Mapping):
                names.update(str(name).casefold() for name in nested)
            names.update(_collect_property_names(nested))
    elif isinstance(value, list):
        for nested in value:
            names.update(_collect_property_names(nested))
    return names


def _route_segments(path: str) -> set[str]:
    return {
        segment.casefold().replace("_", "-")
        for segment in path.strip("/").split("/")
        if segment and not segment.startswith(("{", "[")) and segment != "page.tsx"
    }


def _openapi_operations(schema: Mapping[str, object]) -> tuple[ReleaseApiOperation, ...]:
    raw_paths = schema.get("paths")
    if not isinstance(raw_paths, Mapping):
        raise ValueError("OpenAPI schema does not contain a paths mapping")
    operations: list[ReleaseApiOperation] = []
    for raw_path, raw_path_item in raw_paths.items():
        if not isinstance(raw_path, str) or not isinstance(raw_path_item, Mapping):
            raise ValueError("OpenAPI path inventory is malformed")
        for raw_method in raw_path_item:
            method = str(raw_method).casefold()
            if method in _OPENAPI_HTTP_METHODS:
                operations.append(ReleaseApiOperation(method=method.upper(), path=raw_path))
    return tuple(sorted(operations, key=lambda item: (item.path, item.method)))


def _version_sources(repository_root: Path) -> tuple[tuple[str, str], ...]:
    with (repository_root / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    package = json.loads((repository_root / "frontend/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads(
        (repository_root / "frontend/package-lock.json").read_text(encoding="utf-8")
    )
    environment = dict(
        line.split("=", maxsplit=1)
        for line in (repository_root / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    return tuple(
        sorted(
            (
                ("backend-runtime", __version__),
                ("environment-example", environment["TRD_BOT_APP_VERSION"]),
                ("frontend-lock-root", str(package_lock["packages"][""]["version"])),
                ("frontend-lockfile", str(package_lock["version"])),
                ("frontend-package", str(package["version"])),
                ("python-project", str(pyproject["project"]["version"])),
            )
        )
    )


def build_release_surface_inventory(repository_root: Path) -> ReleaseSurfaceInventory:
    root = repository_root.resolve()
    schema = create_app().openapi()
    providers = tuple(
        sorted(
            (
                ReleaseProviderSurface(
                    provider_id=metadata.provider_id,
                    requires_credentials=metadata.requires_credentials,
                    market_types=tuple(
                        sorted(item.value for item in metadata.supported_market_types)
                    ),
                    access_mode=metadata.access_mode.value,
                )
                for metadata in MarketDataProviderCatalog().list_metadata()
            ),
            key=lambda item: item.provider_id,
        )
    )
    jobs = tuple(
        sorted(
            (
                ReleaseJobSurface(
                    kind=kind.value,
                    max_attempts=policy.max_attempts,
                    payload_versions=tuple(sorted(policy.supported_payload_versions)),
                    cancellation_mode=policy.cancellation_mode.value,
                )
                for kind, policy in BACKGROUND_JOB_POLICIES.items()
            ),
            key=lambda item: item.kind,
        )
    )
    frontend_root = root / "frontend/src/app"
    migration_root = root / "alembic/versions"
    alembic_config = Config(str(root / "alembic.ini"))
    script_directory = ScriptDirectory.from_config(alembic_config)
    return ReleaseSurfaceInventory(
        product_version=__version__,
        version_sources=_version_sources(root),
        api_operations=_openapi_operations(schema),
        openapi_property_names=tuple(sorted(_collect_property_names(schema))),
        frontend_page_files=tuple(
            sorted(
                path.relative_to(frontend_root).as_posix()
                for path in frontend_root.rglob("page.tsx")
            )
        ),
        providers=providers,
        jobs=jobs,
        database_tables=tuple(sorted(DatabaseBase.metadata.tables)),
        migration_revisions=tuple(sorted(path.stem for path in migration_root.glob("*.py"))),
        migration_heads=tuple(sorted(script_directory.get_heads())),
        network_user_agents=tuple(
            sorted(
                (
                    ("market-data-provider", MARKET_DATA_PROVIDER_USER_AGENT),
                    ("provider-probe", MARKET_DATA_PROBE_USER_AGENT),
                )
            )
        ),
    )


def evaluate_release_inventory(inventory: ReleaseSurfaceInventory) -> tuple[str, ...]:
    reasons: list[str] = []
    if inventory.product_version != V0_3_RELEASE_VERSION:
        reasons.append("release product version is not v0.3.0")
    if any(version != inventory.product_version for _, version in inventory.version_sources):
        reasons.append("release version sources are inconsistent")
    if any(item.method not in _ALLOWED_RELEASE_API_METHODS for item in inventory.api_operations):
        reasons.append("release API exposes a method outside GET and POST")
    api_segments = set().union(*(_route_segments(item.path) for item in inventory.api_operations))
    if not PROHIBITED_LIVE_ROUTE_SEGMENTS.isdisjoint(api_segments):
        reasons.append("release API exposes a prohibited live-execution route")
    if not PROHIBITED_CREDENTIAL_FIELDS.isdisjoint(inventory.openapi_property_names):
        reasons.append("release OpenAPI exposes a prohibited credential field")
    frontend_segments = set().union(
        *(_route_segments(item) for item in inventory.frontend_page_files)
    )
    if not PROHIBITED_LIVE_ROUTE_SEGMENTS.isdisjoint(frontend_segments):
        reasons.append("release frontend exposes a prohibited live-execution page")
    if any(
        not provider.provider_id.endswith("-public")
        or provider.requires_credentials
        or provider.market_types != ("spot",)
        for provider in inventory.providers
    ):
        reasons.append("release provider catalog is not public read-only Crypto Spot")
    job_segments = set().union(*(_route_segments(item.kind) for item in inventory.jobs))
    if not PROHIBITED_LIVE_ROUTE_SEGMENTS.isdisjoint(job_segments):
        reasons.append("release worker catalog exposes a prohibited live-execution workload")
    if len(inventory.migration_heads) != 1:
        reasons.append("release migration graph does not have exactly one head")
    if any(
        not user_agent.endswith(f"/{inventory.product_version}")
        for _, user_agent in inventory.network_user_agents
    ):
        reasons.append("release network user agents do not match the product version")
    return tuple(reasons)


def build_release_hardening_report(repository_root: Path) -> ReleaseHardeningReport:
    inventory = build_release_surface_inventory(repository_root)
    return ReleaseHardeningReport(
        inventory=inventory,
        failure_reasons=evaluate_release_inventory(inventory),
    )


def release_hardening_report_to_dict(report: ReleaseHardeningReport) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    payload["inventory"]["counts"] = report.inventory.counts
    payload["inventory"]["definition_checksum"] = report.inventory.definition_checksum
    payload["passed"] = report.passed
    return payload


def serialize_release_hardening_report(report: ReleaseHardeningReport) -> str:
    return json.dumps(release_hardening_report_to_dict(report), indent=2, sort_keys=True)


def parse_release_hardening_report(value: str | bytes) -> ReleaseHardeningReport:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("release hardening report is not valid JSON") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("inventory"), dict):
        raise ValueError("release hardening report must be a JSON object")
    payload = dict(raw)
    persisted_passed = payload.pop("passed", None)
    inventory_payload = dict(payload["inventory"])
    persisted_counts = inventory_payload.pop("counts", None)
    persisted_checksum = inventory_payload.pop("definition_checksum", None)
    payload["inventory"] = inventory_payload
    report = ReleaseHardeningReport.model_validate(payload)
    if persisted_counts is not None and persisted_counts != report.inventory.counts:
        raise ValueError("release inventory counts are inconsistent")
    if (
        persisted_checksum is not None
        and persisted_checksum != report.inventory.definition_checksum
    ):
        raise ValueError("release inventory checksum is inconsistent")
    if persisted_passed is not None and persisted_passed is not report.passed:
        raise ValueError("release hardening outcome is inconsistent")
    return report
