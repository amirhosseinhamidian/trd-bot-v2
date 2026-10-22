import hashlib
import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.backtesting import PositionSide
from trd_bot.decision_intelligence.candidates import DecisionCandidateAction
from trd_bot.decision_intelligence.contracts import (
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionMode,
    DecisionReasonCode,
    DecisionStage,
    DecisionStageOutcome,
)
from trd_bot.decision_intelligence.risk import DecisionRiskGateRecord
from trd_bot.domain.market_data import TradingPair
from trd_bot.market_context import MarketTrendRegime
from trd_bot.paper import PositionStatus, SimulatedPortfolio, SimulationMode

RATIO_QUANTUM = Decimal("0.000001")
MONEY_QUANTUM = Decimal("0.00000001")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("portfolio intelligence timestamp must include timezone information")
    return value.astimezone(UTC)


def _ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class PortfolioSnapshotSource(StrEnum):
    EMPTY_BASELINE = "empty_baseline"
    PERSISTED_SIMULATION = "persisted_simulation"


class PortfolioRecommendation(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    UNAVAILABLE = "unavailable"


class PortfolioCorrelationStatus(StrEnum):
    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class PortfolioCheckName(StrEnum):
    ACTIVE = "portfolio_active"
    CAPACITY = "portfolio_capacity"
    EXPOSURE = "projected_exposure"
    CONCENTRATION = "projected_concentration"
    CORRELATION = "candidate_correlation"
    SCENARIO_LOSS = "scenario_loss"
    REGIME_ALIGNMENT = "regime_alignment"


class PortfolioExitAction(StrEnum):
    HOLD = "hold"
    EXIT_RISK = "exit_risk"
    EXIT_REGIME = "exit_regime"


class DecisionPortfolioPolicyV1(BaseModel):
    """Frozen limits for narrow paper/shadow portfolio intelligence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-portfolio-policy-v1"] = "decision-portfolio-policy-v1"
    policy_version: Literal["decision-portfolio-v1"] = "decision-portfolio-v1"
    max_gross_exposure_fraction: Decimal = Field(default=Decimal("0.250000"), gt=0, le=1)
    max_asset_concentration_fraction: Decimal = Field(default=Decimal("0.200000"), gt=0, le=1)
    max_absolute_correlation: Decimal = Field(default=Decimal("0.850000"), ge=0, le=1)
    max_scenario_loss_fraction: Decimal = Field(default=Decimal("0.020000"), gt=0, le=1)
    risk_exit_drawdown_fraction: Decimal = Field(default=Decimal("0.150000"), gt=0, le=1)
    scenario_shocks: tuple[Decimal, ...] = (
        Decimal("-0.100000"),
        Decimal("-0.050000"),
        Decimal("0.050000"),
        Decimal("0.100000"),
    )
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        expected = {
            "max_gross_exposure_fraction": Decimal("0.250000"),
            "max_asset_concentration_fraction": Decimal("0.200000"),
            "max_absolute_correlation": Decimal("0.850000"),
            "max_scenario_loss_fraction": Decimal("0.020000"),
            "risk_exit_drawdown_fraction": Decimal("0.150000"),
            "scenario_shocks": (
                Decimal("-0.100000"),
                Decimal("-0.050000"),
                Decimal("0.050000"),
                Decimal("0.100000"),
            ),
        }
        for name, value in expected.items():
            if getattr(self, name) != value:
                raise ValueError(f"decision portfolio {name} is not version one")
        if self.definition_checksum != _checksum(self._checksum_payload()):
            raise ValueError("decision portfolio policy checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "max_absolute_correlation": str(self.max_absolute_correlation),
            "max_asset_concentration_fraction": str(self.max_asset_concentration_fraction),
            "max_gross_exposure_fraction": str(self.max_gross_exposure_fraction),
            "max_scenario_loss_fraction": str(self.max_scenario_loss_fraction),
            "policy_version": self.policy_version,
            "risk_exit_drawdown_fraction": str(self.risk_exit_drawdown_fraction),
            "scenario_shocks": [str(item) for item in self.scenario_shocks],
            "schema_version": self.schema_version,
        }


def decision_portfolio_policy_v1() -> DecisionPortfolioPolicyV1:
    unvalidated = DecisionPortfolioPolicyV1.model_construct(definition_checksum="0" * 64)
    payload = unvalidated.model_dump()
    payload["definition_checksum"] = _checksum(unvalidated._checksum_payload())
    return DecisionPortfolioPolicyV1.model_validate(payload)


class PortfolioPositionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    position_id: str = Field(pattern=r"^position-[a-f0-9]{16}$")
    pair: TradingPair
    side: PositionSide
    notional: Decimal = Field(gt=0)
    unrealized_pnl: Decimal


class DecisionPortfolioSnapshot(BaseModel):
    """Immutable input snapshot; it never mutates the simulated portfolio aggregate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-portfolio-snapshot-v1"] = "decision-portfolio-snapshot-v1"
    snapshot_id: str = Field(pattern=r"^decision-portfolio-snapshot-[a-f0-9]{16}$")
    source: PortfolioSnapshotSource
    portfolio_id: str | None = Field(default=None, pattern=r"^portfolio-[a-f0-9]{16}$")
    mode: Literal[DecisionMode.PAPER, DecisionMode.SHADOW]
    dataset_id: str = Field(min_length=1, max_length=100)
    status: Literal["active"] = "active"
    as_of: datetime
    starting_equity: Decimal = Field(gt=0)
    cash: Decimal = Field(ge=0)
    equity: Decimal = Field(gt=0)
    open_positions: tuple[PortfolioPositionSnapshot, ...]
    snapshot_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if (self.portfolio_id is None) != (self.source is PortfolioSnapshotSource.EMPTY_BASELINE):
            raise ValueError("portfolio snapshot source and identity are inconsistent")
        expected_checksum = _checksum(self._checksum_payload())
        if self.snapshot_checksum != expected_checksum:
            raise ValueError("portfolio snapshot checksum is inconsistent")
        if self.snapshot_id != f"decision-portfolio-snapshot-{expected_checksum[:16]}":
            raise ValueError("portfolio snapshot ID is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "cash": str(self.cash),
            "dataset_id": self.dataset_id,
            "equity": str(self.equity),
            "mode": self.mode.value,
            "open_positions": [item.model_dump(mode="json") for item in self.open_positions],
            "portfolio_id": self.portfolio_id,
            "schema_version": self.schema_version,
            "source": self.source.value,
            "starting_equity": str(self.starting_equity),
            "status": self.status,
        }

    @classmethod
    def build_empty(
        cls,
        *,
        mode: DecisionMode,
        dataset_id: str,
        equity: Decimal,
        as_of: datetime,
    ) -> Self:
        if mode is DecisionMode.RESEARCH:
            raise ValueError("research mode cannot build a simulated portfolio snapshot")
        unvalidated = cls.model_construct(
            source=PortfolioSnapshotSource.EMPTY_BASELINE,
            portfolio_id=None,
            mode=mode,
            dataset_id=dataset_id,
            as_of=_normalize_timestamp(as_of),
            starting_equity=equity,
            cash=equity,
            equity=equity,
            open_positions=(),
            snapshot_id="decision-portfolio-snapshot-0000000000000000",
            snapshot_checksum="0" * 64,
        )
        checksum = _checksum(unvalidated._checksum_payload())
        payload = unvalidated.model_dump()
        payload["snapshot_id"] = f"decision-portfolio-snapshot-{checksum[:16]}"
        payload["snapshot_checksum"] = checksum
        return cls.model_validate(payload)

    @classmethod
    def from_portfolio(cls, portfolio: SimulatedPortfolio) -> Self:
        mode = {
            SimulationMode.PAPER: DecisionMode.PAPER,
            SimulationMode.SHADOW: DecisionMode.SHADOW,
        }[portfolio.mode]
        open_positions = tuple(
            PortfolioPositionSnapshot(
                position_id=item.position_id,
                pair=item.pair,
                side=item.side,
                notional=_money(item.quantity * item.current_price),
                unrealized_pnl=item.unrealized_pnl,
            )
            for item in portfolio.positions
            if item.status is PositionStatus.OPEN
        )
        unvalidated = cls.model_construct(
            source=PortfolioSnapshotSource.PERSISTED_SIMULATION,
            portfolio_id=portfolio.portfolio_id,
            mode=mode,
            dataset_id=portfolio.dataset_id,
            as_of=portfolio.updated_at,
            starting_equity=portfolio.starting_cash,
            cash=portfolio.cash,
            equity=portfolio.equity,
            open_positions=open_positions,
            snapshot_id="decision-portfolio-snapshot-0000000000000000",
            snapshot_checksum="0" * 64,
        )
        checksum = _checksum(unvalidated._checksum_payload())
        payload = unvalidated.model_dump()
        payload["snapshot_id"] = f"decision-portfolio-snapshot-{checksum[:16]}"
        payload["snapshot_checksum"] = checksum
        return cls.model_validate(payload)


class PortfolioExposure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    current_gross_notional: Decimal = Field(ge=0)
    candidate_notional: Decimal = Field(gt=0)
    projected_gross_notional: Decimal = Field(gt=0)
    current_exposure_fraction: Decimal = Field(ge=0)
    projected_exposure_fraction: Decimal = Field(ge=0)
    projected_asset_concentration_fraction: Decimal = Field(ge=0)


class PortfolioCorrelation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: PortfolioCorrelationStatus
    maximum_absolute_correlation: Decimal | None = Field(default=None, ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_correlation(self) -> Self:
        if (self.maximum_absolute_correlation is None) == (
            self.status is PortfolioCorrelationStatus.AVAILABLE
        ):
            raise ValueError("portfolio correlation status and value are inconsistent")
        return self


class PortfolioScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    shock_fraction: Decimal = Field(ge=-1, le=1)
    existing_pnl: Decimal
    candidate_pnl: Decimal
    projected_equity: Decimal
    loss_fraction: Decimal = Field(ge=0)


class PortfolioCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: PortfolioCheckName
    passed: bool
    actual_value: str = Field(min_length=1, max_length=100)
    limit_value: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=500)


class PortfolioExitRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    position_id: str = Field(pattern=r"^position-[a-f0-9]{16}$")
    action: PortfolioExitAction
    reason_codes: tuple[Literal["risk_limit", "regime_change"], ...]


class DecisionPortfolioAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-portfolio-analysis-v1"] = "decision-portfolio-analysis-v1"
    analysis_id: str = Field(pattern=r"^decision-portfolio-[a-f0-9]{16}$")
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    candidate_id: str = Field(pattern=r"^decision-candidate-[a-f0-9]{16}$")
    snapshot: DecisionPortfolioSnapshot
    exposure: PortfolioExposure
    correlation: PortfolioCorrelation
    scenarios: tuple[PortfolioScenarioResult, ...]
    checks: tuple[PortfolioCheck, ...]
    recommendation: Literal[PortfolioRecommendation.ACCEPT, PortfolioRecommendation.REJECT]
    exit_recommendations: tuple[PortfolioExitRecommendation, ...]
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    analyzed_at: datetime
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    analysis_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("analyzed_at")
    @classmethod
    def normalize_analyzed_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_analysis(self) -> Self:
        if tuple(item.name for item in self.checks) != tuple(PortfolioCheckName):
            raise ValueError("portfolio checks must be complete and ordered")
        expected = (
            PortfolioRecommendation.ACCEPT
            if all(item.passed for item in self.checks)
            else PortfolioRecommendation.REJECT
        )
        if self.recommendation is not expected:
            raise ValueError("portfolio recommendation does not match its checks")
        identity = {
            "candidate_id": self.candidate_id,
            "evaluation_id": self.evaluation_id,
            "policy_checksum": self.policy_checksum,
            "snapshot_checksum": self.snapshot.snapshot_checksum,
        }
        if self.analysis_id != f"decision-portfolio-{_checksum(identity)[:16]}":
            raise ValueError("portfolio analysis ID is inconsistent")
        if self.analysis_checksum != _checksum(self._checksum_payload()):
            raise ValueError("portfolio analysis checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "analysis_id": self.analysis_id,
            "analyzed_at": self.analyzed_at.isoformat(),
            "candidate_id": self.candidate_id,
            "checks": [item.model_dump(mode="json") for item in self.checks],
            "correlation": self.correlation.model_dump(mode="json"),
            "evaluation_id": self.evaluation_id,
            "exit_recommendations": [
                item.model_dump(mode="json") for item in self.exit_recommendations
            ],
            "exposure": self.exposure.model_dump(mode="json"),
            "external_order_submission_allowed": False,
            "offline_only": True,
            "policy_checksum": self.policy_checksum,
            "recommendation": self.recommendation.value,
            "scenarios": [item.model_dump(mode="json") for item in self.scenarios],
            "schema_version": self.schema_version,
            "snapshot": self.snapshot.model_dump(mode="json"),
        }


class DecisionPortfolioIntelligenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-portfolio-intelligence-record-v1"] = (
        "decision-portfolio-intelligence-record-v1"
    )
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    outcome: DecisionStageOutcome
    risk_gate_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_version: Literal["decision-portfolio-v1"]
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    recommendation: PortfolioRecommendation
    analysis: DecisionPortfolioAnalysis | None
    analyzed_at: datetime
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("analyzed_at")
    @classmethod
    def normalize_analyzed_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.outcome.evaluation_id != self.evaluation_id:
            raise ValueError("portfolio outcome belongs to another evaluation")
        if self.outcome.stage is not DecisionStage.PORTFOLIO_SIMULATION:
            raise ValueError("portfolio outcome has an invalid stage")
        if self.outcome.evaluated_at != self.analyzed_at:
            raise ValueError("portfolio outcome time is inconsistent")
        if self.analysis is None:
            if self.recommendation is not PortfolioRecommendation.UNAVAILABLE:
                raise ValueError("missing portfolio analysis must be unavailable")
            if self.outcome.disposition is not DecisionDisposition.UNAVAILABLE:
                raise ValueError("missing portfolio analysis must have unavailable outcome")
            if self.outcome.reason_codes != (DecisionReasonCode.PORTFOLIO_UNAVAILABLE,):
                raise ValueError("unavailable portfolio reason is inconsistent")
        else:
            if self.analysis.evaluation_id != self.evaluation_id:
                raise ValueError("portfolio analysis belongs to another evaluation")
            if self.analysis.policy_checksum != self.policy_checksum:
                raise ValueError("portfolio policy lineage is inconsistent")
            if self.recommendation is not self.analysis.recommendation:
                raise ValueError("portfolio record recommendation is inconsistent")
            expected_disposition = (
                DecisionDisposition.ACCEPTED
                if self.recommendation is PortfolioRecommendation.ACCEPT
                else DecisionDisposition.REJECTED
            )
            expected_reasons = (
                ()
                if expected_disposition is DecisionDisposition.ACCEPTED
                else (DecisionReasonCode.PORTFOLIO_POLICY_REJECTED,)
            )
            if (
                self.outcome.disposition is not expected_disposition
                or self.outcome.reason_codes != expected_reasons
            ):
                raise ValueError("portfolio stage outcome is inconsistent")
        if self.record_checksum != _checksum(self._checksum_payload()):
            raise ValueError("portfolio intelligence record checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "analysis": None if self.analysis is None else self.analysis.model_dump(mode="json"),
            "analyzed_at": self.analyzed_at.isoformat(),
            "evaluation_id": self.evaluation_id,
            "external_order_submission_allowed": False,
            "offline_only": True,
            "outcome": self.outcome.model_dump(mode="json"),
            "policy_checksum": self.policy_checksum,
            "policy_version": self.policy_version,
            "recommendation": self.recommendation.value,
            "risk_gate_checksum": self.risk_gate_checksum,
            "schema_version": self.schema_version,
        }


class DecisionPortfolioIntegrityError(ValueError):
    """Persisted risk or portfolio evidence no longer matches pinned lineage."""


def _position_direction(side: PositionSide) -> Decimal:
    return Decimal("1") if side is PositionSide.LONG else Decimal("-1")


def _candidate_direction(action: DecisionCandidateAction) -> Decimal:
    return Decimal("1") if action is DecisionCandidateAction.LONG else Decimal("-1")


def _regime_aligned(action: DecisionCandidateAction, trend: MarketTrendRegime) -> bool:
    return (action is DecisionCandidateAction.LONG and trend is MarketTrendRegime.TRENDING_UP) or (
        action is DecisionCandidateAction.SHORT and trend is MarketTrendRegime.TRENDING_DOWN
    )


def _build_analysis(
    *,
    intent: DecisionEvaluationIntent,
    risk_gate: DecisionRiskGateRecord,
    snapshot: DecisionPortfolioSnapshot,
    policy: DecisionPortfolioPolicyV1,
) -> DecisionPortfolioAnalysis:
    sizing = risk_gate.assessment.position_sizing
    if sizing is None:
        raise DecisionPortfolioIntegrityError("portfolio intelligence requires approved sizing")
    ranking_candidate_id = risk_gate.assessment.candidate_id
    action = (
        DecisionCandidateAction.LONG
        if sizing.target_price > sizing.entry_price
        else DecisionCandidateAction.SHORT
    )
    equity = snapshot.equity
    current_gross = _money(sum((item.notional for item in snapshot.open_positions), Decimal("0")))
    projected_gross = _money(current_gross + sizing.notional)
    same_asset = _money(
        sizing.notional
        + sum(
            (
                item.notional
                for item in snapshot.open_positions
                if item.pair.base_asset == intent.dataset.pair.base_asset
            ),
            Decimal("0"),
        )
    )
    exposure = PortfolioExposure(
        current_gross_notional=current_gross,
        candidate_notional=sizing.notional,
        projected_gross_notional=projected_gross,
        current_exposure_fraction=_ratio(current_gross / equity),
        projected_exposure_fraction=_ratio(projected_gross / equity),
        projected_asset_concentration_fraction=_ratio(same_asset / equity),
    )

    if not snapshot.open_positions:
        correlation = PortfolioCorrelation(
            status=PortfolioCorrelationStatus.NOT_APPLICABLE,
            evidence="No open simulated exposure exists; correlation is not applicable.",
        )
    elif all(item.pair == intent.dataset.pair for item in snapshot.open_positions):
        values = tuple(
            _candidate_direction(action) * _position_direction(item.side)
            for item in snapshot.open_positions
        )
        correlation = PortfolioCorrelation(
            status=PortfolioCorrelationStatus.AVAILABLE,
            maximum_absolute_correlation=max(abs(item) for item in values),
            evidence="Exact same-pair directional correlation from the simulated positions.",
        )
    else:
        correlation = PortfolioCorrelation(
            status=PortfolioCorrelationStatus.UNAVAILABLE,
            evidence="The pinned dataset cannot estimate correlation for another asset pair.",
        )

    scenarios = tuple(
        PortfolioScenarioResult(
            shock_fraction=shock,
            existing_pnl=_money(
                sum(
                    (
                        item.notional * shock * _position_direction(item.side)
                        for item in snapshot.open_positions
                    ),
                    Decimal("0"),
                )
            ),
            candidate_pnl=_money(sizing.notional * shock * _candidate_direction(action)),
            projected_equity=_money(
                equity
                + sum(
                    (
                        item.notional * shock * _position_direction(item.side)
                        for item in snapshot.open_positions
                    ),
                    Decimal("0"),
                )
                + sizing.notional * shock * _candidate_direction(action)
            ),
            loss_fraction=_ratio(
                max(
                    Decimal("0"),
                    -(
                        sum(
                            (
                                item.notional * shock * _position_direction(item.side)
                                for item in snapshot.open_positions
                            ),
                            Decimal("0"),
                        )
                        + sizing.notional * shock * _candidate_direction(action)
                    ),
                )
                / equity
            ),
        )
        for shock in policy.scenario_shocks
    )
    worst_loss = max(item.loss_fraction for item in scenarios)
    correlation_passed = correlation.status is PortfolioCorrelationStatus.NOT_APPLICABLE or (
        correlation.status is PortfolioCorrelationStatus.AVAILABLE
        and correlation.maximum_absolute_correlation is not None
        and correlation.maximum_absolute_correlation <= policy.max_absolute_correlation
    )
    checks = (
        PortfolioCheck(
            name=PortfolioCheckName.ACTIVE,
            passed=True,
            actual_value=snapshot.status,
            limit_value="active",
            explanation="Only an active simulated portfolio snapshot can be evaluated.",
        ),
        PortfolioCheck(
            name=PortfolioCheckName.CAPACITY,
            passed=not snapshot.open_positions,
            actual_value=str(len(snapshot.open_positions)),
            limit_value="0",
            explanation="The v1 simulated ledger supports one open position at a time.",
        ),
        PortfolioCheck(
            name=PortfolioCheckName.EXPOSURE,
            passed=(exposure.projected_exposure_fraction <= policy.max_gross_exposure_fraction),
            actual_value=str(exposure.projected_exposure_fraction),
            limit_value=str(policy.max_gross_exposure_fraction),
            explanation="Projected gross exposure must remain below the policy cap.",
        ),
        PortfolioCheck(
            name=PortfolioCheckName.CONCENTRATION,
            passed=(
                exposure.projected_asset_concentration_fraction
                <= policy.max_asset_concentration_fraction
            ),
            actual_value=str(exposure.projected_asset_concentration_fraction),
            limit_value=str(policy.max_asset_concentration_fraction),
            explanation="Projected base-asset concentration must remain below the cap.",
        ),
        PortfolioCheck(
            name=PortfolioCheckName.CORRELATION,
            passed=correlation_passed,
            actual_value=(
                correlation.status.value
                if correlation.maximum_absolute_correlation is None
                else str(correlation.maximum_absolute_correlation)
            ),
            limit_value=str(policy.max_absolute_correlation),
            explanation="Unavailable or excessive correlation fails closed.",
        ),
        PortfolioCheck(
            name=PortfolioCheckName.SCENARIO_LOSS,
            passed=worst_loss <= policy.max_scenario_loss_fraction,
            actual_value=str(worst_loss),
            limit_value=str(policy.max_scenario_loss_fraction),
            explanation="Worst deterministic stress loss must remain inside the policy limit.",
        ),
        PortfolioCheck(
            name=PortfolioCheckName.REGIME_ALIGNMENT,
            passed=_regime_aligned(action, intent.market_context.trend),
            actual_value=f"{action.value}:{intent.market_context.trend.value}",
            limit_value="direction_matches_regime",
            explanation="Candidate direction must remain aligned with the pinned market regime.",
        ),
    )
    drawdown = _ratio(
        max(Decimal("0"), snapshot.starting_equity - snapshot.equity) / snapshot.starting_equity
    )
    exits = tuple(
        PortfolioExitRecommendation(
            position_id=item.position_id,
            action=(
                PortfolioExitAction.EXIT_RISK
                if (
                    drawdown >= policy.risk_exit_drawdown_fraction
                    or exposure.current_exposure_fraction > policy.max_gross_exposure_fraction
                )
                else PortfolioExitAction.EXIT_REGIME
                if not _regime_aligned(
                    DecisionCandidateAction.LONG
                    if item.side is PositionSide.LONG
                    else DecisionCandidateAction.SHORT,
                    intent.market_context.trend,
                )
                else PortfolioExitAction.HOLD
            ),
            reason_codes=(
                ("risk_limit",)
                if (
                    drawdown >= policy.risk_exit_drawdown_fraction
                    or exposure.current_exposure_fraction > policy.max_gross_exposure_fraction
                )
                else ("regime_change",)
                if not _regime_aligned(
                    DecisionCandidateAction.LONG
                    if item.side is PositionSide.LONG
                    else DecisionCandidateAction.SHORT,
                    intent.market_context.trend,
                )
                else ()
            ),
        )
        for item in snapshot.open_positions
    )
    recommendation = (
        PortfolioRecommendation.ACCEPT
        if all(item.passed for item in checks)
        else PortfolioRecommendation.REJECT
    )
    identity = {
        "candidate_id": ranking_candidate_id,
        "evaluation_id": intent.evaluation_id,
        "policy_checksum": policy.definition_checksum,
        "snapshot_checksum": snapshot.snapshot_checksum,
    }
    analysis_id = f"decision-portfolio-{_checksum(identity)[:16]}"
    unvalidated = DecisionPortfolioAnalysis.model_construct(
        analysis_id=analysis_id,
        evaluation_id=intent.evaluation_id,
        candidate_id=ranking_candidate_id,
        snapshot=snapshot,
        exposure=exposure,
        correlation=correlation,
        scenarios=scenarios,
        checks=checks,
        recommendation=recommendation,
        exit_recommendations=exits,
        policy_checksum=policy.definition_checksum,
        analyzed_at=risk_gate.evaluated_at,
        analysis_checksum="0" * 64,
    )
    payload = unvalidated.model_dump()
    payload["analysis_checksum"] = _checksum(unvalidated._checksum_payload())
    return DecisionPortfolioAnalysis.model_validate(payload)


def evaluate_portfolio_intelligence(
    *,
    intent: DecisionEvaluationIntent,
    risk_gate: DecisionRiskGateRecord,
    snapshot: DecisionPortfolioSnapshot | None,
    policy: DecisionPortfolioPolicyV1 | None = None,
) -> DecisionPortfolioIntelligenceRecord:
    """Evaluate candidate impact without applying any portfolio transition."""

    resolved_policy = policy or decision_portfolio_policy_v1()
    if risk_gate.evaluation_id != intent.evaluation_id:
        raise DecisionPortfolioIntegrityError("portfolio risk gate belongs to another intent")
    if risk_gate.outcome.disposition is not DecisionDisposition.ACCEPTED:
        raise DecisionPortfolioIntegrityError("portfolio intelligence requires accepted risk")
    analyzed_at = risk_gate.evaluated_at
    if intent.mode is DecisionMode.RESEARCH or snapshot is None:
        analysis = None
        recommendation = PortfolioRecommendation.UNAVAILABLE
        outcome = DecisionStageOutcome.build(
            evaluation_id=intent.evaluation_id,
            stage=DecisionStage.PORTFOLIO_SIMULATION,
            disposition=DecisionDisposition.UNAVAILABLE,
            reason_codes=(DecisionReasonCode.PORTFOLIO_UNAVAILABLE,),
            evaluated_at=analyzed_at,
        )
    else:
        if snapshot.mode is not intent.mode or snapshot.dataset_id != intent.dataset.dataset_id:
            raise DecisionPortfolioIntegrityError("portfolio snapshot lineage is inconsistent")
        if snapshot.as_of > analyzed_at:
            raise DecisionPortfolioIntegrityError("portfolio snapshot contains future state")
        analysis = _build_analysis(
            intent=intent,
            risk_gate=risk_gate,
            snapshot=snapshot,
            policy=resolved_policy,
        )
        recommendation = analysis.recommendation
        accepted = recommendation is PortfolioRecommendation.ACCEPT
        outcome = DecisionStageOutcome.build(
            evaluation_id=intent.evaluation_id,
            stage=DecisionStage.PORTFOLIO_SIMULATION,
            disposition=(
                DecisionDisposition.ACCEPTED if accepted else DecisionDisposition.REJECTED
            ),
            reason_codes=(() if accepted else (DecisionReasonCode.PORTFOLIO_POLICY_REJECTED,)),
            evaluated_at=analyzed_at,
        )
    unvalidated = DecisionPortfolioIntelligenceRecord.model_construct(
        evaluation_id=intent.evaluation_id,
        outcome=outcome,
        risk_gate_checksum=risk_gate.record_checksum,
        policy_version=resolved_policy.policy_version,
        policy_checksum=resolved_policy.definition_checksum,
        recommendation=recommendation,
        analysis=analysis,
        analyzed_at=analyzed_at,
        record_checksum="0" * 64,
    )
    payload = unvalidated.model_dump()
    payload["record_checksum"] = _checksum(unvalidated._checksum_payload())
    return DecisionPortfolioIntelligenceRecord.model_validate(payload)
