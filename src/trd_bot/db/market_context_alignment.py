from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, aliased

from trd_bot.db.market_context_repositories import SqlAlchemyMarketContextStore
from trd_bot.db.models import MarketDataWindowVersionRow
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_context import (
    MarketContextAlignmentResult,
    MarketContextAlignmentStatus,
    MarketContextFeatureSetDefinition,
    align_market_context_windows,
    default_market_context_alignment_policy,
    floor_market_context_boundary,
    required_market_context_window_counts,
)
from trd_bot.market_data.events import MarketDataWindowSnapshot, MarketDataWindowState


class SqlAlchemyMarketContextAssembler:
    """Read bounded finalized history and stage a reproducible input manifest."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._store = SqlAlchemyMarketContextStore(session)

    def assemble_and_stage(
        self,
        *,
        source: str,
        pair: TradingPair,
        as_of: datetime,
        feature_set: MarketContextFeatureSetDefinition,
        aligned_at: datetime,
    ) -> MarketContextAlignmentResult:
        policy = default_market_context_alignment_policy()
        counts = required_market_context_window_counts(feature_set, policy=policy)
        windows: list[MarketDataWindowSnapshot] = []
        for timeframe in policy.timeframes:
            windows.extend(
                self._latest_finalized_windows(
                    source=source,
                    pair=pair,
                    timeframe=timeframe,
                    window_end_or_before=floor_market_context_boundary(as_of, timeframe),
                    limit=counts[timeframe],
                )
            )

        result = align_market_context_windows(
            source=source,
            pair=pair,
            as_of=as_of,
            windows=tuple(windows),
            feature_set=feature_set,
            aligned_at=aligned_at,
            policy=policy,
        )
        if result.status is MarketContextAlignmentStatus.READY:
            if result.manifest is None:  # pragma: no cover - protected by result contract
                raise RuntimeError("ready alignment did not produce a manifest")
            self._store.stage_input_manifest(result.manifest)
        return result

    def _latest_finalized_windows(
        self,
        *,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        window_end_or_before: datetime,
        limit: int,
    ) -> tuple[MarketDataWindowSnapshot, ...]:
        candidate = aliased(MarketDataWindowVersionRow)
        newer = aliased(MarketDataWindowVersionRow)
        newer_finalized_version = exists(
            select(newer.window_id).where(
                newer.window_id == candidate.window_id,
                newer.state == MarketDataWindowState.FINALIZED.value,
                newer.version > candidate.version,
            )
        )
        rows = self._session.scalars(
            select(candidate)
            .where(
                candidate.source == source.strip(),
                candidate.base_asset == pair.base_asset,
                candidate.quote_asset == pair.quote_asset,
                candidate.market_type == pair.market_type.value,
                candidate.timeframe == timeframe.value,
                candidate.state == MarketDataWindowState.FINALIZED.value,
                candidate.window_end <= window_end_or_before,
                ~newer_finalized_version,
            )
            .order_by(
                candidate.window_end.desc(),
                candidate.version.desc(),
            )
            .limit(limit)
        ).all()
        return tuple(
            reversed(
                [MarketDataWindowSnapshot.model_validate_json(row.payload_json) for row in rows]
            )
        )
