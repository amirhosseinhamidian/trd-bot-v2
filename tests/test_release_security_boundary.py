from collections.abc import Mapping
from pathlib import Path

from fastapi.routing import APIRoute

from trd_bot.main import create_app
from trd_bot.market_data import MarketDataProviderCatalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]

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


def collect_property_names(value: object) -> set[str]:
    """Collect JSON schema property names without trusting schema shape."""

    names: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key == "properties" and isinstance(nested, Mapping):
                names.update(str(name).casefold() for name in nested)
            names.update(collect_property_names(nested))
    elif isinstance(value, list):
        for nested in value:
            names.update(collect_property_names(nested))
    return names


def route_segments(path: str) -> set[str]:
    return {
        segment.casefold()
        for segment in path.strip("/").split("/")
        if segment and not segment.startswith("{")
    }


def test_release_api_has_no_live_execution_routes_or_credential_inputs() -> None:
    application = create_app()
    api_routes = tuple(route for route in application.routes if isinstance(route, APIRoute))

    exposed_segments: set[str] = set()
    for route in api_routes:
        exposed_segments.update(route_segments(route.path_format))
    assert PROHIBITED_LIVE_ROUTE_SEGMENTS.isdisjoint(exposed_segments)

    openapi_property_names = collect_property_names(application.openapi())
    assert PROHIBITED_CREDENTIAL_FIELDS.isdisjoint(openapi_property_names)


def test_release_frontend_has_no_live_execution_page() -> None:
    app_root = PROJECT_ROOT / "frontend" / "src" / "app"
    page_segments: set[str] = set()
    for page in app_root.rglob("page.tsx"):
        page_segments.update(route_segments(page.relative_to(app_root).as_posix()))

    assert PROHIBITED_LIVE_ROUTE_SEGMENTS.isdisjoint(page_segments)


def test_release_provider_catalog_remains_public_and_read_only() -> None:
    providers = MarketDataProviderCatalog().list_metadata()

    assert providers
    assert all(provider.provider_id.endswith("-public") for provider in providers)
    assert all(provider.requires_credentials is False for provider in providers)
