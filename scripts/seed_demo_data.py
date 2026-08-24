from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import sin, tau

from fastapi.testclient import TestClient
from sqlalchemy.engine import URL, make_url

from trd_bot.core.config import Settings
from trd_bot.main import app

PRICE_QUANTUM = Decimal("0.00000001")
CANDLE_COUNT = 360


@dataclass(frozen=True, slots=True)
class DemoMarket:
    """Configuration for one deterministic synthetic market."""

    base_asset: str
    quote_asset: str
    base_price: Decimal
    trend_per_candle: Decimal
    wave_amplitude: Decimal
    phase: int
    fast_period: int
    slow_period: int


DEMO_MARKETS = (
    DemoMarket(
        base_asset="BTC",
        quote_asset="USDT",
        base_price=Decimal("50000"),
        trend_per_candle=Decimal("5"),
        wave_amplitude=Decimal("1200"),
        phase=0,
        fast_period=9,
        slow_period=21,
    ),
    DemoMarket(
        base_asset="ETH",
        quote_asset="USDT",
        base_price=Decimal("3000"),
        trend_per_candle=Decimal("0.30"),
        wave_amplitude=Decimal("90"),
        phase=4,
        fast_period=12,
        slow_period=26,
    ),
    DemoMarket(
        base_asset="SOL",
        quote_asset="USDT",
        base_price=Decimal("150"),
        trend_per_candle=Decimal("0.02"),
        wave_amplitude=Decimal("6"),
        phase=8,
        fast_period=5,
        slow_period=15,
    ),
)


def validate_seed_target(settings: Settings) -> URL:
    """Prevent demo data from being inserted outside local development."""

    if settings.environment != "development":
        raise RuntimeError("demo seed may run only in the development environment")

    url = make_url(settings.database_url)

    if url.get_backend_name() != "postgresql":
        raise RuntimeError("demo seed requires PostgreSQL")

    if url.host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("demo seed may run only against local PostgreSQL")

    if url.database != "trd_bot":
        raise RuntimeError("demo seed may run only against the trd_bot database")

    return url


def serialize_decimal(value: Decimal) -> str:
    """Return a stable decimal representation for API payloads."""

    return format(value.quantize(PRICE_QUANTUM), "f")


def build_candles(
    market: DemoMarket,
    *,
    candle_count: int = CANDLE_COUNT,
) -> list[dict[str, object]]:
    """Build deterministic synthetic closed OHLCV candles."""

    start_time = datetime(
        2025,
        1,
        1,
        tzinfo=UTC,
    ) + timedelta(days=market.phase)

    spread = max(
        market.base_price * Decimal("0.001"),
        Decimal("0.01"),
    )

    candles: list[dict[str, object]] = []
    previous_close = market.base_price

    for index in range(candle_count):
        open_time = start_time + timedelta(hours=index)
        close_time = open_time + timedelta(hours=1)

        cycle_position = ((index + market.phase) % 48) / 48

        wave = Decimal(
            str(
                round(
                    sin(cycle_position * tau) * float(market.wave_amplitude),
                    8,
                )
            )
        )

        close_price = (
            market.base_price + market.trend_per_candle * Decimal(index) + wave
        ).quantize(PRICE_QUANTUM)

        open_price = previous_close.quantize(PRICE_QUANTUM)

        high_price = (max(open_price, close_price) + spread).quantize(PRICE_QUANTUM)

        low_price = (min(open_price, close_price) - spread).quantize(PRICE_QUANTUM)

        volume = Decimal("1000") + Decimal(index * 3) + Decimal(market.phase * 10)

        candles.append(
            {
                "source": "synthetic-demo",
                "pair": {
                    "base_asset": market.base_asset,
                    "quote_asset": market.quote_asset,
                    "market_type": "spot",
                },
                "timeframe": "1h",
                "open_time": open_time.isoformat(),
                "close_time": close_time.isoformat(),
                "received_at": (close_time + timedelta(seconds=2)).isoformat(),
                "open_price": serialize_decimal(open_price),
                "high_price": serialize_decimal(high_price),
                "low_price": serialize_decimal(low_price),
                "close_price": serialize_decimal(close_price),
                "volume": serialize_decimal(volume),
                "is_closed": True,
            }
        )

        previous_close = close_price

    return candles


def build_experiment_payload(
    market: DemoMarket,
    candles: list[dict[str, object]],
    *,
    fast_period: int,
    slow_period: int,
    horizon_candles: int,
) -> dict[str, object]:
    """Build one historical synthetic experiment request."""

    return {
        "dataset_name": (f"SYNTHETIC DEMO {market.base_asset}/{market.quote_asset} 1h"),
        "candles": candles,
        "fast_period": fast_period,
        "slow_period": slow_period,
        "horizon_candles": horizon_candles,
        "starting_balance": "10000",
        "allocation_fraction": "0.10",
        "fee_rate": "0.001",
        "slippage_rate": "0.0005",
    }


def build_walk_forward_payload(
    market: DemoMarket,
    candles: list[dict[str, object]],
) -> dict[str, object]:
    """Build one synthetic walk-forward request."""

    payload = build_experiment_payload(
        market,
        candles,
        fast_period=market.fast_period,
        slow_period=market.slow_period,
        horizon_candles=1,
    )

    payload.update(
        {
            "train_candles": 180,
            "test_candles": 60,
            "step_candles": 60,
            "gap_candles": 1,
            "mode": "rolling",
        }
    )

    return payload


def create_resource(
    client: TestClient,
    *,
    path: str,
    payload: dict[str, object],
    id_field: str,
) -> str:
    """Create one API resource and return its identifier."""

    response = client.post(
        path,
        json=payload,
    )

    if not response.is_success:
        raise RuntimeError(f"seed request failed: {response.status_code} {response.text}")

    data = response.json()
    resource_id = data.get(id_field)

    if not isinstance(resource_id, str):
        raise RuntimeError(f"seed response does not contain {id_field}")

    return resource_id


def main() -> None:
    """Populate the local database with deterministic demo research data."""

    settings = Settings()
    database_url = validate_seed_target(settings)

    print(
        "Seeding synthetic research data into:",
        database_url.render_as_string(hide_password=True),
    )

    created_experiments: list[str] = []
    created_walk_forward_runs: list[str] = []

    with TestClient(app) as client:
        for market in DEMO_MARKETS:
            candles = build_candles(market)

            primary_experiment_id = create_resource(
                client,
                path="/api/v1/research/experiments/ema-crossover",
                payload=build_experiment_payload(
                    market,
                    candles,
                    fast_period=market.fast_period,
                    slow_period=market.slow_period,
                    horizon_candles=1,
                ),
                id_field="experiment_id",
            )

            alternate_experiment_id = create_resource(
                client,
                path="/api/v1/research/experiments/ema-crossover",
                payload=build_experiment_payload(
                    market,
                    candles,
                    fast_period=max(2, market.fast_period - 2),
                    slow_period=market.slow_period + 4,
                    horizon_candles=3,
                ),
                id_field="experiment_id",
            )

            walk_forward_id = create_resource(
                client,
                path=("/api/v1/research/walk-forward/runs/ema-crossover"),
                payload=build_walk_forward_payload(
                    market,
                    candles,
                ),
                id_field="execution_id",
            )

            created_experiments.extend(
                [
                    primary_experiment_id,
                    alternate_experiment_id,
                ]
            )
            created_walk_forward_runs.append(walk_forward_id)

            print(f"Seeded {market.base_asset}/{market.quote_asset}")

    print()
    print(f"Experiments available: {len(created_experiments)}")
    print(
        "Walk-forward runs available:",
        len(created_walk_forward_runs),
    )
    print("Synthetic datasets expected: 3")
    print("Seed completed successfully.")


if __name__ == "__main__":
    main()
