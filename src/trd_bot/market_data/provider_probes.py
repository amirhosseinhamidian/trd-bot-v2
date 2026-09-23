import json
import socket
import ssl
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class MarketDataProbeOutcome(StrEnum):
    """Stable, credential-free connectivity probe outcomes."""

    SUCCESS = "success"
    DNS_FAILURE = "dns_failure"
    TLS_FAILURE = "tls_failure"
    TIMEOUT = "timeout"
    GEO_BLOCKED = "geo_blocked"
    RATE_LIMITED = "rate_limited"
    HTTP_ERROR = "http_error"
    INVALID_RESPONSE = "invalid_response"
    TRANSPORT_ERROR = "transport_error"


class MarketDataProbePayloadError(ValueError):
    """Raised when a public endpoint does not return its documented candle shape."""


PayloadParser = Callable[[object], int]
UrlFactory = Callable[[datetime], str]


@dataclass(frozen=True, slots=True)
class MarketDataProbeSpec:
    provider_id: str
    display_name: str
    market: str
    timeframe: str
    url_factory: UrlFactory
    payload_parser: PayloadParser

    def build_url(self, observed_at: datetime) -> str:
        url = self.url_factory(observed_at)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("probe endpoints must use an absolute HTTPS URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("probe endpoints cannot contain credentials")
        return url


@dataclass(frozen=True, slots=True)
class MarketDataProbeResult:
    provider_id: str
    display_name: str
    endpoint_host: str
    endpoint_path: str
    market: str
    timeframe: str
    observed_at: datetime
    outcome: MarketDataProbeOutcome
    dns_latency_ms: int | None
    resolved_address_count: int | None
    tls_latency_ms: int | None
    tls_version: str | None
    http_latency_ms: int | None
    http_status_code: int | None
    response_bytes: int | None
    payload_valid: bool
    candle_count: int | None
    error_detail: str | None

    def __post_init__(self) -> None:
        if not self.provider_id or not self.display_name:
            raise ValueError("probe result provider identity cannot be empty")
        if not self.endpoint_host or not self.endpoint_path.startswith("/"):
            raise ValueError("probe result endpoint must contain a host and path")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("probe result timestamp must include timezone information")

        numeric_values = (
            self.dns_latency_ms,
            self.resolved_address_count,
            self.tls_latency_ms,
            self.http_latency_ms,
            self.http_status_code,
            self.response_bytes,
            self.candle_count,
        )
        if any(value is not None and value < 0 for value in numeric_values):
            raise ValueError("probe result numeric values cannot be negative")

        if self.outcome is MarketDataProbeOutcome.SUCCESS:
            if self.http_status_code is None or not 200 <= self.http_status_code < 300:
                raise ValueError("successful probe must contain a successful HTTP status")
            if not self.payload_valid or self.candle_count is None or self.candle_count <= 0:
                raise ValueError("successful probe must contain at least one valid candle")
            if self.error_detail is not None:
                raise ValueError("successful probe cannot contain an error detail")
        elif not self.error_detail:
            raise ValueError("failed probe must contain a bounded error detail")


@dataclass(frozen=True, slots=True)
class MarketDataProbeReport:
    schema_version: int
    is_synthetic: bool
    environment_label: str
    generated_at: datetime
    results: tuple[MarketDataProbeResult, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported market-data probe report schema")
        if not self.environment_label or len(self.environment_label) > 64:
            raise ValueError("environment label must contain between 1 and 64 characters")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("probe report timestamp must include timezone information")
        if not self.results:
            raise ValueError("probe report must contain at least one result")
        provider_ids = [result.provider_id for result in self.results]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("probe report cannot contain duplicate providers")


def _fixed_url(url: str) -> UrlFactory:
    def build_url(_: datetime) -> str:
        return url

    return build_url


def _nobitex_url(observed_at: datetime) -> str:
    end_time = int(observed_at.timestamp())
    start_time = end_time - (3 * 60 * 60)
    query = urlencode(
        {
            "symbol": "BTCUSDT",
            "resolution": "60",
            "from": start_time,
            "to": end_time,
        }
    )
    return f"https://apiv2.nobitex.ir/market/udf/history?{query}"


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise MarketDataProbePayloadError(f"{context} must be a JSON object")
    return cast(dict[str, object], value)


def _list(value: object, *, context: str) -> list[object]:
    if not isinstance(value, list):
        raise MarketDataProbePayloadError(f"{context} must be a JSON array")
    return cast(list[object], value)


def _field(mapping: Mapping[str, object], name: str, *, context: str) -> object:
    if name not in mapping:
        raise MarketDataProbePayloadError(f"{context} is missing {name}")
    return mapping[name]


def _number_like(value: object, *, context: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise MarketDataProbePayloadError(f"{context} must contain a numeric value")
    if isinstance(value, str) and not value.strip():
        raise MarketDataProbePayloadError(f"{context} cannot be empty")


def _parse_bitstamp_payload(payload: object) -> int:
    root = _mapping(payload, context="Bitstamp payload")
    data = _mapping(_field(root, "data", context="Bitstamp payload"), context="Bitstamp data")
    candles = _list(_field(data, "ohlc", context="Bitstamp data"), context="Bitstamp ohlc")
    if not candles:
        raise MarketDataProbePayloadError("Bitstamp payload contains no candles")

    for index, raw_candle in enumerate(candles):
        candle = _mapping(raw_candle, context=f"Bitstamp candle {index}")
        for name in ("timestamp", "open", "high", "low", "close", "volume"):
            _number_like(
                _field(candle, name, context=f"Bitstamp candle {index}"),
                context=f"Bitstamp candle {index}.{name}",
            )
    return len(candles)


def _parse_kraken_payload(payload: object) -> int:
    root = _mapping(payload, context="Kraken payload")
    errors = _list(_field(root, "error", context="Kraken payload"), context="Kraken errors")
    if errors:
        raise MarketDataProbePayloadError("Kraken payload contains API errors")

    result = _mapping(_field(root, "result", context="Kraken payload"), context="Kraken result")
    series = [value for key, value in result.items() if key != "last"]
    if len(series) != 1:
        raise MarketDataProbePayloadError("Kraken payload must contain exactly one candle series")
    candles = _list(series[0], context="Kraken candle series")
    if not candles:
        raise MarketDataProbePayloadError("Kraken payload contains no candles")

    for index, raw_candle in enumerate(candles):
        candle = _list(raw_candle, context=f"Kraken candle {index}")
        if len(candle) < 7:
            raise MarketDataProbePayloadError("Kraken candle has fewer than seven values")
        for value_index in range(7):
            _number_like(candle[value_index], context=f"Kraken candle {index}[{value_index}]")
    return len(candles)


def _parse_coinbase_payload(payload: object) -> int:
    candles = _list(payload, context="Coinbase payload")
    if not candles:
        raise MarketDataProbePayloadError("Coinbase payload contains no candles")
    for index, raw_candle in enumerate(candles):
        candle = _list(raw_candle, context=f"Coinbase candle {index}")
        if len(candle) < 6:
            raise MarketDataProbePayloadError("Coinbase candle has fewer than six values")
        for value_index in range(6):
            _number_like(candle[value_index], context=f"Coinbase candle {index}[{value_index}]")
    return len(candles)


def _parse_coinpaprika_payload(payload: object) -> int:
    candles = _list(payload, context="CoinPaprika payload")
    if not candles:
        raise MarketDataProbePayloadError("CoinPaprika payload contains no candles")
    for index, raw_candle in enumerate(candles):
        candle = _mapping(raw_candle, context=f"CoinPaprika candle {index}")
        for name in ("open", "high", "low", "close", "volume"):
            _number_like(
                _field(candle, name, context=f"CoinPaprika candle {index}"),
                context=f"CoinPaprika candle {index}.{name}",
            )
        time_open = _field(candle, "time_open", context=f"CoinPaprika candle {index}")
        if not isinstance(time_open, str) or not time_open:
            raise MarketDataProbePayloadError("CoinPaprika candle time_open must be a string")
    return len(candles)


def _parse_nobitex_payload(payload: object) -> int:
    root = _mapping(payload, context="Nobitex payload")
    status = _field(root, "s", context="Nobitex payload")
    if status != "ok":
        raise MarketDataProbePayloadError("Nobitex payload status is not ok")

    columns = {
        name: _list(_field(root, name, context="Nobitex payload"), context=f"Nobitex {name}")
        for name in ("t", "o", "h", "l", "c", "v")
    }
    candle_count = len(columns["t"])
    if candle_count == 0:
        raise MarketDataProbePayloadError("Nobitex payload contains no candles")
    if any(len(values) != candle_count for values in columns.values()):
        raise MarketDataProbePayloadError("Nobitex candle columns have inconsistent lengths")
    for name, values in columns.items():
        for index, value in enumerate(values):
            _number_like(value, context=f"Nobitex {name}[{index}]")
    return candle_count


_PROBE_SPECS: dict[str, MarketDataProbeSpec] = {
    "bitstamp-public": MarketDataProbeSpec(
        provider_id="bitstamp-public",
        display_name="Bitstamp Public",
        market="BTC/USD",
        timeframe="1h",
        url_factory=_fixed_url(
            "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
            "?step=3600&limit=2&exclude_current_candle=true"
        ),
        payload_parser=_parse_bitstamp_payload,
    ),
    "coinbase-exchange-public": MarketDataProbeSpec(
        provider_id="coinbase-exchange-public",
        display_name="Coinbase Exchange Public",
        market="BTC/USD",
        timeframe="1h",
        url_factory=_fixed_url(
            "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600"
        ),
        payload_parser=_parse_coinbase_payload,
    ),
    "coinpaprika-free": MarketDataProbeSpec(
        provider_id="coinpaprika-free",
        display_name="CoinPaprika Free",
        market="BTC/USD aggregated",
        timeframe="current day",
        url_factory=_fixed_url("https://api.coinpaprika.com/v1/coins/btc-bitcoin/ohlcv/today"),
        payload_parser=_parse_coinpaprika_payload,
    ),
    "kraken-public": MarketDataProbeSpec(
        provider_id="kraken-public",
        display_name="Kraken Public",
        market="XBT/USD",
        timeframe="1h",
        url_factory=_fixed_url("https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60"),
        payload_parser=_parse_kraken_payload,
    ),
    "nobitex-public": MarketDataProbeSpec(
        provider_id="nobitex-public",
        display_name="Nobitex Public",
        market="BTC/USDT",
        timeframe="1h",
        url_factory=_nobitex_url,
        payload_parser=_parse_nobitex_payload,
    ),
}

_MAX_RESPONSE_BYTES = 2_000_000


def available_market_data_probe_provider_ids() -> tuple[str, ...]:
    return tuple(sorted(_PROBE_SPECS))


def get_market_data_probe_spec(provider_id: str) -> MarketDataProbeSpec:
    try:
        return _PROBE_SPECS[provider_id]
    except KeyError as exc:
        raise ValueError(f"unsupported market-data probe provider: {provider_id}") from exc


def validate_market_data_probe_payload(provider_id: str, payload: object) -> int:
    return get_market_data_probe_spec(provider_id).payload_parser(payload)


def classify_market_data_probe_http_status(status_code: int) -> MarketDataProbeOutcome:
    if 200 <= status_code < 300:
        return MarketDataProbeOutcome.SUCCESS
    if status_code in {403, 451}:
        return MarketDataProbeOutcome.GEO_BLOCKED
    if status_code == 429:
        return MarketDataProbeOutcome.RATE_LIMITED
    if status_code in {408, 504}:
        return MarketDataProbeOutcome.TIMEOUT
    return MarketDataProbeOutcome.HTTP_ERROR


def _elapsed_milliseconds(started_at: float) -> int:
    return max(0, round((time.monotonic() - started_at) * 1_000))


def _build_result(
    spec: MarketDataProbeSpec,
    *,
    url: str,
    observed_at: datetime,
    outcome: MarketDataProbeOutcome,
    dns_latency_ms: int | None,
    resolved_address_count: int | None,
    tls_latency_ms: int | None,
    tls_version: str | None,
    http_latency_ms: int | None = None,
    http_status_code: int | None = None,
    response_bytes: int | None = None,
    payload_valid: bool = False,
    candle_count: int | None = None,
    error_detail: str | None = None,
) -> MarketDataProbeResult:
    parsed = urlsplit(url)
    return MarketDataProbeResult(
        provider_id=spec.provider_id,
        display_name=spec.display_name,
        endpoint_host=parsed.hostname or "invalid-host",
        endpoint_path=parsed.path or "/",
        market=spec.market,
        timeframe=spec.timeframe,
        observed_at=observed_at,
        outcome=outcome,
        dns_latency_ms=dns_latency_ms,
        resolved_address_count=resolved_address_count,
        tls_latency_ms=tls_latency_ms,
        tls_version=tls_version,
        http_latency_ms=http_latency_ms,
        http_status_code=http_status_code,
        response_bytes=response_bytes,
        payload_valid=payload_valid,
        candle_count=candle_count,
        error_detail=error_detail,
    )


def probe_market_data_provider(
    provider_id: str,
    *,
    timeout_seconds: float = 10.0,
    observed_at: datetime | None = None,
) -> MarketDataProbeResult:
    """Probe one fixed public endpoint without credentials or response-body persistence."""

    if not 1.0 <= timeout_seconds <= 30.0:
        raise ValueError("probe timeout must be between 1 and 30 seconds")
    observed_at = observed_at or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("probe timestamp must include timezone information")
    observed_at = observed_at.astimezone(UTC)

    spec = get_market_data_probe_spec(provider_id)
    url = spec.build_url(observed_at)
    parsed = urlsplit(url)
    host = parsed.hostname
    if host is None:
        raise ValueError("probe endpoint is missing its host")

    dns_started_at = time.monotonic()
    try:
        resolved_addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=MarketDataProbeOutcome.DNS_FAILURE,
            dns_latency_ms=_elapsed_milliseconds(dns_started_at),
            resolved_address_count=None,
            tls_latency_ms=None,
            tls_version=None,
            error_detail="DNS lookup failed",
        )
    dns_latency_ms = _elapsed_milliseconds(dns_started_at)
    resolved_address_count = len(resolved_addresses)

    tls_started_at = time.monotonic()
    try:
        context = ssl.create_default_context()
        with (
            socket.create_connection((host, 443), timeout=timeout_seconds) as plain_socket,
            context.wrap_socket(plain_socket, server_hostname=host) as tls_socket,
        ):
            tls_version = tls_socket.version()
    except TimeoutError:
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=MarketDataProbeOutcome.TIMEOUT,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=_elapsed_milliseconds(tls_started_at),
            tls_version=None,
            error_detail="TLS connection timed out",
        )
    except OSError:
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=MarketDataProbeOutcome.TLS_FAILURE,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=_elapsed_milliseconds(tls_started_at),
            tls_version=None,
            error_detail="TLS handshake failed",
        )
    tls_latency_ms = _elapsed_milliseconds(tls_started_at)

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "trd-bot-v2-provider-probe/0.1",
        },
    )
    http_started_at = time.monotonic()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.status
            response_body = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        outcome = classify_market_data_probe_http_status(exc.code)
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=outcome,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=tls_latency_ms,
            tls_version=tls_version,
            http_latency_ms=_elapsed_milliseconds(http_started_at),
            http_status_code=exc.code,
            error_detail=f"Provider returned HTTP {exc.code}",
        )
    except URLError as exc:
        if isinstance(exc.reason, socket.gaierror):
            outcome = MarketDataProbeOutcome.DNS_FAILURE
            detail = "HTTP DNS lookup failed"
        elif isinstance(exc.reason, ssl.SSLError):
            outcome = MarketDataProbeOutcome.TLS_FAILURE
            detail = "HTTP TLS handshake failed"
        elif isinstance(exc.reason, TimeoutError):
            outcome = MarketDataProbeOutcome.TIMEOUT
            detail = "Provider request timed out"
        else:
            outcome = MarketDataProbeOutcome.TRANSPORT_ERROR
            detail = "Provider transport request failed"
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=outcome,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=tls_latency_ms,
            tls_version=tls_version,
            http_latency_ms=_elapsed_milliseconds(http_started_at),
            error_detail=detail,
        )
    except TimeoutError:
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=MarketDataProbeOutcome.TIMEOUT,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=tls_latency_ms,
            tls_version=tls_version,
            http_latency_ms=_elapsed_milliseconds(http_started_at),
            error_detail="Provider request timed out",
        )
    except OSError:
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=MarketDataProbeOutcome.TRANSPORT_ERROR,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=tls_latency_ms,
            tls_version=tls_version,
            http_latency_ms=_elapsed_milliseconds(http_started_at),
            error_detail="Provider transport request failed",
        )

    http_latency_ms = _elapsed_milliseconds(http_started_at)
    if len(response_body) > _MAX_RESPONSE_BYTES:
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=MarketDataProbeOutcome.INVALID_RESPONSE,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=tls_latency_ms,
            tls_version=tls_version,
            http_latency_ms=http_latency_ms,
            http_status_code=status_code,
            response_bytes=len(response_body),
            error_detail="Provider response exceeded the two-megabyte safety limit",
        )

    try:
        payload = cast(object, json.loads(response_body.decode("utf-8")))
        candle_count = spec.payload_parser(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=MarketDataProbeOutcome.INVALID_RESPONSE,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=tls_latency_ms,
            tls_version=tls_version,
            http_latency_ms=http_latency_ms,
            http_status_code=status_code,
            response_bytes=len(response_body),
            error_detail="Provider returned a non-JSON response",
        )
    except MarketDataProbePayloadError as exc:
        return _build_result(
            spec,
            url=url,
            observed_at=observed_at,
            outcome=MarketDataProbeOutcome.INVALID_RESPONSE,
            dns_latency_ms=dns_latency_ms,
            resolved_address_count=resolved_address_count,
            tls_latency_ms=tls_latency_ms,
            tls_version=tls_version,
            http_latency_ms=http_latency_ms,
            http_status_code=status_code,
            response_bytes=len(response_body),
            error_detail=str(exc)[:240],
        )

    return _build_result(
        spec,
        url=url,
        observed_at=observed_at,
        outcome=MarketDataProbeOutcome.SUCCESS,
        dns_latency_ms=dns_latency_ms,
        resolved_address_count=resolved_address_count,
        tls_latency_ms=tls_latency_ms,
        tls_version=tls_version,
        http_latency_ms=http_latency_ms,
        http_status_code=status_code,
        response_bytes=len(response_body),
        payload_valid=True,
        candle_count=candle_count,
    )


def probe_market_data_providers(
    provider_ids: tuple[str, ...],
    *,
    environment_label: str,
    timeout_seconds: float = 10.0,
) -> MarketDataProbeReport:
    generated_at = datetime.now(UTC)
    results = tuple(
        probe_market_data_provider(
            provider_id,
            timeout_seconds=timeout_seconds,
            observed_at=datetime.now(UTC),
        )
        for provider_id in provider_ids
    )
    return MarketDataProbeReport(
        schema_version=1,
        is_synthetic=False,
        environment_label=environment_label,
        generated_at=generated_at,
        results=results,
    )


def _datetime_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def market_data_probe_report_to_dict(report: MarketDataProbeReport) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for result in report.results:
        results.append(
            {
                "provider_id": result.provider_id,
                "display_name": result.display_name,
                "endpoint_host": result.endpoint_host,
                "endpoint_path": result.endpoint_path,
                "market": result.market,
                "timeframe": result.timeframe,
                "observed_at": _datetime_text(result.observed_at),
                "outcome": result.outcome.value,
                "dns_latency_ms": result.dns_latency_ms,
                "resolved_address_count": result.resolved_address_count,
                "tls_latency_ms": result.tls_latency_ms,
                "tls_version": result.tls_version,
                "http_latency_ms": result.http_latency_ms,
                "http_status_code": result.http_status_code,
                "response_bytes": result.response_bytes,
                "payload_valid": result.payload_valid,
                "candle_count": result.candle_count,
                "error_detail": result.error_detail,
            }
        )
    return {
        "schema_version": report.schema_version,
        "is_synthetic": report.is_synthetic,
        "environment_label": report.environment_label,
        "generated_at": _datetime_text(report.generated_at),
        "results": results,
    }


def serialize_market_data_probe_report(report: MarketDataProbeReport) -> str:
    return json.dumps(
        market_data_probe_report_to_dict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _required_text(mapping: Mapping[str, object], name: str) -> str:
    value = _field(mapping, name, context="probe report")
    if not isinstance(value, str) or not value:
        raise ValueError(f"probe report field {name} must be a non-empty string")
    return value


def _optional_text(mapping: Mapping[str, object], name: str) -> str | None:
    value = _field(mapping, name, context="probe report")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"probe report field {name} must be null or a non-empty string")
    return value


def _required_bool(mapping: Mapping[str, object], name: str) -> bool:
    value = _field(mapping, name, context="probe report")
    if not isinstance(value, bool):
        raise ValueError(f"probe report field {name} must be a boolean")
    return value


def _required_int(mapping: Mapping[str, object], name: str) -> int:
    value = _field(mapping, name, context="probe report")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"probe report field {name} must be an integer")
    return value


def _optional_int(mapping: Mapping[str, object], name: str) -> int | None:
    value = _field(mapping, name, context="probe report")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"probe report field {name} must be null or an integer")
    return value


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("probe report contains an invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("probe report timestamp must include timezone information")
    return parsed.astimezone(UTC)


def parse_market_data_probe_report(value: str | bytes) -> MarketDataProbeReport:
    try:
        raw = cast(object, json.loads(value))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("probe report is not valid JSON") from exc
    root = _mapping(raw, context="probe report")
    raw_results = _list(_field(root, "results", context="probe report"), context="results")
    results: list[MarketDataProbeResult] = []
    for raw_result in raw_results:
        item = _mapping(raw_result, context="probe result")
        try:
            outcome = MarketDataProbeOutcome(_required_text(item, "outcome"))
        except ValueError as exc:
            raise ValueError("probe report contains an unsupported outcome") from exc
        results.append(
            MarketDataProbeResult(
                provider_id=_required_text(item, "provider_id"),
                display_name=_required_text(item, "display_name"),
                endpoint_host=_required_text(item, "endpoint_host"),
                endpoint_path=_required_text(item, "endpoint_path"),
                market=_required_text(item, "market"),
                timeframe=_required_text(item, "timeframe"),
                observed_at=_parse_datetime(_required_text(item, "observed_at")),
                outcome=outcome,
                dns_latency_ms=_optional_int(item, "dns_latency_ms"),
                resolved_address_count=_optional_int(item, "resolved_address_count"),
                tls_latency_ms=_optional_int(item, "tls_latency_ms"),
                tls_version=_optional_text(item, "tls_version"),
                http_latency_ms=_optional_int(item, "http_latency_ms"),
                http_status_code=_optional_int(item, "http_status_code"),
                response_bytes=_optional_int(item, "response_bytes"),
                payload_valid=_required_bool(item, "payload_valid"),
                candle_count=_optional_int(item, "candle_count"),
                error_detail=_optional_text(item, "error_detail"),
            )
        )

    return MarketDataProbeReport(
        schema_version=_required_int(root, "schema_version"),
        is_synthetic=_required_bool(root, "is_synthetic"),
        environment_label=_required_text(root, "environment_label"),
        generated_at=_parse_datetime(_required_text(root, "generated_at")),
        results=tuple(results),
    )
