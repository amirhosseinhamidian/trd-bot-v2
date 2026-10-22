from pathlib import Path

import pytest

from trd_bot.release_hardening import (
    PROHIBITED_CREDENTIAL_FIELDS,
    PROHIBITED_LIVE_ROUTE_SEGMENTS,
    ReleaseSurfaceInventory,
    build_release_surface_inventory,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def route_segments(path: str) -> set[str]:
    return {
        segment.casefold()
        for segment in path.strip("/").split("/")
        if segment and not segment.startswith("{")
    }


@pytest.fixture(scope="module")
def release_inventory() -> ReleaseSurfaceInventory:
    return build_release_surface_inventory(PROJECT_ROOT)


def test_release_api_has_no_live_execution_routes_or_credential_inputs(
    release_inventory: ReleaseSurfaceInventory,
) -> None:
    assert release_inventory.api_operations
    exposed_segments = set().union(
        *(route_segments(operation.path) for operation in release_inventory.api_operations)
    )
    assert PROHIBITED_LIVE_ROUTE_SEGMENTS.isdisjoint(exposed_segments)
    assert PROHIBITED_CREDENTIAL_FIELDS.isdisjoint(release_inventory.openapi_property_names)


def test_release_frontend_has_no_live_execution_page(
    release_inventory: ReleaseSurfaceInventory,
) -> None:
    page_segments: set[str] = set()
    for page in release_inventory.frontend_page_files:
        page_segments.update(route_segments(page))

    assert PROHIBITED_LIVE_ROUTE_SEGMENTS.isdisjoint(page_segments)


def test_release_provider_catalog_remains_public_and_read_only(
    release_inventory: ReleaseSurfaceInventory,
) -> None:
    assert release_inventory.providers
    assert all(provider.provider_id.endswith("-public") for provider in release_inventory.providers)
    assert all(provider.requires_credentials is False for provider in release_inventory.providers)
    assert all(provider.market_types == ("spot",) for provider in release_inventory.providers)
