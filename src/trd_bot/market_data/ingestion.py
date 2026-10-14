from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.market_data.events import (
    MarketDataEventDecision,
    MarketDataEventDisposition,
)

MARKET_DATA_WINDOWING_TOPIC = "market-data.windowing"


class MarketDataIngestionError(RuntimeError):
    """Base error for durable market-data ingestion."""


class MarketDataIngestionConflictError(MarketDataIngestionError):
    """A concurrent write could not be resolved to a durable prior result."""


class MarketDataIngestionWatermarkMissingError(MarketDataIngestionError):
    """No persisted watermark exists for the event stream."""


class MarketDataIngestionResult(BaseModel):
    """Stable outcome of one atomic ingestion observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-ingestion-result-v1"] = "market-data-ingestion-result-v1"
    observation_id: str = Field(pattern=r"^market-raw-[a-f0-9]{16}$")
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    decision_id: str = Field(pattern=r"^market-decision-[a-f0-9]{16}$")
    watermark_id: str = Field(pattern=r"^market-watermark-[a-f0-9]{16}$")
    decision: MarketDataEventDecision
    inbox_delivery_count: int = Field(ge=1)
    window_version: int | None = Field(default=None, ge=1)
    outbox_id: str | None = Field(
        default=None,
        pattern=r"^market-outbox-[a-f0-9]{16}$",
    )
    created: bool

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.event_id != self.decision.event_id:
            raise ValueError("ingestion result event does not match its decision")

        if self.decision.disposition is MarketDataEventDisposition.ACCEPTED:
            if self.window_version is None or self.outbox_id is None:
                raise ValueError("accepted ingestion requires window and outbox references")
            if self.window_version != self.decision.proposed_window_version:
                raise ValueError("ingestion window version does not match its decision")
        elif self.window_version is not None or self.outbox_id is not None:
            raise ValueError("non-accepted ingestion cannot create a window or outbox message")

        return self
