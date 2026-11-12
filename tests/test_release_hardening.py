import json
from pathlib import Path

import pytest

from trd_bot.release_hardening import (
    ReleaseApiOperation,
    ReleaseHardeningReport,
    ReleaseJobSurface,
    build_release_hardening_report,
    evaluate_release_inventory,
    parse_release_hardening_report,
    serialize_release_hardening_report,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_INVENTORY_CHECKSUM = "7c97e85703da7c312d24deabec9c3f9b7a3d1be19694a69a1c003f458996df68"


@pytest.fixture(scope="module")
def release_report() -> ReleaseHardeningReport:
    return build_release_hardening_report(REPOSITORY_ROOT)


def test_release_inventory_is_complete_deterministic_and_frozen(
    release_report: ReleaseHardeningReport,
) -> None:
    inventory = release_report.inventory

    assert release_report.passed is True
    assert release_report.failure_reasons == ()
    assert inventory.counts == {
        "api_operations": 120,
        "database_tables": 62,
        "frontend_pages": 23,
        "jobs": 11,
        "migration_heads": 1,
        "migration_revisions": 40,
        "providers": 3,
    }
    assert inventory.definition_checksum == EXPECTED_INVENTORY_CHECKSUM
    assert parse_release_hardening_report(serialize_release_hardening_report(release_report)) == (
        release_report
    )


def test_release_inventory_scans_real_openapi_operations(
    release_report: ReleaseHardeningReport,
) -> None:
    operations = release_report.inventory.api_operations

    assert ReleaseApiOperation(method="GET", path="/api/v1/health") in operations
    assert (
        ReleaseApiOperation(
            method="GET",
            path="/api/v1/integration/nexora/snapshots/{resource_type}",
        )
        in operations
    )
    assert (
        ReleaseApiOperation(method="POST", path="/api/v1/integration/nexora/exports") in operations
    )
    assert (
        ReleaseApiOperation(method="GET", path="/api/v1/integration/nexora/exports/{export_id}")
        in operations
    )
    assert (
        ReleaseApiOperation(
            method="GET", path="/api/v1/integration/nexora/exports/{export_id}/manifest"
        )
        in operations
    )
    assert (
        ReleaseApiOperation(
            method="GET",
            path="/api/v1/integration/nexora/capabilities",
        )
        in operations
    )
    assert ReleaseApiOperation(method="GET", path="/api/v1/integration/nexora/events") in operations
    assert (
        ReleaseApiOperation(
            method="GET",
            path="/api/v1/integration/nexora/events/{event_id}",
        )
        in operations
    )
    assert (
        ReleaseApiOperation(
            method="POST",
            path="/api/v1/integration/nexora/commands/decision-reviews",
        )
        in operations
    )
    assert ReleaseApiOperation(method="POST", path="/api/v1/research/datasets") in operations
    assert {item.method for item in operations} == {"GET", "POST"}


def test_release_inventory_fails_closed_for_live_route(
    release_report: ReleaseHardeningReport,
) -> None:
    inventory = release_report.inventory
    operations = tuple(
        sorted(
            (
                *inventory.api_operations,
                ReleaseApiOperation(method="POST", path="/api/v1/live-orders"),
            ),
            key=lambda item: (item.path, item.method),
        )
    )
    tampered = inventory.model_copy(update={"api_operations": operations})

    assert "release API exposes a prohibited live-execution route" in evaluate_release_inventory(
        tampered
    )


def test_release_inventory_fails_closed_for_live_worker(
    release_report: ReleaseHardeningReport,
) -> None:
    inventory = release_report.inventory
    jobs = tuple(
        sorted(
            (
                *inventory.jobs,
                ReleaseJobSurface(
                    kind="live_order",
                    max_attempts=1,
                    payload_versions=(1,),
                    cancellation_mode="cooperative",
                ),
            ),
            key=lambda item: item.kind,
        )
    )
    tampered = inventory.model_copy(update={"jobs": jobs})

    assert "release worker catalog exposes a prohibited live-execution workload" in (
        evaluate_release_inventory(tampered)
    )


def test_release_report_parser_rejects_tampered_inventory(
    release_report: ReleaseHardeningReport,
) -> None:
    payload = json.loads(serialize_release_hardening_report(release_report))
    payload["inventory"]["openapi_property_names"].append("api_key")
    payload["inventory"]["openapi_property_names"].sort()

    with pytest.raises(ValueError, match="inconsistent"):
        parse_release_hardening_report(json.dumps(payload))


def test_network_clients_identify_the_current_release(
    release_report: ReleaseHardeningReport,
) -> None:
    assert dict(release_report.inventory.network_user_agents) == {
        "market-data-provider": "trd-bot-v2-research/0.3.1",
        "provider-probe": "trd-bot-v2-provider-probe/0.3.1",
    }
