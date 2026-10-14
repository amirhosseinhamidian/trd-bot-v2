#!/usr/bin/env python3
import argparse
import time
from datetime import UTC, datetime

from trd_bot.db import SqlAlchemyMarketDataPollingScheduler, get_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enqueue due durable market-data watchlist polling jobs."
    )
    parser.add_argument("--once", action="store_true", help="Schedule one due batch and exit.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.poll_seconds <= 0:
        raise SystemExit("poll interval must be positive")
    if not 1 <= args.batch_size <= 100:
        raise SystemExit("batch size must be between 1 and 100")

    session_factory = get_session_factory()
    while True:
        with session_factory() as session:
            SqlAlchemyMarketDataPollingScheduler(session).enqueue_due(
                now=datetime.now(UTC),
                limit=args.batch_size,
            )
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
