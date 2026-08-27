import argparse
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db.candidate_journal_repositories import (
    SqlAlchemyCandidateJournalRepository,
)
from trd_bot.db.candidate_projection_rebuild import (
    SqlAlchemyCandidateProjectionRebuilder,
)
from trd_bot.db.session import get_session_factory


@dataclass(frozen=True)
class CandidateProjectionRebuildSummary:
    """Deterministic result of one candidate projection maintenance rebuild."""

    journal_count: int
    projection_count: int


def rebuild_candidate_projections(
    session_factory: sessionmaker[Session],
) -> CandidateProjectionRebuildSummary:
    """Rebuild the candidate read model from persisted journal source-of-truth."""

    with session_factory() as session:
        journal_count = SqlAlchemyCandidateJournalRepository(session).count()
        projections = SqlAlchemyCandidateProjectionRebuilder(session).rebuild()

    return CandidateProjectionRebuildSummary(
        journal_count=journal_count,
        projection_count=len(projections),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m trd_bot.maintenance",
        description="Offline maintenance commands for TRD Bot research persistence.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "rebuild-candidate-projections",
        help="Rebuild candidate projections from persisted candidate journals.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "rebuild-candidate-projections":
        summary = rebuild_candidate_projections(
            session_factory or get_session_factory(),
        )
        print(
            "candidate projection rebuild complete: "
            f"journals={summary.journal_count} "
            f"projections={summary.projection_count}"
        )
        return 0

    raise ValueError(f"unsupported maintenance command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
