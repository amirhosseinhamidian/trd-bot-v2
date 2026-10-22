#!/usr/bin/env python3
import argparse
import json
from typing import Literal

from trd_bot.db import (
    MarketDataRetentionHoldNotFoundError,
    SqlAlchemyMarketDataRetentionManager,
    get_session_factory,
)
from trd_bot.market_data import (
    MarketDataRetentionHoldKind,
    MarketDataRetentionMode,
    MarketDataRetentionOutcome,
)

POLICY_VERSION = "market-data-service-level-policy-v1"


def _add_requester(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--requested-by",
        required=True,
        help="Auditable operator identity; do not provide a credential or secret.",
    )


def _add_batch_limit(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--batch-limit",
        type=int,
        default=100,
        help="Shared maximum rows selected across all retention scopes (1-500).",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or execute audited market-data retention batches.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="Persist a dry-run audit without deleting rows.")
    _add_requester(plan)
    _add_batch_limit(plan)

    execute = commands.add_parser(
        "execute",
        help="Execute one bounded purge batch after an explicit policy confirmation.",
    )
    _add_requester(execute)
    _add_batch_limit(execute)
    execute.add_argument(
        "--confirm-policy-version",
        required=True,
        choices=(POLICY_VERSION,),
    )

    place_hold = commands.add_parser(
        "place-hold",
        help="Place a legal or incident hold that blocks plan and execute modes.",
    )
    _add_requester(place_hold)
    place_hold.add_argument(
        "--kind",
        required=True,
        choices=tuple(item.value for item in MarketDataRetentionHoldKind),
    )
    place_hold.add_argument("--reason", required=True)

    release_hold = commands.add_parser("release-hold", help="Release one existing hold.")
    _add_requester(release_hold)
    release_hold.add_argument("--hold-id", required=True)

    commands.add_parser("list-holds", help="List active retention holds.")
    list_runs = commands.add_parser("list-runs", help="List recent retention audit runs.")
    list_runs.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum audit runs to return (1-100).",
    )
    return parser.parse_args(argv)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _run_mode(
    mode: Literal["dry_run", "execute"],
    *,
    requested_by: str,
    batch_limit: int,
) -> int:
    with get_session_factory()() as session:
        result = SqlAlchemyMarketDataRetentionManager(session).run(
            mode=MarketDataRetentionMode(mode),
            requested_by=requested_by,
            batch_limit=batch_limit,
        )
    print(_json(result.model_dump(mode="json")))
    if result.outcome is MarketDataRetentionOutcome.FAILED:
        return 2
    if result.outcome is MarketDataRetentionOutcome.BLOCKED:
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "plan":
        return _run_mode(
            "dry_run",
            requested_by=args.requested_by,
            batch_limit=args.batch_limit,
        )
    if args.command == "execute":
        return _run_mode(
            "execute",
            requested_by=args.requested_by,
            batch_limit=args.batch_limit,
        )
    if args.command == "place-hold":
        with get_session_factory()() as session:
            hold = SqlAlchemyMarketDataRetentionManager(session).place_hold(
                kind=MarketDataRetentionHoldKind(args.kind),
                reason=args.reason,
                requested_by=args.requested_by,
            )
        print(_json(hold.model_dump(mode="json")))
        return 0
    if args.command == "release-hold":
        try:
            with get_session_factory()() as session:
                hold = SqlAlchemyMarketDataRetentionManager(session).release_hold(
                    args.hold_id,
                    requested_by=args.requested_by,
                )
        except MarketDataRetentionHoldNotFoundError:
            print(_json({"error_code": "retention_hold_not_found"}))
            return 2
        print(_json(hold.model_dump(mode="json")))
        return 0

    with get_session_factory()() as session:
        manager = SqlAlchemyMarketDataRetentionManager(session)
        items = (
            manager.list_active_holds()
            if args.command == "list-holds"
            else manager.list_runs(limit=args.limit)
        )
    print(_json([item.model_dump(mode="json") for item in items]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
