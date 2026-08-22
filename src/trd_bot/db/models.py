from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from trd_bot.db.base import DatabaseBase


class DatasetSnapshotRow(DatabaseBase):
    """Serialized immutable market-data snapshot metadata and payload."""

    __tablename__ = "dataset_snapshots"

    dataset_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    base_asset: Mapped[str] = mapped_column(String(30), index=True)
    quote_asset: Mapped[str] = mapped_column(String(30), index=True)
    market_type: Mapped[str] = mapped_column(String(30))
    timeframe: Mapped[str] = mapped_column(String(20))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    candle_count: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    payload_json: Mapped[str] = mapped_column(Text)


class ResearchExperimentRow(DatabaseBase):
    """Serialized result of one standard offline research experiment."""

    __tablename__ = "research_experiments"

    experiment_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dataset_id: Mapped[str] = mapped_column(String(100), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str] = mapped_column(String(30))
    horizon_candles: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)


class WalkForwardRunRow(DatabaseBase):
    """Serialized result of one offline walk-forward research run."""

    __tablename__ = "walk_forward_runs"

    execution_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_dataset_id: Mapped[str] = mapped_column(String(100), index=True)
    plan_id: Mapped[str] = mapped_column(String(100), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str] = mapped_column(String(30))
    horizon_candles: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
