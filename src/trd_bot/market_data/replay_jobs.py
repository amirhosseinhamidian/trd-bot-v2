from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from trd_bot.market_data.replay import MarketDataReplayRequest


class MarketDataReplayJobPayload(BaseModel):
    """Version-one allowlisted payload for one market-data replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    replay_id: str = Field(pattern=r"^market-replay-[a-f0-9]{16}$")


@dataclass(frozen=True)
class MarketDataReplayEnqueueResult:
    request: MarketDataReplayRequest
    job: BackgroundJob
    created: bool


def build_market_data_replay_idempotency_key(decision_id: str) -> str:
    return f"market-data-replay:{decision_id}"


def validate_market_data_replay_enqueue(
    *,
    request: MarketDataReplayRequest,
    job: BackgroundJob,
) -> MarketDataReplayJobPayload:
    if job.kind is not BackgroundJobKind.MARKET_DATA_REPLAY:
        raise ValueError("market-data replay requires a replay background job")
    if job.status is not BackgroundJobStatus.QUEUED:
        raise ValueError("market-data replay background job must be queued")
    payload = MarketDataReplayJobPayload.model_validate(job.payload)
    if payload.replay_id != request.replay_id:
        raise ValueError("market-data replay job does not reference its request")
    expected_key = build_market_data_replay_idempotency_key(request.decision_id)
    if job.idempotency_key != expected_key:
        raise ValueError("market-data replay job idempotency key is invalid")
    return payload
