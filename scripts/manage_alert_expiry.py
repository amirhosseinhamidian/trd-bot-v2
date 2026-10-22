"""Inspect or materialize expired Alert Center lifecycle evidence."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from trd_bot.db import SqlAlchemyAlertPublicationRepository, get_session_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "execute"))
    parser.add_argument("--requested-by", required=True)
    parser.add_argument("--batch-limit", type=int, default=100)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    now = datetime.now(UTC)
    with get_session_factory()() as session:
        repository = SqlAlchemyAlertPublicationRepository(session)
        if arguments.mode == "plan":
            print(repository.expiry_summary(evaluated_at=now).model_dump_json(indent=2))
            return 0
        result = repository.sweep_expired(
            evaluated_at=now,
            recorded_by=arguments.requested_by,
            limit=arguments.batch_limit,
        )
        print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
