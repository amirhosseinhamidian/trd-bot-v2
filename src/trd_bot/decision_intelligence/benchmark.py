import hashlib
import json
import platform
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.decision_intelligence.candidates import (
    build_decision_candidate_ranking,
    decision_candidate_policy_v1,
)
from trd_bot.decision_intelligence.contracts import (
    DecisionEvaluationIntent,
    DecisionMode,
    DecisionPolicyDefinition,
    DecisionPolicyState,
)
from trd_bot.decision_intelligence.evaluation import (
    evaluate_strategy_intent,
    strategy_context_compatibility_policy_v1,
)
from trd_bot.decision_intelligence.portfolio import (
    DecisionPortfolioSnapshot,
    decision_portfolio_policy_v1,
    evaluate_portfolio_intelligence,
)
from trd_bot.decision_intelligence.risk import (
    decision_risk_policy_v1,
    evaluate_decision_risk,
)
from trd_bot.domain import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextEvidence,
    MarketContextProductView,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
    build_market_regime_assessment_id,
)
from trd_bot.research import DatasetBuilder, DatasetSnapshot
from trd_bot.strategies import build_default_strategy_registry

DECISION_PIPELINE_BENCHMARK_FIXTURE_VERSION = "decision-pipeline-golden-v1"
DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES = 100
DECISION_PIPELINE_BENCHMARK_RUNTIME_BUDGET_MS = Decimal("25")

_PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
_SOURCE = "kraken-public"
_AS_OF = datetime(2026, 10, 19, 12, tzinfo=UTC)
_REQUESTED_AT = _AS_OF + timedelta(minutes=20)


def _checksum(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _percentile(values: list[Decimal], percentile: Decimal) -> Decimal:
    ordered = sorted(values)
    index = int((Decimal(len(ordered) - 1) * percentile).to_integral_value())
    return ordered[index]


def _fixture_inputs() -> tuple[DecisionEvaluationIntent, DatasetSnapshot]:
    closes = (3, 2, 1, 2, 3)
    candles = tuple(
        OHLCVCandle(
            source=_SOURCE,
            pair=_PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=_AS_OF - timedelta(hours=len(closes) - index),
            close_time=_AS_OF - timedelta(hours=len(closes) - index - 1),
            received_at=(_AS_OF - timedelta(hours=len(closes) - index - 1) + timedelta(minutes=1)),
            open_price=Decimal(close + 100),
            high_price=Decimal(close + 101),
            low_price=Decimal(close + 99),
            close_price=Decimal(close + 100),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index, close in enumerate(closes)
    )
    dataset = DatasetBuilder().build(
        name="Decision pipeline golden fixture",
        candles=candles,
        created_at=_AS_OF + timedelta(minutes=2),
    )
    input_checksum = "a" * 64
    assessment = MarketRegimeAssessment(
        assessment_id=build_market_regime_assessment_id(
            source=_SOURCE,
            pair=_PAIR,
            as_of=_AS_OF,
            input_checksum=input_checksum,
            feature_set_version="market-context-features-v1",
            algorithm_version="market-regime-v1",
        ),
        source=_SOURCE,
        pair=_PAIR,
        as_of=_AS_OF,
        input_manifest_id=f"market-context-input-{input_checksum[:16]}",
        input_checksum=input_checksum,
        feature_set_version="market-context-features-v1",
        feature_set_checksum="b" * 64,
        feature_snapshot_id="market-context-features-cccccccccccccccc",
        feature_snapshot_checksum="c" * 64,
        algorithm_version="market-regime-v1",
        status=MarketContextAssessmentStatus.READY,
        trend=MarketTrendRegime.TRENDING_UP,
        volatility=MarketVolatilityRegime.NORMAL,
        confidence=Decimal("0.82"),
        evidence=(
            MarketContextEvidence(
                feature_key="trend_slope_1h",
                timeframe=Timeframe.HOUR_1,
                value=Decimal("0.013"),
                calculation_version="trend-slope-v1",
                window_reference_checksums=("d" * 64,),
            ),
        ),
        assessed_at=_AS_OF + timedelta(minutes=1),
        expires_at=_AS_OF + timedelta(hours=1),
    )
    context = MarketContextProductView.from_assessment(
        assessment,
        evaluated_at=_REQUESTED_AT,
    )
    policy = DecisionPolicyDefinition.build(
        policy_key="default-context-aware-decision",
        policy_version=1,
        name="Default context-aware decision policy",
        description="Admit only traceable offline strategy decisions.",
        state=DecisionPolicyState.ENABLED,
        allowed_modes=tuple(DecisionMode),
        created_at=_AS_OF + timedelta(minutes=2),
    )
    metadata = build_default_strategy_registry().get_metadata(
        name="sma-crossover",
        version="1.0.0",
    )
    if metadata is None:  # pragma: no cover - guarded by the canonical registry contract
        raise RuntimeError("decision benchmark strategy is unavailable")
    intent = DecisionEvaluationIntent.build(
        mode=DecisionMode.SHADOW,
        dataset=dataset,
        strategy=metadata,
        strategy_parameters={"fast_period": 2, "slow_period": 3},
        market_context=context,
        policy=policy,
        requested_at=_REQUESTED_AT,
    )
    return intent, dataset


def decision_pipeline_benchmark_fixture_checksum() -> str:
    intent, dataset = _fixture_inputs()
    return _checksum(
        {
            "dataset_checksum": dataset.checksum,
            "fixture_version": DECISION_PIPELINE_BENCHMARK_FIXTURE_VERSION,
            "intent_checksum": intent.intent_checksum,
            "mode": intent.mode.value,
            "stage_order": (
                "strategy_evaluation",
                "candidate_ranking",
                "risk_gate",
                "portfolio_simulation",
            ),
        }
    )


class DecisionPipelineBenchmarkReport(BaseModel):
    """Same-SHA synthetic evidence for the complete offline P5 decision path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-pipeline-benchmark-v1"] = "decision-pipeline-benchmark-v1"
    fixture_version: Literal["decision-pipeline-golden-v1"] = "decision-pipeline-golden-v1"
    fixture_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    compatibility_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    risk_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    portfolio_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    python_version: str = Field(min_length=1, max_length=50)
    platform: str = Field(min_length=1, max_length=200)
    requested_samples: int = Field(ge=1)
    successful_samples: int = Field(ge=0)
    unique_output_fingerprints: tuple[str, ...]
    runtime_p50_ms: Decimal = Field(ge=0)
    runtime_p95_ms: Decimal = Field(ge=0)
    runtime_budget_ms: Decimal = Field(gt=0)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("benchmark timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        expected = {
            "fixture_checksum": decision_pipeline_benchmark_fixture_checksum(),
            "compatibility_policy_checksum": (
                strategy_context_compatibility_policy_v1().definition_checksum
            ),
            "candidate_policy_checksum": decision_candidate_policy_v1().definition_checksum,
            "risk_policy_checksum": decision_risk_policy_v1().definition_checksum,
            "portfolio_policy_checksum": decision_portfolio_policy_v1().definition_checksum,
        }
        for field_name, value in expected.items():
            if getattr(self, field_name) != value:
                raise ValueError(f"decision benchmark {field_name} is not canonical")
        if self.runtime_budget_ms != DECISION_PIPELINE_BENCHMARK_RUNTIME_BUDGET_MS:
            raise ValueError("decision benchmark runtime budget is not canonical")
        if self.successful_samples > self.requested_samples:
            raise ValueError("successful samples cannot exceed requested samples")
        return self

    @property
    def passed(self) -> bool:
        return (
            self.requested_samples >= DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES
            and self.successful_samples == self.requested_samples
            and len(self.unique_output_fingerprints) == 1
            and self.runtime_p95_ms <= self.runtime_budget_ms
        )


def run_decision_pipeline_benchmark(
    *, samples: int, commit_sha: str, environment_label: str
) -> DecisionPipelineBenchmarkReport:
    intent, dataset = _fixture_inputs()
    registry = build_default_strategy_registry()
    runtimes: list[Decimal] = []
    fingerprints: set[str] = set()
    for _ in range(samples):
        started = perf_counter()
        strategy = evaluate_strategy_intent(intent=intent, dataset=dataset, registry=registry)
        ranking = build_decision_candidate_ranking(
            intent=intent,
            strategy_evaluation=strategy,
            dataset=dataset,
        )
        risk = evaluate_decision_risk(ranking=ranking)
        sizing = risk.assessment.position_sizing
        if sizing is None:  # pragma: no cover - rejected fixtures fail the benchmark directly
            raise RuntimeError("decision benchmark risk fixture was rejected")
        snapshot = DecisionPortfolioSnapshot.build_empty(
            mode=intent.mode,
            dataset_id=intent.dataset.dataset_id,
            equity=sizing.reference_equity,
            as_of=risk.evaluated_at,
        )
        portfolio = evaluate_portfolio_intelligence(
            intent=intent,
            risk_gate=risk,
            snapshot=snapshot,
        )
        fingerprints.add(
            _checksum(
                {
                    "evaluation_id": intent.evaluation_id,
                    "portfolio_record_checksum": portfolio.record_checksum,
                    "ranking_record_checksum": ranking.record_checksum,
                    "risk_record_checksum": risk.record_checksum,
                    "stage_outcomes": [
                        strategy.outcome.outcome_checksum,
                        ranking.outcome.outcome_checksum,
                        risk.outcome.outcome_checksum,
                        portfolio.outcome.outcome_checksum,
                    ],
                    "strategy_record_checksum": strategy.record_checksum,
                }
            )
        )
        runtimes.append(Decimal(str((perf_counter() - started) * 1_000)))
    return DecisionPipelineBenchmarkReport(
        fixture_checksum=decision_pipeline_benchmark_fixture_checksum(),
        compatibility_policy_checksum=(
            strategy_context_compatibility_policy_v1().definition_checksum
        ),
        candidate_policy_checksum=decision_candidate_policy_v1().definition_checksum,
        risk_policy_checksum=decision_risk_policy_v1().definition_checksum,
        portfolio_policy_checksum=decision_portfolio_policy_v1().definition_checksum,
        commit_sha=commit_sha,
        environment_label=environment_label,
        generated_at=datetime.now(UTC),
        python_version=platform.python_version() or sys.version.split()[0],
        platform=platform.platform(),
        requested_samples=samples,
        successful_samples=len(runtimes),
        unique_output_fingerprints=tuple(sorted(fingerprints)),
        runtime_p50_ms=_percentile(runtimes, Decimal("0.50")),
        runtime_p95_ms=_percentile(runtimes, Decimal("0.95")),
        runtime_budget_ms=DECISION_PIPELINE_BENCHMARK_RUNTIME_BUDGET_MS,
    )


def serialize_decision_pipeline_benchmark_report(
    report: DecisionPipelineBenchmarkReport,
) -> str:
    payload = report.model_dump(mode="json")
    payload["passed"] = report.passed
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def parse_decision_pipeline_benchmark_report(
    value: str | bytes,
) -> DecisionPipelineBenchmarkReport:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("decision pipeline benchmark is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("decision pipeline benchmark must be a JSON object")
    payload = dict(raw)
    persisted_passed = payload.pop("passed", None)
    report = DecisionPipelineBenchmarkReport.model_validate(payload)
    if persisted_passed is not None and persisted_passed is not report.passed:
        raise ValueError("decision pipeline benchmark decision is inconsistent")
    return report
