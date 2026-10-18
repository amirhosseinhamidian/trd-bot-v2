import hashlib
import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.alerts.simulations import AlertSimulationRecord
from trd_bot.market_context import MarketTrendRegime

ALERT_OUTCOME_POLICY_VERSION: Literal["alert-outcome-policy-v1"] = "alert-outcome-policy-v1"
ALERT_OUTCOME_THRESHOLD = Decimal("0.005")
_METRIC_QUANTUM = Decimal("0.00000001")


def _checksum(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("alert outcome timestamp must include timezone information")
    return value.astimezone(UTC)


def _actor(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("alert outcome actor cannot be empty")
    return normalized


def _metric(value: Decimal) -> Decimal:
    return value.quantize(_METRIC_QUANTUM, rounding=ROUND_HALF_EVEN)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def alert_outcome_policy_checksum() -> str:
    return _checksum(
        {
            "classification_threshold": _decimal_text(ALERT_OUTCOME_THRESHOLD),
            "policy_version": ALERT_OUTCOME_POLICY_VERSION,
            "ranging_uses_absolute_return": True,
            "trend_uses_directional_return": True,
        }
    )


class AlertOutcomeClassification(StrEnum):
    CONFIRMED = "confirmed"
    NEUTRAL = "neutral"
    FALSE_POSITIVE = "false_positive"


def build_alert_outcome_id(simulation_id: str) -> str:
    return f"alert-outcome-{_checksum({'simulation_id': simulation_id})[:16]}"


class AlertOutcomeRecord(BaseModel):
    """Immutable offline observation linked to one alert simulation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-outcome-v1"] = "alert-outcome-v1"
    outcome_id: str = Field(pattern=r"^alert-outcome-[a-f0-9]{16}$")
    simulation_id: str = Field(pattern=r"^alert-simulation-[a-f0-9]{16}$")
    simulation_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    alert_id: str = Field(pattern=r"^alert-[a-f0-9]{16}$")
    alert_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: str = Field(pattern=r"^(paper|shadow)$")
    expected_trend: MarketTrendRegime
    observed_trend: MarketTrendRegime
    reference_price: Decimal = Field(gt=0, max_digits=28, decimal_places=10)
    end_price: Decimal = Field(gt=0, max_digits=28, decimal_places=10)
    high_price: Decimal = Field(gt=0, max_digits=28, decimal_places=10)
    low_price: Decimal = Field(gt=0, max_digits=28, decimal_places=10)
    raw_return: Decimal = Field(max_digits=18, decimal_places=8)
    directional_return: Decimal = Field(max_digits=18, decimal_places=8)
    max_favorable_excursion: Decimal = Field(max_digits=18, decimal_places=8)
    max_adverse_excursion: Decimal = Field(max_digits=18, decimal_places=8)
    classification: AlertOutcomeClassification
    false_positive: bool
    drifted: bool
    policy_version: Literal["alert-outcome-policy-v1"] = ALERT_OUTCOME_POLICY_VERSION
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    classification_threshold: Decimal = Field(gt=0, lt=1)
    observed_at: datetime
    recorded_at: datetime
    recorded_by: str = Field(min_length=1, max_length=100)
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("observed_at", "recorded_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _timestamp(value)

    @field_validator("recorded_by")
    @classmethod
    def normalize_actor(cls, value: str) -> str:
        return _actor(value)

    def _payload(self) -> dict[str, object]:
        return {
            "alert_checksum": self.alert_checksum,
            "alert_id": self.alert_id,
            "classification": self.classification.value,
            "classification_threshold": _decimal_text(self.classification_threshold),
            "directional_return": _decimal_text(self.directional_return),
            "drifted": self.drifted,
            "end_price": _decimal_text(self.end_price),
            "expected_trend": self.expected_trend.value,
            "external_order_submission_allowed": False,
            "false_positive": self.false_positive,
            "high_price": _decimal_text(self.high_price),
            "low_price": _decimal_text(self.low_price),
            "max_adverse_excursion": _decimal_text(self.max_adverse_excursion),
            "max_favorable_excursion": _decimal_text(self.max_favorable_excursion),
            "mode": self.mode,
            "observed_at": self.observed_at.isoformat(),
            "observed_trend": self.observed_trend.value,
            "offline_only": True,
            "outcome_id": self.outcome_id,
            "policy_checksum": self.policy_checksum,
            "policy_version": self.policy_version,
            "raw_return": _decimal_text(self.raw_return),
            "recorded_at": self.recorded_at.isoformat(),
            "recorded_by": self.recorded_by,
            "reference_price": _decimal_text(self.reference_price),
            "schema_version": self.schema_version,
            "simulation_checksum": self.simulation_checksum,
            "simulation_id": self.simulation_id,
        }

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.outcome_id != build_alert_outcome_id(self.simulation_id):
            raise ValueError("alert outcome ID is inconsistent")
        if self.high_price < max(self.reference_price, self.end_price):
            raise ValueError("high price cannot be below observed prices")
        if self.low_price > min(self.reference_price, self.end_price):
            raise ValueError("low price cannot be above observed prices")
        if self.recorded_at < self.observed_at:
            raise ValueError("alert outcome cannot be recorded before observation")
        if self.policy_checksum != alert_outcome_policy_checksum():
            raise ValueError("alert outcome policy checksum is inconsistent")
        if self.classification_threshold != ALERT_OUTCOME_THRESHOLD:
            raise ValueError("alert outcome threshold is inconsistent")
        if self.false_positive != (
            self.classification is AlertOutcomeClassification.FALSE_POSITIVE
        ):
            raise ValueError("alert outcome false-positive flag is inconsistent")
        if self.drifted != (self.observed_trend is not self.expected_trend):
            raise ValueError("alert outcome drift flag is inconsistent")
        if self.record_checksum != _checksum(self._payload()):
            raise ValueError("alert outcome checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        simulation: AlertSimulationRecord,
        reference_price: Decimal,
        end_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        observed_trend: MarketTrendRegime,
        observed_at: datetime,
        recorded_at: datetime,
        recorded_by: str,
    ) -> Self:
        observed = _timestamp(observed_at)
        recorded = _timestamp(recorded_at)
        if observed < simulation.ends_at:
            raise ValueError("alert outcome cannot be observed before simulation horizon")
        if recorded < observed:
            raise ValueError("alert outcome cannot be recorded before observation")
        if min(reference_price, end_price, high_price, low_price) <= 0:
            raise ValueError("alert outcome prices must be positive")
        if high_price < max(reference_price, end_price):
            raise ValueError("high price cannot be below observed prices")
        if low_price > min(reference_price, end_price):
            raise ValueError("low price cannot be above observed prices")

        raw_return = _metric((end_price / reference_price) - Decimal(1))
        up_excursion = _metric((high_price / reference_price) - Decimal(1))
        down_excursion = _metric((low_price / reference_price) - Decimal(1))
        if simulation.expected_trend is MarketTrendRegime.TRENDING_UP:
            directional_return = raw_return
            favorable = max(Decimal(0), up_excursion)
            adverse = min(Decimal(0), down_excursion)
        elif simulation.expected_trend is MarketTrendRegime.TRENDING_DOWN:
            directional_return = _metric(-raw_return)
            favorable = max(Decimal(0), _metric(-down_excursion))
            adverse = min(Decimal(0), _metric(-up_excursion))
        else:
            directional_return = _metric(-abs(raw_return))
            favorable = Decimal(0)
            adverse = directional_return

        if simulation.expected_trend is MarketTrendRegime.RANGING:
            classification = (
                AlertOutcomeClassification.CONFIRMED
                if abs(raw_return) <= ALERT_OUTCOME_THRESHOLD
                else AlertOutcomeClassification.FALSE_POSITIVE
            )
        elif simulation.expected_trend is MarketTrendRegime.UNDETERMINED:
            classification = AlertOutcomeClassification.NEUTRAL
        elif directional_return >= ALERT_OUTCOME_THRESHOLD:
            classification = AlertOutcomeClassification.CONFIRMED
        elif directional_return <= -ALERT_OUTCOME_THRESHOLD:
            classification = AlertOutcomeClassification.FALSE_POSITIVE
        else:
            classification = AlertOutcomeClassification.NEUTRAL

        outcome_id = build_alert_outcome_id(simulation.simulation_id)
        favorable_excursion = _metric(favorable)
        adverse_excursion = _metric(adverse)
        false_positive = classification is AlertOutcomeClassification.FALSE_POSITIVE
        drifted = observed_trend is not simulation.expected_trend
        policy_checksum = alert_outcome_policy_checksum()
        normalized_actor = _actor(recorded_by)
        payload = {
            "alert_checksum": simulation.alert_checksum,
            "alert_id": simulation.alert_id,
            "classification": classification.value,
            "classification_threshold": _decimal_text(ALERT_OUTCOME_THRESHOLD),
            "directional_return": _decimal_text(directional_return),
            "drifted": drifted,
            "end_price": _decimal_text(end_price),
            "expected_trend": simulation.expected_trend.value,
            "external_order_submission_allowed": False,
            "false_positive": false_positive,
            "high_price": _decimal_text(high_price),
            "low_price": _decimal_text(low_price),
            "max_adverse_excursion": _decimal_text(adverse_excursion),
            "max_favorable_excursion": _decimal_text(favorable_excursion),
            "mode": simulation.mode.value,
            "observed_at": observed.isoformat(),
            "observed_trend": observed_trend.value,
            "offline_only": True,
            "outcome_id": outcome_id,
            "policy_checksum": policy_checksum,
            "policy_version": ALERT_OUTCOME_POLICY_VERSION,
            "raw_return": _decimal_text(raw_return),
            "recorded_at": recorded.isoformat(),
            "recorded_by": normalized_actor,
            "reference_price": _decimal_text(reference_price),
            "schema_version": "alert-outcome-v1",
            "simulation_checksum": simulation.record_checksum,
            "simulation_id": simulation.simulation_id,
        }
        return cls(
            outcome_id=outcome_id,
            simulation_id=simulation.simulation_id,
            simulation_checksum=simulation.record_checksum,
            alert_id=simulation.alert_id,
            alert_checksum=simulation.alert_checksum,
            mode=simulation.mode.value,
            expected_trend=simulation.expected_trend,
            observed_trend=observed_trend,
            reference_price=reference_price,
            end_price=end_price,
            high_price=high_price,
            low_price=low_price,
            raw_return=raw_return,
            directional_return=directional_return,
            max_favorable_excursion=favorable_excursion,
            max_adverse_excursion=adverse_excursion,
            classification=classification,
            false_positive=false_positive,
            drifted=drifted,
            policy_checksum=policy_checksum,
            classification_threshold=ALERT_OUTCOME_THRESHOLD,
            observed_at=observed,
            recorded_at=recorded,
            recorded_by=normalized_actor,
            record_checksum=_checksum(payload),
        )


class AlertOutcomeRecordResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-outcome-record-result-v1"] = "alert-outcome-record-result-v1"
    created: bool
    outcome: AlertOutcomeRecord


class AlertOutcomeSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-outcome-summary-v1"] = "alert-outcome-summary-v1"
    evaluated_at: datetime
    completed: int = Field(ge=0)
    awaiting_outcome: int = Field(ge=0)
    confirmed: int = Field(ge=0)
    neutral: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    drifted: int = Field(ge=0)
    paper: int = Field(ge=0)
    shadow: int = Field(ge=0)
    false_positive_rate: Decimal = Field(ge=0, le=1)
    drift_rate: Decimal = Field(ge=0, le=1)
    average_directional_return: Decimal = Field(max_digits=18, decimal_places=8)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _timestamp(value)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.completed != self.confirmed + self.neutral + self.false_positive:
            raise ValueError("alert outcome classification totals are inconsistent")
        if self.completed != self.paper + self.shadow:
            raise ValueError("alert outcome mode totals are inconsistent")
        return self
