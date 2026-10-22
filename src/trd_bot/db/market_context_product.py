from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from trd_bot.db.models import MarketRegimeAssessmentRow
from trd_bot.domain.market_data import MarketType, TradingPair
from trd_bot.market_context import MarketContextProductView, MarketRegimeAssessment


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-context product query time must include timezone information")
    return value.astimezone(UTC)


class SqlAlchemyMarketContextProductReader:
    """Read latest immutable assessments without mutating or recomputing context."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_latest(
        self,
        *,
        limit: int,
        offset: int,
        source: str | None = None,
        pair: TradingPair | None = None,
        market_type: MarketType | None = None,
        evaluated_at: datetime | None = None,
    ) -> tuple[tuple[MarketContextProductView, ...], int]:
        if limit <= 0 or limit > 100:
            raise ValueError("market-context page limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("market-context page offset cannot be negative")
        normalized_source = None if source is None else source.strip()
        if source is not None and not normalized_source:
            raise ValueError("market-context source cannot be empty")

        statement = select(MarketRegimeAssessmentRow)
        statement = self._apply_filters(
            statement,
            source=normalized_source,
            pair=pair,
            market_type=market_type,
        )
        ranked = statement.with_only_columns(
            MarketRegimeAssessmentRow.assessment_id.label("assessment_id"),
            func.row_number()
            .over(
                partition_by=(
                    MarketRegimeAssessmentRow.source,
                    MarketRegimeAssessmentRow.base_asset,
                    MarketRegimeAssessmentRow.quote_asset,
                    MarketRegimeAssessmentRow.market_type,
                ),
                order_by=(
                    MarketRegimeAssessmentRow.as_of.desc(),
                    MarketRegimeAssessmentRow.assessed_at.desc(),
                    MarketRegimeAssessmentRow.assessment_id.desc(),
                ),
            )
            .label("stream_rank"),
        ).subquery()

        total = int(
            self._session.scalar(
                select(func.count()).select_from(ranked).where(ranked.c.stream_rank == 1)
            )
            or 0
        )
        rows = self._session.scalars(
            select(MarketRegimeAssessmentRow)
            .join(ranked, MarketRegimeAssessmentRow.assessment_id == ranked.c.assessment_id)
            .where(ranked.c.stream_rank == 1)
            .order_by(
                MarketRegimeAssessmentRow.as_of.desc(),
                MarketRegimeAssessmentRow.source,
                MarketRegimeAssessmentRow.base_asset,
                MarketRegimeAssessmentRow.quote_asset,
            )
            .offset(offset)
            .limit(limit)
        ).all()
        now = _as_utc(evaluated_at or datetime.now(UTC))
        return (
            tuple(
                MarketContextProductView.from_assessment(
                    MarketRegimeAssessment.model_validate_json(row.payload_json),
                    evaluated_at=now,
                )
                for row in rows
            ),
            total,
        )

    def get(
        self,
        assessment_id: str,
        *,
        evaluated_at: datetime | None = None,
    ) -> MarketContextProductView | None:
        row = self._session.get(MarketRegimeAssessmentRow, assessment_id)
        if row is None:
            return None
        return MarketContextProductView.from_assessment(
            MarketRegimeAssessment.model_validate_json(row.payload_json),
            evaluated_at=_as_utc(evaluated_at or datetime.now(UTC)),
        )

    @staticmethod
    def _apply_filters(
        statement: Select[tuple[MarketRegimeAssessmentRow]],
        *,
        source: str | None,
        pair: TradingPair | None,
        market_type: MarketType | None,
    ) -> Select[tuple[MarketRegimeAssessmentRow]]:
        if source is not None:
            statement = statement.where(MarketRegimeAssessmentRow.source == source)
        if pair is not None:
            statement = statement.where(
                MarketRegimeAssessmentRow.base_asset == pair.base_asset,
                MarketRegimeAssessmentRow.quote_asset == pair.quote_asset,
                MarketRegimeAssessmentRow.market_type == pair.market_type.value,
            )
        elif market_type is not None:
            statement = statement.where(MarketRegimeAssessmentRow.market_type == market_type.value)
        return statement
