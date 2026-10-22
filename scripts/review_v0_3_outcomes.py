#!/usr/bin/env python3
import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine, make_url

from trd_bot.core.config import Settings
from trd_bot.db import create_database_engine, create_session_factory
from trd_bot.db.outcome_learning import SqlAlchemyOutcomeLearningReviewReader
from trd_bot.outcome_learning import serialize_outcome_learning_review

_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export an aggregate, read-only v0.3 outcome and learning review. "
            "No policy update or model training is performed."
        )
    )
    parser.add_argument("--database-url", default=Settings().database_url)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--commit-sha", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def validate_review_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if not normalized:
        raise ValueError("outcome learning review requires a database URL")
    if make_url(normalized).get_backend_name() != "postgresql":
        raise ValueError("outcome learning release review requires PostgreSQL")
    return normalized


def _commit_sha(explicit_sha: str | None) -> str:
    if explicit_sha is not None:
        return explicit_sha.strip().casefold()
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        cwd=_ROOT,
        text=True,
    )
    return result.stdout.strip().casefold()


def _assert_current_migration_head(engine: Engine) -> None:
    config = Config(str(_ROOT / "alembic.ini"))
    expected = tuple(sorted(ScriptDirectory.from_config(config).get_heads()))
    with engine.connect() as connection:
        current = tuple(sorted(MigrationContext.configure(connection).get_current_heads()))
    if current != expected:
        raise ValueError(
            "outcome learning database is not at repository migration head: "
            f"current={current}, expected={expected}"
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")
    engine = create_database_engine(validate_review_database_url(args.database_url))
    try:
        _assert_current_migration_head(engine)
        factory = create_session_factory(engine)
        with factory() as session:
            review = SqlAlchemyOutcomeLearningReviewReader(session).read(
                environment_label=args.environment_label,
                commit_sha=_commit_sha(args.commit_sha),
                generated_at=datetime.now(UTC),
            )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))
    finally:
        engine.dispose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_outcome_learning_review(review) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(
        json.dumps(
            {
                "commit_sha": review.commit_sha,
                "human_review_required": review.human_review_required,
                "policy_checksum": review.policy.definition_checksum,
                "readiness": review.readiness.value,
                "report_checksum": review.report_checksum,
                "sample_gaps": list(review.sample_gaps),
                "signal_count": len(review.signals),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
