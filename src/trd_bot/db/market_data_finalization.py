from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from trd_bot.db.market_data_event_repositories import SqlAlchemyMarketDataEventStore
from trd_bot.db.models import MarketDataWindowFinalizationRow
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data.events import MarketDataWindowState
from trd_bot.market_data.finalization import MarketDataWindowFinalization
from trd_bot.market_data.service_levels import (
    MarketDataServiceLevelPolicy,
    default_market_data_service_level_policy,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("window finalization time must include timezone information")
    return value.astimezone(UTC)


class MarketDataWindowFinalizationError(RuntimeError):
    """A finalization batch could not be committed safely."""


class MarketDataWindowFinalizationWatermarkMissingError(MarketDataWindowFinalizationError):
    """The requested stream has no persisted watermark revision."""


class SqlAlchemyMarketDataWindowFinalizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def stage(
        self,
        evidence: MarketDataWindowFinalization,
    ) -> tuple[MarketDataWindowFinalization, bool]:
        existing = self.get(evidence.finalization_id)
        if existing is not None:
            if existing != evidence:
                raise ValueError("window finalization ID already exists with different content")
            return existing, False

        existing_version = self.get_by_window_version(
            window_id=evidence.window_id,
            finalized_version=evidence.finalized_version,
        )
        if existing_version is not None:
            if existing_version != evidence:
                raise ValueError("window version already has different finalization evidence")
            return existing_version, False

        self._session.add(
            MarketDataWindowFinalizationRow(
                finalization_id=evidence.finalization_id,
                schema_version=evidence.schema_version,
                window_id=evidence.window_id,
                source=evidence.source,
                base_asset=evidence.pair.base_asset,
                quote_asset=evidence.pair.quote_asset,
                market_type=evidence.pair.market_type.value,
                timeframe=evidence.timeframe.value,
                provisional_version=evidence.provisional_version,
                finalized_version=evidence.finalized_version,
                event_id=evidence.event_id,
                payload_checksum=evidence.payload_checksum,
                watermark_id=evidence.watermark_id,
                watermark_version=evidence.watermark_version,
                policy_version=evidence.policy_version,
                window_end=evidence.window_end,
                watermark_time=evidence.watermark_time,
                finalized_at=evidence.finalized_at,
                freshness_seconds=evidence.freshness_seconds,
                freshness_target_seconds=evidence.freshness_target_seconds,
                freshness_outcome=evidence.freshness_outcome.value,
                payload_json=evidence.model_dump_json(),
            )
        )
        self._session.flush()
        return evidence, True

    def get(self, finalization_id: str) -> MarketDataWindowFinalization | None:
        row = self._session.get(MarketDataWindowFinalizationRow, finalization_id)
        return None if row is None else self._to_model(row)

    def get_by_window_version(
        self,
        *,
        window_id: str,
        finalized_version: int,
    ) -> MarketDataWindowFinalization | None:
        row = self._session.scalar(
            select(MarketDataWindowFinalizationRow).where(
                MarketDataWindowFinalizationRow.window_id == window_id,
                MarketDataWindowFinalizationRow.finalized_version == finalized_version,
            )
        )
        return None if row is None else self._to_model(row)

    @staticmethod
    def _to_model(row: MarketDataWindowFinalizationRow) -> MarketDataWindowFinalization:
        return MarketDataWindowFinalization.model_validate_json(row.payload_json)


class SqlAlchemyMarketDataWindowFinalizer:
    """Finalize eligible latest window versions in one atomic stream transaction."""

    def __init__(
        self,
        session: Session,
        *,
        policy: MarketDataServiceLevelPolicy | None = None,
    ) -> None:
        self._session = session
        self._store = SqlAlchemyMarketDataEventStore(session)
        self._evidence = SqlAlchemyMarketDataWindowFinalizationRepository(session)
        self._policy = policy or default_market_data_service_level_policy()

    def finalize_eligible(
        self,
        *,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        finalized_at: datetime,
        limit: int = 100,
    ) -> tuple[MarketDataWindowFinalization, ...]:
        normalized = _as_utc(finalized_at)
        for attempt in range(2):
            try:
                evidence = self._finalize_once(
                    source=source,
                    pair=pair,
                    timeframe=timeframe,
                    finalized_at=normalized,
                    limit=limit,
                )
                self._session.commit()
                return evidence
            except IntegrityError as error:
                self._session.rollback()
                if attempt == 0:
                    continue
                raise MarketDataWindowFinalizationError(
                    "concurrent window finalization could not be resolved"
                ) from error
            except SQLAlchemyError as error:
                self._session.rollback()
                raise MarketDataWindowFinalizationError(
                    "window finalization transaction failed"
                ) from error
            except Exception:
                self._session.rollback()
                raise
        raise AssertionError("window finalization retry loop did not return")

    def _finalize_once(
        self,
        *,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        finalized_at: datetime,
        limit: int,
    ) -> tuple[MarketDataWindowFinalization, ...]:
        watermark = self._store.get_latest_watermark(
            source=source,
            pair=pair,
            timeframe=timeframe,
            for_update=True,
        )
        if watermark is None:
            raise MarketDataWindowFinalizationWatermarkMissingError(
                "market-data stream has no persisted watermark"
            )
        service_level = self._policy.for_timeframe(timeframe)
        if (
            watermark.policy_version != self._policy.schema_version
            or watermark.watermark.allowed_lateness_seconds
            != service_level.allowed_lateness_seconds
        ):
            raise MarketDataWindowFinalizationError(
                "watermark revision does not match the active service-level policy"
            )

        candidate_ids = self._store.list_finalization_candidate_ids(
            source=source,
            pair=pair,
            timeframe=timeframe,
            watermark_time=watermark.watermark.watermark_time,
            limit=limit,
        )
        results: list[MarketDataWindowFinalization] = []
        for window_id in candidate_ids:
            provisional = self._store.get_latest_window(window_id, for_update=True)
            if provisional is None or provisional.state is MarketDataWindowState.FINALIZED:
                continue
            if (
                provisional.source != source
                or provisional.pair != pair
                or provisional.timeframe is not timeframe
            ):
                raise MarketDataWindowFinalizationError(
                    "window candidate changed stream during finalization"
                )
            if not provisional.candle.is_closed or provisional.window_end > finalized_at:
                continue

            finalized = provisional.finalize(
                watermark.watermark,
                finalized_at=finalized_at,
            )
            evidence = MarketDataWindowFinalization.build(
                provisional=provisional,
                finalized=finalized,
                watermark=watermark,
                freshness_target_seconds=service_level.finalized_freshness_p95_seconds,
            )
            self._store.stage_window_version(finalized)
            self._evidence.stage(evidence)
            results.append(evidence)
        return tuple(results)
