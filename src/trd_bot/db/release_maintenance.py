from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trd_bot.db.alert_publication import SqlAlchemyAlertPublicationRepository
from trd_bot.db.candidate_journal_repositories import (
    SqlAlchemyCandidateJournalRepository,
)
from trd_bot.db.candidate_projection_repositories import (
    SqlAlchemyCandidateProjectionRepository,
)
from trd_bot.db.dataset_file_stage_repositories import (
    SqlAlchemyDatasetFileStageRepository,
)
from trd_bot.db.market_data_retention import SqlAlchemyMarketDataRetentionManager
from trd_bot.db.models import CandidateJournalRow, CandidateProjectionRow
from trd_bot.market_data import MarketDataRetentionMode
from trd_bot.release_maintenance import (
    ReleaseMaintenancePlan,
    ReleaseMaintenancePolicy,
    ReleaseMaintenanceSnapshot,
    build_release_maintenance_plan,
    default_release_maintenance_policy,
)


class SqlAlchemyReleaseMaintenancePlanner:
    """Persist one retention dry-run audit and inspect all other maintenance scopes."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def plan(
        self,
        *,
        environment_label: str,
        commit_sha: str,
        requested_by: str,
        generated_at: datetime | None = None,
        policy: ReleaseMaintenancePolicy | None = None,
    ) -> ReleaseMaintenancePlan:
        timestamp = _timestamp(generated_at or datetime.now(UTC))
        active_policy = policy or default_release_maintenance_policy()
        retention = SqlAlchemyMarketDataRetentionManager(self._session).run(
            mode=MarketDataRetentionMode.DRY_RUN,
            requested_by=requested_by,
            batch_limit=active_policy.market_data_batch_limit,
            now=timestamp,
        )
        alert_expiry = SqlAlchemyAlertPublicationRepository(self._session).expiry_summary(
            evaluated_at=timestamp
        )
        journal_repository = SqlAlchemyCandidateJournalRepository(self._session)
        projection_repository = SqlAlchemyCandidateProjectionRepository(self._session)
        snapshot = ReleaseMaintenanceSnapshot(
            evaluated_at=timestamp,
            market_data_retention_plan=retention,
            expired_dataset_stages=SqlAlchemyDatasetFileStageRepository(
                self._session
            ).count_expired(now=timestamp),
            alert_expiry=alert_expiry,
            candidate_journals=journal_repository.count(),
            candidate_projections=projection_repository.count(),
            latest_candidate_journal_at=_optional_timestamp(
                self._session.scalar(select(func.max(CandidateJournalRow.recorded_at)))
            ),
            latest_candidate_projection_at=_optional_timestamp(
                self._session.scalar(select(func.max(CandidateProjectionRow.latest_recorded_at)))
            ),
        )
        return build_release_maintenance_plan(
            environment_label=environment_label,
            commit_sha=commit_sha,
            generated_at=timestamp,
            snapshot=snapshot,
            policy=active_policy,
        )


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("release maintenance timestamp must include timezone")
    return value.astimezone(UTC)


def _optional_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
