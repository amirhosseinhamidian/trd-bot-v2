from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.market_data_event_repositories import SqlAlchemyMarketDataEventStore
from trd_bot.db.models import MarketDataReplayRequestRow, MarketDataWindowRevisionRow
from trd_bot.jobs import BackgroundJobBuilder, BackgroundJobKind
from trd_bot.market_data.events import MarketDataEventDisposition
from trd_bot.market_data.replay import (
    MarketDataReplayRequest,
    MarketDataWindowRevision,
    build_revised_market_data_window,
)
from trd_bot.market_data.replay_jobs import (
    MarketDataReplayEnqueueResult,
    MarketDataReplayJobPayload,
    build_market_data_replay_idempotency_key,
    validate_market_data_replay_enqueue,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-data replay time must include timezone information")
    return value.astimezone(UTC)


class MarketDataReplayError(RuntimeError):
    """A replay could not be committed safely and may be retried."""


class MarketDataReplayRejectedError(MarketDataReplayError):
    """A replay request violates persisted lineage and must not be retried."""


class SqlAlchemyMarketDataReplayRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def stage(
        self,
        request: MarketDataReplayRequest,
    ) -> tuple[MarketDataReplayRequest, bool]:
        existing = self.get(request.replay_id)
        if existing is not None:
            if existing != request:
                raise ValueError("market-data replay ID already exists with different content")
            return existing, False
        by_decision = self.get_by_decision(request.decision_id)
        if by_decision is not None:
            if by_decision != request:
                raise ValueError("market-data decision already has another replay request")
            return by_decision, False

        self._session.add(
            MarketDataReplayRequestRow(
                replay_id=request.replay_id,
                schema_version=request.schema_version,
                decision_id=request.decision_id,
                observation_id=request.observation_id,
                event_id=request.event_id,
                window_id=request.window_id,
                reason=request.reason.value,
                requested_by=request.requested_by,
                requested_at=request.requested_at,
                payload_json=request.model_dump_json(),
            )
        )
        self._session.flush()
        return request, True

    def get(
        self,
        replay_id: str,
        *,
        for_update: bool = False,
    ) -> MarketDataReplayRequest | None:
        statement = select(MarketDataReplayRequestRow).where(
            MarketDataReplayRequestRow.replay_id == replay_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = self._session.scalar(statement)
        return (
            None if row is None else MarketDataReplayRequest.model_validate_json(row.payload_json)
        )

    def get_by_decision(self, decision_id: str) -> MarketDataReplayRequest | None:
        row = self._session.scalar(
            select(MarketDataReplayRequestRow).where(
                MarketDataReplayRequestRow.decision_id == decision_id
            )
        )
        return (
            None if row is None else MarketDataReplayRequest.model_validate_json(row.payload_json)
        )


class SqlAlchemyMarketDataWindowRevisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def stage(
        self,
        revision: MarketDataWindowRevision,
    ) -> tuple[MarketDataWindowRevision, bool]:
        existing = self.get(revision.revision_id)
        if existing is not None:
            if existing != revision:
                raise ValueError("market-data revision ID already exists with different content")
            return existing, False
        by_replay = self.get_by_replay(revision.replay_id)
        if by_replay is not None:
            if by_replay != revision:
                raise ValueError("market-data replay already produced another revision")
            return by_replay, False

        self._session.add(
            MarketDataWindowRevisionRow(
                revision_id=revision.revision_id,
                schema_version=revision.schema_version,
                replay_id=revision.replay_id,
                decision_id=revision.decision_id,
                observation_id=revision.observation_id,
                event_id=revision.event_id,
                window_id=revision.window_id,
                reason=revision.reason.value,
                kind=revision.kind.value,
                previous_version=revision.previous_version,
                previous_event_id=revision.previous_event_id,
                previous_payload_checksum=revision.previous_payload_checksum,
                revised_version=revision.revised_version,
                revised_payload_checksum=revision.revised_payload_checksum,
                watermark_id=revision.watermark_id,
                watermark_version=revision.watermark_version,
                watermark_time=revision.watermark_time,
                applied_at=revision.applied_at,
                payload_json=revision.model_dump_json(),
            )
        )
        self._session.flush()
        return revision, True

    def get(self, revision_id: str) -> MarketDataWindowRevision | None:
        row = self._session.get(MarketDataWindowRevisionRow, revision_id)
        return (
            None if row is None else MarketDataWindowRevision.model_validate_json(row.payload_json)
        )

    def get_by_replay(self, replay_id: str) -> MarketDataWindowRevision | None:
        row = self._session.scalar(
            select(MarketDataWindowRevisionRow).where(
                MarketDataWindowRevisionRow.replay_id == replay_id
            )
        )
        return (
            None if row is None else MarketDataWindowRevision.model_validate_json(row.payload_json)
        )


class SqlAlchemyMarketDataReplayEnqueuer:
    """Atomically persist one explicit replay request and its durable job."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._store = SqlAlchemyMarketDataEventStore(session)
        self._requests = SqlAlchemyMarketDataReplayRequestRepository(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def enqueue(
        self,
        *,
        decision_id: str,
        requested_by: str,
        requested_at: datetime,
    ) -> MarketDataReplayEnqueueResult:
        normalized = _as_utc(requested_at)
        existing_request = self._requests.get_by_decision(decision_id)
        if existing_request is not None:
            return self._existing_result(existing_request)

        decision = self._store.get_decision(decision_id)
        if decision is None:
            raise MarketDataReplayRejectedError("market-data replay decision does not exist")
        if (
            decision.decision.disposition is not MarketDataEventDisposition.REVISION_REQUIRED
            or not decision.decision.requires_replay
        ):
            raise MarketDataReplayRejectedError("market-data decision is not authorized for replay")
        request = MarketDataReplayRequest.from_decision(
            decision,
            requested_by=requested_by,
            requested_at=normalized,
        )
        job = BackgroundJobBuilder().build(
            kind=BackgroundJobKind.MARKET_DATA_REPLAY,
            payload=MarketDataReplayJobPayload(replay_id=request.replay_id).model_dump(mode="json"),
            idempotency_key=build_market_data_replay_idempotency_key(decision_id),
            now=normalized,
        )
        validate_market_data_replay_enqueue(request=request, job=job)

        try:
            self._requests.stage(request)
            stored_job, created = self._jobs.stage(job)
            if not created:
                raise MarketDataReplayError("replay job exists without its request")
            self._session.commit()
            return MarketDataReplayEnqueueResult(request=request, job=stored_job, created=True)
        except IntegrityError as error:
            self._session.rollback()
            existing = self._requests.get_by_decision(decision_id)
            if existing is not None:
                return self._existing_result(existing)
            raise MarketDataReplayError("market-data replay could not be enqueued") from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise MarketDataReplayError("market-data replay could not be enqueued") from error
        except Exception:
            self._session.rollback()
            raise

    def _existing_result(
        self,
        request: MarketDataReplayRequest,
    ) -> MarketDataReplayEnqueueResult:
        job = self._jobs.get_by_idempotency_key(
            kind=BackgroundJobKind.MARKET_DATA_REPLAY,
            idempotency_key=build_market_data_replay_idempotency_key(request.decision_id),
        )
        if job is None:
            raise MarketDataReplayError("replay request exists without its durable job")
        validate_market_data_replay_enqueue(request=request, job=job)
        return MarketDataReplayEnqueueResult(request=request, job=job, created=False)


class SqlAlchemyMarketDataReplayRunner:
    """Apply one authorized replay as an atomic append-only finalized revision."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._store = SqlAlchemyMarketDataEventStore(session)
        self._requests = SqlAlchemyMarketDataReplayRequestRepository(session)
        self._revisions = SqlAlchemyMarketDataWindowRevisionRepository(session)

    def apply(
        self,
        replay_id: str,
        *,
        applied_at: datetime,
    ) -> MarketDataWindowRevision:
        normalized = _as_utc(applied_at)
        for attempt in range(2):
            try:
                revision = self._apply_once(replay_id, applied_at=normalized)
                self._session.commit()
                return revision
            except IntegrityError as error:
                self._session.rollback()
                existing = self._revisions.get_by_replay(replay_id)
                if existing is not None:
                    return existing
                if attempt == 0:
                    continue
                raise MarketDataReplayError(
                    "concurrent market-data replay could not be resolved"
                ) from error
            except SQLAlchemyError as error:
                self._session.rollback()
                raise MarketDataReplayError("market-data replay transaction failed") from error
            except Exception:
                self._session.rollback()
                raise
        raise AssertionError("market-data replay retry loop did not return")

    def _apply_once(
        self,
        replay_id: str,
        *,
        applied_at: datetime,
    ) -> MarketDataWindowRevision:
        existing = self._revisions.get_by_replay(replay_id)
        if existing is not None:
            return existing
        request = self._requests.get(replay_id, for_update=True)
        if request is None:
            raise MarketDataReplayRejectedError("market-data replay request does not exist")
        existing = self._revisions.get_by_replay(replay_id)
        if existing is not None:
            return existing
        if applied_at < request.requested_at:
            raise MarketDataReplayRejectedError(
                "market-data replay cannot complete before it was requested"
            )

        decision_record = self._store.get_decision(request.decision_id)
        event_record = self._store.get_event(request.event_id)
        if decision_record is None or event_record is None:
            raise MarketDataReplayRejectedError("market-data replay lineage is incomplete")
        decision = decision_record.decision
        event = event_record.event
        if (
            decision_record.observation_id != request.observation_id
            or event_record.raw_observation_id != request.observation_id
            or decision.event_id != request.event_id
            or decision.window_id != request.window_id
            or decision.reason is not request.reason
            or not decision.requires_replay
        ):
            raise MarketDataReplayRejectedError("market-data replay lineage does not match")
        watermark = self._store.get_watermark(decision_record.watermark_id)
        if watermark is None:
            raise MarketDataReplayRejectedError("market-data replay watermark does not exist")

        previous = self._store.get_latest_window(request.window_id, for_update=True)
        current_version = None if previous is None else previous.version
        if current_version != decision.existing_window_version:
            raise MarketDataReplayRejectedError(
                "market-data replay source version is no longer current"
            )
        revised = build_revised_market_data_window(
            event=event,
            previous=previous,
            watermark=watermark,
            revised_at=applied_at,
        )
        if revised.version != decision.proposed_window_version:
            raise MarketDataReplayRejectedError(
                "market-data replay target version does not match its decision"
            )
        revision = MarketDataWindowRevision.build(
            request=request,
            event=event,
            previous=previous,
            revised=revised,
            watermark=watermark,
            applied_at=applied_at,
        )
        self._store.stage_window_version(revised)
        self._revisions.stage(revision)
        return revision
