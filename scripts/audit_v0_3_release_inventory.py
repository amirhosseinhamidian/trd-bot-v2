import argparse
import json
from pathlib import Path

from trd_bot.release_hardening import (
    build_release_hardening_report,
    serialize_release_hardening_report,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the deterministic v0.3 release surface and security boundary."
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=_REPOSITORY_ROOT,
        help="Repository root containing pyproject.toml, frontend, and alembic.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional new JSON report path. Existing files are never overwritten.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_release_hardening_report(args.repository_root)
    serialized = serialize_release_hardening_report(report) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    print(
        json.dumps(
            {
                "counts": report.inventory.counts,
                "failure_reasons": list(report.failure_reasons),
                "inventory_checksum": report.inventory.definition_checksum,
                "passed": report.passed,
                "product_version": report.inventory.product_version,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
