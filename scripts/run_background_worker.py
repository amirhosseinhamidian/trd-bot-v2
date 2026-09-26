#!/usr/bin/env python3
import argparse
import time
from datetime import timedelta
from socket import gethostname
from uuid import uuid4

from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import SqlAlchemyBackgroundJobRepository, get_session_factory
from trd_bot.jobs import BackgroundJobWorker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the durable TRD background worker.")
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--lease-seconds", type=int, default=60)
    parser.add_argument("--worker-id", default=f"{gethostname()}-{uuid4().hex[:8]}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.poll_seconds <= 0 or args.lease_seconds <= 0:
        raise SystemExit("poll and lease durations must be positive")

    session_factory = get_session_factory()
    while True:
        with session_factory() as session:
            worker = BackgroundJobWorker(
                repository=SqlAlchemyBackgroundJobRepository(session),
                handlers=build_background_job_handler_registry(),
                worker_id=args.worker_id,
                lease_duration=timedelta(seconds=args.lease_seconds),
            )
            job = worker.run_once()
        if args.once:
            return 0
        if job is None:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
