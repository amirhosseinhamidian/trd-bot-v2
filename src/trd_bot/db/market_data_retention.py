from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, exists, literal, or_, select, tuple_
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql import Select

from trd_bot.db.base import DatabaseBase
from trd_bot.db.models import (
    BackgroundJobRow,
    MarketDataEventDecisionRow,
    MarketDataEventInboxRow,
    MarketDataEventRow,
    MarketDataOutboxRow,
    MarketDataRawObservationRow,
    MarketDataReplayRequestRow,
    MarketDataRetentionControlRow,
    MarketDataRetentionHoldRow,
    MarketDataRetentionRunRow,
    MarketDataWatermarkRow,
    MarketDataWindowFinalizationRow,
    MarketDataWindowRevisionRow,
    MarketDataWindowVersionRow,
)
from trd_bot.jobs import BackgroundJobKind, BackgroundJobStatus
from trd_bot.market_data.events import MarketDataWindowState
from trd_bot.market_data.retention import (
    MarketDataRetentionCounts,
    MarketDataRetentionCutoffs,
    MarketDataRetentionHold,
    MarketDataRetentionHoldKind,
    MarketDataRetentionMode,
    MarketDataRetentionOutcome,
    MarketDataRetentionRun,
)
from trd_bot.market_data.service_levels import (
    MarketDataServiceLevelPolicy,
    default_market_data_service_level_policy,
)

_CONTROL_ID = "market-data-retention-control"
_TERMINAL_JOB_STATUSES = (
    BackgroundJobStatus.SUCCEEDED.value,
    BackgroundJobStatus.FAILED.value,
    BackgroundJobStatus.CANCELLED.value,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-data retention time must include timezone information")
    return value.astimezone(UTC)


class MarketDataRetentionError(RuntimeError):
    """A bounded retention operation could not be audited safely."""


class MarketDataRetentionHoldNotFoundError(LookupError):
    """The requested retention hold does not exist."""


@dataclass(frozen=True)
class _CandidateBatch:
    delivered_outbox: tuple[str, ...] = ()
    failed_outbox: tuple[str, ...] = ()
    window_revisions: tuple[str, ...] = ()
    replay_requests: tuple[str, ...] = ()
    replay_request_decisions: tuple[str, ...] = ()
    provisional_windows: tuple[tuple[str, int], ...] = ()
    event_decisions: tuple[str, ...] = ()
    normalized_events: tuple[str, ...] = ()
    raw_observations: tuple[str, ...] = ()
    inbox_receipts: tuple[str, ...] = ()
    orphan_watermarks: tuple[str, ...] = ()

    @property
    def counts(self) -> MarketDataRetentionCounts:
        return MarketDataRetentionCounts(
            raw_observations=len(self.raw_observations),
            normalized_events=len(self.normalized_events),
            event_decisions=len(self.event_decisions),
            inbox_receipts=len(self.inbox_receipts),
            delivered_outbox=len(self.delivered_outbox),
            failed_outbox=len(self.failed_outbox),
            provisional_windows=len(self.provisional_windows),
            replay_requests=len(self.replay_requests),
            window_revisions=len(self.window_revisions),
            orphan_watermarks=len(self.orphan_watermarks),
        )


class SqlAlchemyMarketDataRetentionManager:
    """Serialize hold changes and execute one audited, shared-limit purge batch."""

    def __init__(
        self,
        session: Session,
        *,
        policy: MarketDataServiceLevelPolicy | None = None,
    ) -> None:
        self._session = session
        self._policy = policy or default_market_data_service_level_policy()

    def place_hold(
        self,
        *,
        kind: MarketDataRetentionHoldKind,
        reason: str,
        requested_by: str,
        now: datetime | None = None,
    ) -> MarketDataRetentionHold:
        placed_at = _as_utc(now or datetime.now(UTC))
        hold = MarketDataRetentionHold.place(
            kind=kind,
            reason=reason,
            placed_by=requested_by,
            placed_at=placed_at,
        )
        try:
            control = self._lock_control(placed_at)
            self._session.add(self._hold_row(hold))
            control.updated_at = placed_at
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise MarketDataRetentionError("retention hold could not be persisted") from error
        return hold

    def release_hold(
        self,
        hold_id: str,
        *,
        requested_by: str,
        now: datetime | None = None,
    ) -> MarketDataRetentionHold:
        released_at = _as_utc(now or datetime.now(UTC))
        try:
            control = self._lock_control(released_at)
            row = self._session.scalar(
                select(MarketDataRetentionHoldRow)
                .where(MarketDataRetentionHoldRow.hold_id == hold_id)
                .with_for_update()
            )
            if row is None:
                raise MarketDataRetentionHoldNotFoundError(
                    "market-data retention hold does not exist"
                )
            current = MarketDataRetentionHold.model_validate_json(row.payload_json)
            released = current.release(
                released_by=requested_by,
                released_at=released_at,
            )
            row.released_by = released.released_by
            row.released_at = released.released_at
            row.payload_json = released.model_dump_json()
            control.updated_at = released_at
            self._session.commit()
            return released
        except MarketDataRetentionHoldNotFoundError:
            self._session.rollback()
            raise
        except SQLAlchemyError as error:
            self._session.rollback()
            raise MarketDataRetentionError("retention hold could not be released") from error

    def list_active_holds(self) -> tuple[MarketDataRetentionHold, ...]:
        rows = self._session.scalars(
            select(MarketDataRetentionHoldRow)
            .where(MarketDataRetentionHoldRow.released_at.is_(None))
            .order_by(
                MarketDataRetentionHoldRow.placed_at,
                MarketDataRetentionHoldRow.hold_id,
            )
            .limit(100)
        ).all()
        return tuple(MarketDataRetentionHold.model_validate_json(row.payload_json) for row in rows)

    def list_runs(self, *, limit: int = 20) -> tuple[MarketDataRetentionRun, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("market-data retention run limit must be between 1 and 100")
        rows = self._session.scalars(
            select(MarketDataRetentionRunRow)
            .order_by(
                MarketDataRetentionRunRow.requested_at.desc(),
                MarketDataRetentionRunRow.run_id.desc(),
            )
            .limit(limit)
        ).all()
        return tuple(MarketDataRetentionRun.model_validate_json(row.payload_json) for row in rows)

    def run(
        self,
        *,
        mode: MarketDataRetentionMode,
        requested_by: str,
        batch_limit: int,
        now: datetime | None = None,
    ) -> MarketDataRetentionRun:
        requested_at = _as_utc(now or datetime.now(UTC))
        if not 1 <= batch_limit <= 500:
            raise ValueError("market-data retention batch limit must be between 1 and 500")
        if not requested_by.strip():
            raise ValueError("market-data retention requester cannot be empty")
        run_id = MarketDataRetentionRun.build_run_id(
            requested_by=requested_by,
            requested_at=requested_at,
        )
        cutoffs = self._cutoffs(requested_at)

        try:
            control = self._lock_control(requested_at)
            holds = self._active_holds_for_update()
            if holds:
                run = MarketDataRetentionRun(
                    run_id=run_id,
                    mode=mode,
                    outcome=MarketDataRetentionOutcome.BLOCKED,
                    requested_by=requested_by,
                    requested_at=requested_at,
                    completed_at=requested_at,
                    batch_limit=batch_limit,
                    cutoffs=cutoffs,
                    selected=MarketDataRetentionCounts(),
                    deleted_count=0,
                    blocking_hold_ids=tuple(item.hold_id for item in holds),
                )
            else:
                candidates = self._select_candidates(cutoffs=cutoffs, limit=batch_limit)
                deleted_count = (
                    0
                    if mode is MarketDataRetentionMode.DRY_RUN
                    else self._delete_candidates(candidates)
                )
                run = MarketDataRetentionRun(
                    run_id=run_id,
                    mode=mode,
                    outcome=MarketDataRetentionOutcome.COMPLETED,
                    requested_by=requested_by,
                    requested_at=requested_at,
                    completed_at=requested_at,
                    batch_limit=batch_limit,
                    cutoffs=cutoffs,
                    selected=candidates.counts,
                    deleted_count=deleted_count,
                )
            self._session.add(self._run_row(run))
            control.updated_at = requested_at
            self._session.commit()
            return run
        except (MarketDataRetentionError, SQLAlchemyError):
            self._session.rollback()
            failed = MarketDataRetentionRun(
                run_id=run_id,
                mode=mode,
                outcome=MarketDataRetentionOutcome.FAILED,
                requested_by=requested_by,
                requested_at=requested_at,
                completed_at=requested_at,
                batch_limit=batch_limit,
                cutoffs=cutoffs,
                selected=MarketDataRetentionCounts(),
                deleted_count=0,
                error_code="retention_transaction_failed",
            )
            try:
                self._session.add(self._run_row(failed))
                self._session.commit()
            except SQLAlchemyError as audit_error:
                self._session.rollback()
                raise MarketDataRetentionError(
                    "retention failure could not be audited"
                ) from audit_error
            return failed

    def _lock_control(self, now: datetime) -> MarketDataRetentionControlRow:
        row = self._session.scalar(
            select(MarketDataRetentionControlRow)
            .where(MarketDataRetentionControlRow.control_id == _CONTROL_ID)
            .with_for_update()
        )
        if row is None:
            row = MarketDataRetentionControlRow(control_id=_CONTROL_ID, updated_at=now)
            self._session.add(row)
            self._session.flush()
        return row

    def _active_holds_for_update(self) -> tuple[MarketDataRetentionHold, ...]:
        rows = self._session.scalars(
            select(MarketDataRetentionHoldRow)
            .where(MarketDataRetentionHoldRow.released_at.is_(None))
            .order_by(MarketDataRetentionHoldRow.placed_at, MarketDataRetentionHoldRow.hold_id)
            .with_for_update()
        ).all()
        return tuple(MarketDataRetentionHold.model_validate_json(row.payload_json) for row in rows)

    def _cutoffs(self, now: datetime) -> MarketDataRetentionCutoffs:
        retention = self._policy.retention
        return MarketDataRetentionCutoffs(
            raw_observations_before=now - timedelta(days=retention.raw_observation_days),
            normalized_events_before=now - timedelta(days=retention.normalized_event_days),
            inbox_receipts_before=now - timedelta(days=retention.inbox_deduplication_days),
            delivered_outbox_before=now - timedelta(days=retention.delivered_outbox_days),
            failed_outbox_before=now - timedelta(days=retention.failed_outbox_days),
            provisional_windows_finalized_before=now
            - timedelta(days=retention.provisional_window_days_after_finalization),
            revision_evidence_before=now - timedelta(days=retention.revision_evidence_days),
            orphan_watermarks_before=now - timedelta(days=retention.revision_evidence_days),
        )

    def _select_candidates(
        self,
        *,
        cutoffs: MarketDataRetentionCutoffs,
        limit: int,
    ) -> _CandidateBatch:
        remaining = limit

        def take_ids(statement: Select[tuple[str]]) -> tuple[str, ...]:
            nonlocal remaining
            if remaining == 0:
                return ()
            values = tuple(self._session.scalars(statement.limit(remaining)).all())
            remaining -= len(values)
            return values

        delivered_outbox = take_ids(
            select(MarketDataOutboxRow.outbox_id)
            .where(
                MarketDataOutboxRow.status == "delivered",
                MarketDataOutboxRow.delivered_at <= cutoffs.delivered_outbox_before,
            )
            .order_by(MarketDataOutboxRow.delivered_at, MarketDataOutboxRow.outbox_id)
        )
        failed_outbox = take_ids(
            select(MarketDataOutboxRow.outbox_id)
            .where(
                MarketDataOutboxRow.status == "failed",
                MarketDataOutboxRow.updated_at <= cutoffs.failed_outbox_before,
            )
            .order_by(MarketDataOutboxRow.updated_at, MarketDataOutboxRow.outbox_id)
        )
        window_revisions = take_ids(
            select(MarketDataWindowRevisionRow.revision_id)
            .where(MarketDataWindowRevisionRow.applied_at <= cutoffs.revision_evidence_before)
            .order_by(
                MarketDataWindowRevisionRow.applied_at,
                MarketDataWindowRevisionRow.revision_id,
            )
        )
        replay_rows: tuple[tuple[str, str], ...] = ()
        if remaining:
            replay_rows = tuple(
                self._session.execute(
                    select(
                        MarketDataReplayRequestRow.replay_id,
                        MarketDataReplayRequestRow.decision_id,
                    )
                    .join(
                        BackgroundJobRow,
                        (BackgroundJobRow.kind == BackgroundJobKind.MARKET_DATA_REPLAY.value)
                        & (
                            BackgroundJobRow.idempotency_key
                            == literal("market-data-replay:")
                            + MarketDataReplayRequestRow.decision_id
                        ),
                    )
                    .where(
                        MarketDataReplayRequestRow.requested_at <= cutoffs.revision_evidence_before,
                        BackgroundJobRow.status.in_(_TERMINAL_JOB_STATUSES),
                        ~exists().where(
                            MarketDataWindowRevisionRow.replay_id
                            == MarketDataReplayRequestRow.replay_id
                        ),
                    )
                    .order_by(
                        MarketDataReplayRequestRow.requested_at,
                        MarketDataReplayRequestRow.replay_id,
                    )
                    .limit(remaining)
                )
                .tuples()
                .all()
            )
            remaining -= len(replay_rows)
        replay_requests = tuple(item[0] for item in replay_rows)
        replay_request_decisions = tuple(item[1] for item in replay_rows)

        provisional_windows: tuple[tuple[str, int], ...] = ()
        if remaining:
            provisional_windows = tuple(
                self._session.execute(
                    select(
                        MarketDataWindowVersionRow.window_id,
                        MarketDataWindowVersionRow.version,
                    )
                    .where(
                        MarketDataWindowVersionRow.state == MarketDataWindowState.PROVISIONAL.value,
                        exists().where(
                            MarketDataWindowFinalizationRow.window_id
                            == MarketDataWindowVersionRow.window_id,
                            MarketDataWindowFinalizationRow.finalized_at
                            <= cutoffs.provisional_windows_finalized_before,
                        ),
                    )
                    .order_by(
                        MarketDataWindowVersionRow.created_at,
                        MarketDataWindowVersionRow.window_id,
                        MarketDataWindowVersionRow.version,
                    )
                    .limit(remaining)
                )
                .tuples()
                .all()
            )
            remaining -= len(provisional_windows)

        replay_decision_filter = (
            MarketDataEventDecisionRow.decision_id.in_(replay_request_decisions)
            if replay_request_decisions
            else MarketDataEventDecisionRow.decision_id.is_(None)
        )
        event_decisions = take_ids(
            select(MarketDataEventDecisionRow.decision_id)
            .where(
                MarketDataEventDecisionRow.decided_at <= cutoffs.normalized_events_before,
                or_(
                    (
                        MarketDataEventDecisionRow.requires_replay.is_(False)
                        & ~exists().where(
                            MarketDataReplayRequestRow.decision_id
                            == MarketDataEventDecisionRow.decision_id
                        )
                    ),
                    replay_decision_filter,
                ),
            )
            .order_by(
                MarketDataEventDecisionRow.decided_at,
                MarketDataEventDecisionRow.decision_id,
            )
        )
        normalized_events = take_ids(
            select(MarketDataEventRow.event_id)
            .where(
                MarketDataEventRow.persisted_at <= cutoffs.normalized_events_before,
                ~exists().where(MarketDataOutboxRow.event_id == MarketDataEventRow.event_id),
                ~exists().where(MarketDataEventDecisionRow.event_id == MarketDataEventRow.event_id),
            )
            .order_by(MarketDataEventRow.persisted_at, MarketDataEventRow.event_id)
        )
        raw_observations = take_ids(
            select(MarketDataRawObservationRow.observation_id)
            .where(MarketDataRawObservationRow.created_at <= cutoffs.raw_observations_before)
            .order_by(
                MarketDataRawObservationRow.created_at,
                MarketDataRawObservationRow.observation_id,
            )
        )
        inbox_receipts = take_ids(
            select(MarketDataEventInboxRow.idempotency_key)
            .where(MarketDataEventInboxRow.last_seen_at <= cutoffs.inbox_receipts_before)
            .order_by(
                MarketDataEventInboxRow.last_seen_at,
                MarketDataEventInboxRow.idempotency_key,
            )
        )
        orphan_watermarks = take_ids(
            select(MarketDataWatermarkRow.watermark_id)
            .where(
                MarketDataWatermarkRow.stored_at <= cutoffs.orphan_watermarks_before,
                ~exists().where(
                    MarketDataEventDecisionRow.watermark_id == MarketDataWatermarkRow.watermark_id
                ),
                ~exists().where(
                    MarketDataWindowFinalizationRow.watermark_id
                    == MarketDataWatermarkRow.watermark_id
                ),
                ~exists().where(
                    MarketDataWindowRevisionRow.watermark_id == MarketDataWatermarkRow.watermark_id
                ),
            )
            .order_by(MarketDataWatermarkRow.stored_at, MarketDataWatermarkRow.watermark_id)
        )
        return _CandidateBatch(
            delivered_outbox=delivered_outbox,
            failed_outbox=failed_outbox,
            window_revisions=window_revisions,
            replay_requests=replay_requests,
            replay_request_decisions=replay_request_decisions,
            provisional_windows=provisional_windows,
            event_decisions=event_decisions,
            normalized_events=normalized_events,
            raw_observations=raw_observations,
            inbox_receipts=inbox_receipts,
            orphan_watermarks=orphan_watermarks,
        )

    def _delete_candidates(self, candidates: _CandidateBatch) -> int:
        deleted = 0
        deleted += self._delete_ids(
            MarketDataOutboxRow,
            MarketDataOutboxRow.outbox_id,
            candidates.delivered_outbox + candidates.failed_outbox,
        )
        deleted += self._delete_ids(
            MarketDataWindowRevisionRow,
            MarketDataWindowRevisionRow.revision_id,
            candidates.window_revisions,
        )
        deleted += self._delete_ids(
            MarketDataReplayRequestRow,
            MarketDataReplayRequestRow.replay_id,
            candidates.replay_requests,
        )
        deleted += self._delete_ids(
            MarketDataEventDecisionRow,
            MarketDataEventDecisionRow.decision_id,
            candidates.event_decisions,
        )
        if candidates.provisional_windows:
            result = cast(
                CursorResult[Any],
                self._session.execute(
                    delete(MarketDataWindowVersionRow).where(
                        tuple_(
                            MarketDataWindowVersionRow.window_id,
                            MarketDataWindowVersionRow.version,
                        ).in_(candidates.provisional_windows)
                    )
                ),
            )
            deleted += int(result.rowcount or 0)
        deleted += self._delete_ids(
            MarketDataEventRow,
            MarketDataEventRow.event_id,
            candidates.normalized_events,
        )
        deleted += self._delete_ids(
            MarketDataRawObservationRow,
            MarketDataRawObservationRow.observation_id,
            candidates.raw_observations,
        )
        deleted += self._delete_ids(
            MarketDataEventInboxRow,
            MarketDataEventInboxRow.idempotency_key,
            candidates.inbox_receipts,
        )
        deleted += self._delete_ids(
            MarketDataWatermarkRow,
            MarketDataWatermarkRow.watermark_id,
            candidates.orphan_watermarks,
        )
        if deleted != candidates.counts.total:
            raise MarketDataRetentionError("retention delete count did not match its plan")
        return deleted

    def _delete_ids(
        self,
        row_type: type[DatabaseBase],
        column: InstrumentedAttribute[str],
        ids: tuple[str, ...],
    ) -> int:
        if not ids:
            return 0
        result = cast(
            CursorResult[Any],
            self._session.execute(delete(row_type).where(column.in_(ids))),
        )
        return int(result.rowcount or 0)

    @staticmethod
    def _hold_row(hold: MarketDataRetentionHold) -> MarketDataRetentionHoldRow:
        return MarketDataRetentionHoldRow(
            hold_id=hold.hold_id,
            schema_version=hold.schema_version,
            kind=hold.kind.value,
            reason=hold.reason,
            placed_by=hold.placed_by,
            placed_at=hold.placed_at,
            released_by=hold.released_by,
            released_at=hold.released_at,
            payload_json=hold.model_dump_json(),
        )

    @staticmethod
    def _run_row(run: MarketDataRetentionRun) -> MarketDataRetentionRunRow:
        return MarketDataRetentionRunRow(
            run_id=run.run_id,
            schema_version=run.schema_version,
            policy_version=run.policy_version,
            mode=run.mode.value,
            outcome=run.outcome.value,
            requested_by=run.requested_by,
            requested_at=run.requested_at,
            completed_at=run.completed_at,
            batch_limit=run.batch_limit,
            selected_count=run.selected.total,
            deleted_count=run.deleted_count,
            error_code=run.error_code,
            payload_json=run.model_dump_json(),
        )
