from datetime import UTC, datetime
from decimal import Decimal

import pytest

from scripts.benchmark_market_data_providers import build_provider_evidence
from scripts.benchmark_postgresql_capacity import validate_benchmark_database_url
from trd_bot.market_data import (
    CapacityEvidenceMethod,
    MarketDataProbeOutcome,
    MarketDataProbeResult,
)

OBSERVED_AT = datetime(2026, 10, 9, 20, tzinfo=UTC)


def probe_result(
    provider_id: str,
    *,
    outcome: MarketDataProbeOutcome = MarketDataProbeOutcome.SUCCESS,
    http_latency_ms: int | None = 100,
) -> MarketDataProbeResult:
    successful = outcome is MarketDataProbeOutcome.SUCCESS
    return MarketDataProbeResult(
        provider_id=provider_id,
        display_name=provider_id,
        endpoint_host="example.test",
        endpoint_path="/public/ohlcv",
        market="BTC/USDT",
        timeframe="1h",
        observed_at=OBSERVED_AT,
        outcome=outcome,
        dns_latency_ms=10,
        resolved_address_count=1,
        tls_latency_ms=20,
        tls_version="TLSv1.3",
        http_latency_ms=http_latency_ms,
        http_status_code=200 if successful else 429,
        response_bytes=100 if successful else None,
        payload_valid=successful,
        candle_count=1 if successful else None,
        error_detail=None if successful else "Provider returned HTTP 429",
    )


def test_provider_evidence_aggregates_latency_and_failure_outcomes() -> None:
    evidence = build_provider_evidence(
        (
            probe_result("nobitex-public", http_latency_ms=100),
            probe_result("nobitex-public", http_latency_ms=200),
            probe_result(
                "nobitex-public",
                outcome=MarketDataProbeOutcome.RATE_LIMITED,
                http_latency_ms=50,
            ),
        ),
        selected_provider_ids=("nobitex-public",),
        minimum_samples_per_provider=3,
    )

    assert evidence.complete is True
    assert evidence.method is CapacityEvidenceMethod.LIVE_PROBE
    assert evidence.metrics["nobitex-public.http_latency_p95_ms"] == 200
    assert evidence.metrics["nobitex-public.success_fraction"] == Decimal(2) / Decimal(3)
    assert evidence.metrics["nobitex-public.rate_limited_fraction"] == Decimal(1) / Decimal(3)


def test_provider_evidence_stays_incomplete_below_sample_floor() -> None:
    evidence = build_provider_evidence(
        (probe_result("kraken-public"),),
        selected_provider_ids=("kraken-public",),
        minimum_samples_per_provider=30,
    )

    assert evidence.complete is False
    assert evidence.limitation is not None
    assert "kraken-public" in evidence.limitation


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite+pysqlite:///:memory:",
        "postgresql+psycopg://localhost/trd_bot",
        "postgresql+psycopg://localhost/production",
    ],
)
def test_postgresql_benchmark_rejects_non_dedicated_databases(database_url: str) -> None:
    with pytest.raises(ValueError):
        validate_benchmark_database_url(database_url)


def test_postgresql_benchmark_accepts_dedicated_test_or_benchmark_database() -> None:
    database_url = "postgresql+psycopg://localhost/trd_bot_benchmark"

    assert validate_benchmark_database_url(database_url) == database_url
