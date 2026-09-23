import json
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from trd_bot.market_data.provider_probes import (
    MarketDataProbeOutcome,
    MarketDataProbeReport,
    MarketDataProbeResult,
    available_market_data_probe_provider_ids,
    classify_market_data_probe_http_status,
    get_market_data_probe_spec,
    parse_market_data_probe_report,
    serialize_market_data_probe_report,
    validate_market_data_probe_payload,
)


@pytest.mark.parametrize(
    ("provider_id", "payload", "expected_count"),
    [
        (
            "bitstamp-public",
            {
                "data": {
                    "ohlc": [
                        {
                            "timestamp": "1725148800",
                            "open": "59000",
                            "high": "59200",
                            "low": "58900",
                            "close": "59100",
                            "volume": "12.5",
                        }
                    ]
                }
            },
            1,
        ),
        (
            "coinbase-exchange-public",
            [
                [1725148800, 58900, 59200, 59000, 59100, 12.5],
                [1725152400, 59000, 59300, 59100, 59200, 10.0],
            ],
            2,
        ),
        (
            "coinpaprika-free",
            [
                {
                    "time_open": "2026-09-19T00:00:00Z",
                    "time_close": "2026-09-19T23:59:59Z",
                    "open": 59000,
                    "high": 59200,
                    "low": 58900,
                    "close": 59100,
                    "volume": 12.5,
                }
            ],
            1,
        ),
        (
            "kraken-public",
            {
                "error": [],
                "result": {
                    "XXBTZUSD": [
                        [1725148800, "59000", "59200", "58900", "59100", "59050", "12.5", 4]
                    ],
                    "last": 1725152400,
                },
            },
            1,
        ),
        (
            "nobitex-public",
            {
                "s": "ok",
                "t": [1725148800, 1725152400],
                "o": [59000, 59100],
                "h": [59200, 59300],
                "l": [58900, 59000],
                "c": [59100, 59200],
                "v": [12.5, 10.0],
            },
            2,
        ),
    ],
)
def test_provider_probe_payload_parsers_accept_documented_shapes(
    provider_id: str,
    payload: object,
    expected_count: int,
) -> None:
    assert validate_market_data_probe_payload(provider_id, payload) == expected_count


@pytest.mark.parametrize(
    ("provider_id", "payload"),
    [
        ("bitstamp-public", {"data": {"ohlc": []}}),
        ("coinbase-exchange-public", [[1725148800, 58900]]),
        ("coinpaprika-free", [{"time_open": "2026-09-19T00:00:00Z"}]),
        ("kraken-public", {"error": ["temporary error"], "result": {}}),
        (
            "nobitex-public",
            {
                "s": "ok",
                "t": [1725148800],
                "o": [59000, 59100],
                "h": [59200],
                "l": [58900],
                "c": [59100],
                "v": [12.5],
            },
        ),
    ],
)
def test_provider_probe_payload_parsers_reject_unusable_shapes(
    provider_id: str,
    payload: object,
) -> None:
    with pytest.raises(ValueError):
        validate_market_data_probe_payload(provider_id, payload)


def test_probe_registry_uses_fixed_https_endpoints_without_credentials() -> None:
    observed_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    forbidden_query_names = {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "signature",
        "token",
    }

    assert available_market_data_probe_provider_ids() == (
        "bitstamp-public",
        "coinbase-exchange-public",
        "coinpaprika-free",
        "kraken-public",
        "nobitex-public",
    )
    for provider_id in available_market_data_probe_provider_ids():
        parsed = urlsplit(get_market_data_probe_spec(provider_id).build_url(observed_at))
        assert parsed.scheme == "https"
        assert parsed.hostname
        assert parsed.username is None
        assert parsed.password is None
        assert forbidden_query_names.isdisjoint(parse_qs(parsed.query))


def test_nobitex_probe_uses_the_documented_public_api_host() -> None:
    observed_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    parsed = urlsplit(get_market_data_probe_spec("nobitex-public").build_url(observed_at))

    assert parsed.hostname == "apiv2.nobitex.ir"
    assert parsed.path == "/market/udf/history"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, MarketDataProbeOutcome.SUCCESS),
        (204, MarketDataProbeOutcome.SUCCESS),
        (403, MarketDataProbeOutcome.GEO_BLOCKED),
        (451, MarketDataProbeOutcome.GEO_BLOCKED),
        (429, MarketDataProbeOutcome.RATE_LIMITED),
        (408, MarketDataProbeOutcome.TIMEOUT),
        (504, MarketDataProbeOutcome.TIMEOUT),
        (500, MarketDataProbeOutcome.HTTP_ERROR),
    ],
)
def test_probe_http_statuses_have_stable_outcomes(
    status_code: int,
    expected: MarketDataProbeOutcome,
) -> None:
    assert classify_market_data_probe_http_status(status_code) is expected


def test_probe_report_round_trip_keeps_only_sanitized_measurements() -> None:
    observed_at = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    success = MarketDataProbeResult(
        provider_id="bitstamp-public",
        display_name="Bitstamp Public",
        endpoint_host="www.bitstamp.net",
        endpoint_path="/api/v2/ohlc/btcusd/",
        market="BTC/USD",
        timeframe="1h",
        observed_at=observed_at,
        outcome=MarketDataProbeOutcome.SUCCESS,
        dns_latency_ms=20,
        resolved_address_count=2,
        tls_latency_ms=40,
        tls_version="TLSv1.3",
        http_latency_ms=80,
        http_status_code=200,
        response_bytes=350,
        payload_valid=True,
        candle_count=2,
        error_detail=None,
    )
    blocked = MarketDataProbeResult(
        provider_id="coinbase-exchange-public",
        display_name="Coinbase Exchange Public",
        endpoint_host="api.exchange.coinbase.com",
        endpoint_path="/products/BTC-USD/candles",
        market="BTC/USD",
        timeframe="1h",
        observed_at=observed_at,
        outcome=MarketDataProbeOutcome.GEO_BLOCKED,
        dns_latency_ms=15,
        resolved_address_count=2,
        tls_latency_ms=35,
        tls_version="TLSv1.3",
        http_latency_ms=50,
        http_status_code=451,
        response_bytes=None,
        payload_valid=False,
        candle_count=None,
        error_detail="Provider returned HTTP 451",
    )
    report = MarketDataProbeReport(
        schema_version=1,
        is_synthetic=True,
        environment_label="fixture",
        generated_at=observed_at,
        results=(success, blocked),
    )

    serialized = serialize_market_data_probe_report(report)
    parsed = parse_market_data_probe_report(serialized)

    assert parsed == report
    assert "api_key" not in serialized
    assert "response_body" not in serialized
    assert "172." not in serialized


def test_probe_report_parser_rejects_unknown_schema() -> None:
    report = {
        "schema_version": 2,
        "is_synthetic": True,
        "environment_label": "fixture",
        "generated_at": "2026-09-19T12:00:00Z",
        "results": [
            {
                "provider_id": "bitstamp-public",
                "display_name": "Bitstamp Public",
                "endpoint_host": "www.bitstamp.net",
                "endpoint_path": "/api/v2/ohlc/btcusd/",
                "market": "BTC/USD",
                "timeframe": "1h",
                "observed_at": "2026-09-19T12:00:00Z",
                "outcome": "success",
                "dns_latency_ms": 20,
                "resolved_address_count": 2,
                "tls_latency_ms": 40,
                "tls_version": "TLSv1.3",
                "http_latency_ms": 80,
                "http_status_code": 200,
                "response_bytes": 350,
                "payload_valid": True,
                "candle_count": 2,
                "error_detail": None,
            }
        ],
    }

    with pytest.raises(ValueError, match=r"unsupported.*schema"):
        parse_market_data_probe_report(json.dumps(report))


def test_probe_result_rejects_false_success() -> None:
    with pytest.raises(ValueError, match="at least one valid candle"):
        MarketDataProbeResult(
            provider_id="bitstamp-public",
            display_name="Bitstamp Public",
            endpoint_host="www.bitstamp.net",
            endpoint_path="/api/v2/ohlc/btcusd/",
            market="BTC/USD",
            timeframe="1h",
            observed_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
            outcome=MarketDataProbeOutcome.SUCCESS,
            dns_latency_ms=20,
            resolved_address_count=2,
            tls_latency_ms=40,
            tls_version="TLSv1.3",
            http_latency_ms=80,
            http_status_code=200,
            response_bytes=2,
            payload_valid=False,
            candle_count=0,
            error_detail=None,
        )
