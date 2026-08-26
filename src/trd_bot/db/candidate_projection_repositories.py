from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import CandidateProjectionRow
from trd_bot.research.candidate_projection import CandidateProjection


class SqlAlchemyCandidateProjectionRepository:
    """Persist rebuildable candidate projections for efficient read queries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        projection: CandidateProjection,
        *,
        commit: bool = True,
    ) -> CandidateProjection:
        row = self._session.get(
            CandidateProjectionRow,
            projection.candidate.candidate_id,
        )

        if row is None:
            self._session.add(self._build_row(projection))
        else:
            self._update_row(row=row, projection=projection)

        try:
            self._session.flush()
            if commit:
                self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValueError("candidate projection could not be persisted") from error

        return projection

    def get(self, candidate_id: str) -> CandidateProjection | None:
        row = self._session.get(CandidateProjectionRow, candidate_id)
        if row is None:
            return None

        return CandidateProjection.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(CandidateProjectionRow))
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[CandidateProjection, ...]:
        self._validate_pagination(limit=limit, offset=offset)

        rows = self._session.scalars(
            select(CandidateProjectionRow)
            .order_by(
                CandidateProjectionRow.latest_recorded_at.desc(),
                CandidateProjectionRow.latest_journal_id.desc(),
                CandidateProjectionRow.candidate_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(CandidateProjection.model_validate_json(row.payload_json) for row in rows)

    @staticmethod
    def _build_row(
        projection: CandidateProjection,
    ) -> CandidateProjectionRow:
        row = CandidateProjectionRow(
            candidate_id=projection.candidate.candidate_id,
            payload_json="",
        )
        SqlAlchemyCandidateProjectionRepository._update_row(
            row=row,
            projection=projection,
        )
        return row

    @staticmethod
    def _update_row(
        *,
        row: CandidateProjectionRow,
        projection: CandidateProjection,
    ) -> None:
        candidate = projection.candidate
        latest = projection.latest

        row.dataset_id = candidate.dataset_id
        row.experiment_id = candidate.experiment_id
        row.signal_id = candidate.signal_id
        row.latest_journal_id = latest.journal_id
        row.latest_recorded_at = latest.recorded_at
        row.status = candidate.status.value
        row.action = candidate.action.value
        row.base_asset = candidate.pair.base_asset
        row.quote_asset = candidate.pair.quote_asset
        row.market_type = candidate.pair.market_type.value
        row.timeframe = candidate.timeframe.value
        row.strategy_name = candidate.strategy_name
        row.strategy_version = candidate.strategy_version
        row.created_at = candidate.created_at
        row.valid_until = candidate.valid_until
        row.confidence = candidate.confidence
        row.signal_score = candidate.signal_score
        row.occurrence_count = len(projection.history)
        row.latest_rank = latest.rank
        row.latest_ranking_score = latest.ranking_score
        row.latest_replay_status = latest.replay_status.value
        row.latest_risk_decision = latest.risk_decision.value
        row.selected = int(latest.selected)
        row.position_id = latest.position_id
        row.exit_reason = latest.exit_reason.value if latest.exit_reason is not None else None
        row.payload_json = projection.model_dump_json()

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")
