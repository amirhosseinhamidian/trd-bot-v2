import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db.candidate_journal_repositories import (
    SqlAlchemyCandidateJournalRepository,
)
from trd_bot.db.candidate_projection_rebuild import (
    SqlAlchemyCandidateProjectionRebuilder,
)
from trd_bot.db.dataset_file_stage_repositories import (
    SqlAlchemyDatasetFileStageRepository,
)
from trd_bot.db.session import get_session_factory
from trd_bot.release_maintenance import RELEASE_MAINTENANCE_POLICY_VERSION


@dataclass(frozen=True)
class CandidateProjectionRebuildSummary:
    """Deterministic result of one candidate projection maintenance rebuild."""

    journal_count: int
    projection_count: int


@dataclass(frozen=True)
class DatasetStageCleanupSummary:
    """Bounded result for deleting expired temporary dataset bytes."""

    requested_by: str
    evaluated_at: datetime
    expired_before: int
    deleted_count: int
    remaining_expired: int
    batch_limit: int


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


def cleanup_expired_dataset_stages(
    session_factory: sessionmaker[Session],
    *,
    requested_by: str,
    batch_limit: int,
    now: datetime | None = None,
) -> DatasetStageCleanupSummary:
    actor = requested_by.strip()
    if not actor or len(actor) > 100:
        raise ValueError("dataset stage cleanup requester must be between 1 and 100 characters")
    if not 1 <= batch_limit <= 500:
        raise ValueError("dataset stage cleanup limit must be between 1 and 500")
    observed_at = now or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("dataset stage cleanup timestamp must include timezone")
    observed_at = observed_at.astimezone(UTC)
    with session_factory() as session:
        repository = SqlAlchemyDatasetFileStageRepository(session)
        expired_before = repository.count_expired(now=observed_at)
        deleted_count = repository.delete_expired(
            now=observed_at,
            limit=batch_limit,
        )
        remaining_expired = repository.count_expired(now=observed_at)
    return DatasetStageCleanupSummary(
        requested_by=actor,
        evaluated_at=observed_at,
        expired_before=expired_before,
        deleted_count=deleted_count,
        remaining_expired=remaining_expired,
        batch_limit=batch_limit,
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
    cleanup = subparsers.add_parser(
        "cleanup-expired-dataset-stages",
        help="Delete one bounded batch of expired temporary dataset uploads.",
    )
    cleanup.add_argument("--requested-by", required=True)
    cleanup.add_argument("--batch-limit", type=int, default=100)
    cleanup.add_argument(
        "--confirm-policy-version",
        required=True,
        choices=(RELEASE_MAINTENANCE_POLICY_VERSION,),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "rebuild-candidate-projections":
        projection_summary = rebuild_candidate_projections(
            session_factory or get_session_factory(),
        )
        print(
            "candidate projection rebuild complete: "
            f"journals={projection_summary.journal_count} "
            f"projections={projection_summary.projection_count}"
        )
        return 0

    if args.command == "cleanup-expired-dataset-stages":
        cleanup_summary = cleanup_expired_dataset_stages(
            session_factory or get_session_factory(),
            requested_by=args.requested_by,
            batch_limit=args.batch_limit,
        )
        print(
            json.dumps(
                {
                    "batch_limit": cleanup_summary.batch_limit,
                    "deleted_count": cleanup_summary.deleted_count,
                    "evaluated_at": cleanup_summary.evaluated_at.isoformat(),
                    "expired_before": cleanup_summary.expired_before,
                    "policy_version": RELEASE_MAINTENANCE_POLICY_VERSION,
                    "remaining_expired": cleanup_summary.remaining_expired,
                    "requested_by": cleanup_summary.requested_by,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    raise ValueError(f"unsupported maintenance command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
