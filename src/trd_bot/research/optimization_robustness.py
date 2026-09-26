from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.experiments import ExperimentSummary
from trd_bot.research.walk_forward import WalkForwardConfig, WalkForwardPlanner
from trd_bot.research.walk_forward_reporting import WalkForwardStabilityReport

MIN_OPTIMIZATION_FOLDS = 3
MAX_OPTIMIZATION_FOLDS = 12
MAX_OPTIMIZATION_VALIDATION_RUNS = 300


class OptimizationRobustnessWeights(BaseModel):
    """Version-one weights for out-of-sample robustness evidence."""

    model_config = ConfigDict(frozen=True)

    out_of_sample_objective: Decimal = Decimal("0.45")
    median_excess_return: Decimal = Decimal("0.15")
    positive_fold_fraction: Decimal = Decimal("0.10")
    traded_fold_fraction: Decimal = Decimal("0.10")
    return_dispersion_penalty: Decimal = Decimal("0.05")
    drawdown_penalty: Decimal = Decimal("0.05")
    generalization_gap_penalty: Decimal = Decimal("0.10")

    @model_validator(mode="after")
    def weights_are_fixed_and_complete(self) -> Self:
        expected = (
            Decimal("0.45"),
            Decimal("0.15"),
            Decimal("0.10"),
            Decimal("0.10"),
            Decimal("0.05"),
            Decimal("0.05"),
            Decimal("0.10"),
        )
        actual = (
            self.out_of_sample_objective,
            self.median_excess_return,
            self.positive_fold_fraction,
            self.traded_fold_fraction,
            self.return_dispersion_penalty,
            self.drawdown_penalty,
            self.generalization_gap_penalty,
        )
        if actual != expected:
            raise ValueError("optimization robustness v1 weights are immutable")
        if sum(actual, start=Decimal("0")) != Decimal("1"):
            raise ValueError("optimization robustness weights must sum to one")
        return self


class OptimizationRobustnessPlan(BaseModel):
    """Bounded and reproducible walk-forward policy for one optimization."""

    model_config = ConfigDict(frozen=True)

    policy_version: Literal["optimization-robustness-v1"] = "optimization-robustness-v1"
    score_version: Literal["optimization-robustness-score-v1"] = "optimization-robustness-score-v1"
    walk_forward_config: WalkForwardConfig
    walk_forward_plan_id: str = Field(pattern=r"^walk-forward-[a-f0-9]{16}$")
    total_folds: int = Field(ge=MIN_OPTIMIZATION_FOLDS, le=MAX_OPTIMIZATION_FOLDS)
    minimum_traded_folds: int = Field(default=1, ge=1)
    validation_runs: int = Field(ge=1, le=MAX_OPTIMIZATION_VALIDATION_RUNS)
    weights: OptimizationRobustnessWeights = Field(default_factory=OptimizationRobustnessWeights)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.minimum_traded_folds != 1:
            raise ValueError("optimization robustness v1 minimum traded folds is immutable")
        if self.minimum_traded_folds > self.total_folds:
            raise ValueError("minimum traded folds cannot exceed total folds")
        return self


class OptimizationRobustnessPlanner:
    """Validate fold count and total work before a durable job is enqueued."""

    def __init__(self, walk_forward_planner: WalkForwardPlanner | None = None) -> None:
        self._walk_forward_planner = walk_forward_planner or WalkForwardPlanner()

    def plan(
        self,
        *,
        dataset: DatasetSnapshot,
        walk_forward_config: WalkForwardConfig,
        optimization_trials: int,
    ) -> OptimizationRobustnessPlan:
        walk_forward_plan = self._walk_forward_planner.plan(
            dataset=dataset,
            config=walk_forward_config,
        )
        total_folds = len(walk_forward_plan.folds)
        if total_folds < MIN_OPTIMIZATION_FOLDS:
            raise ValueError(
                f"optimization robustness requires at least {MIN_OPTIMIZATION_FOLDS} folds"
            )
        if total_folds > MAX_OPTIMIZATION_FOLDS:
            raise ValueError(
                f"optimization robustness allows at most {MAX_OPTIMIZATION_FOLDS} folds"
            )

        validation_runs = total_folds * optimization_trials
        if validation_runs > MAX_OPTIMIZATION_VALIDATION_RUNS:
            raise ValueError(
                "optimization robustness exceeds the maximum of "
                f"{MAX_OPTIMIZATION_VALIDATION_RUNS} trial-fold runs"
            )

        return OptimizationRobustnessPlan(
            walk_forward_config=walk_forward_config,
            walk_forward_plan_id=walk_forward_plan.plan_id,
            total_folds=total_folds,
            validation_runs=validation_runs,
        )


class OptimizationTrialRejectionReason(StrEnum):
    """Fail-closed reasons that exclude a trial from final ranking."""

    INSUFFICIENT_TRADED_FOLDS = "insufficient_traded_folds"


class OptimizationRobustnessBreakdown(BaseModel):
    """Auditable weighted components of one robustness score."""

    model_config = ConfigDict(frozen=True)

    out_of_sample_objective_contribution: Decimal
    median_excess_return_contribution: Decimal
    positive_fold_contribution: Decimal
    traded_fold_contribution: Decimal
    return_dispersion_penalty: Decimal = Field(ge=0)
    drawdown_penalty: Decimal = Field(ge=0)
    generalization_gap_penalty: Decimal = Field(ge=0)
    total_score: Decimal

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        expected = (
            self.out_of_sample_objective_contribution
            + self.median_excess_return_contribution
            + self.positive_fold_contribution
            + self.traded_fold_contribution
            - self.return_dispersion_penalty
            - self.drawdown_penalty
            - self.generalization_gap_penalty
        )
        if self.total_score != expected:
            raise ValueError("optimization robustness score breakdown is inconsistent")
        return self


class OptimizationTrialEvaluation(BaseModel):
    """Persisted in-sample and out-of-sample evidence for one trial."""

    model_config = ConfigDict(frozen=True)

    trial_number: int = Field(ge=1)
    experiment_id: str = Field(min_length=1, max_length=100)
    walk_forward_run_id: str = Field(pattern=r"^walk-forward-execution-[a-f0-9]{16}$")
    objective: ExperimentComparisonMetric
    score_version: Literal["optimization-robustness-score-v1"] = "optimization-robustness-score-v1"
    total_folds: int = Field(ge=1)
    traded_folds: int = Field(ge=0)
    in_sample_objective_value: Decimal
    out_of_sample_objective_value: Decimal
    median_excess_return: Decimal
    positive_return_fraction: Decimal = Field(ge=0, le=1)
    traded_fold_fraction: Decimal = Field(ge=0, le=1)
    return_mean_absolute_deviation: Decimal = Field(ge=0)
    worst_max_drawdown_fraction: Decimal = Field(ge=0)
    generalization_gap: Decimal = Field(ge=0)
    eligible: bool
    rejection_reasons: tuple[OptimizationTrialRejectionReason, ...] = ()
    breakdown: OptimizationRobustnessBreakdown

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        if self.traded_folds > self.total_folds:
            raise ValueError("traded folds cannot exceed total folds")
        expected_fraction = Decimal(self.traded_folds) / Decimal(self.total_folds)
        if self.traded_fold_fraction != expected_fraction:
            raise ValueError("traded fold fraction is inconsistent")
        if self.eligible == bool(self.rejection_reasons):
            raise ValueError("optimization trial eligibility is inconsistent")
        return self


class OptimizationRobustnessRankingEntry(BaseModel):
    """One eligible trial in deterministic robustness order."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=1)
    evaluation: OptimizationTrialEvaluation

    @model_validator(mode="after")
    def require_eligible_evaluation(self) -> Self:
        if not self.evaluation.eligible:
            raise ValueError("robustness ranking cannot contain an ineligible trial")
        return self


class OptimizationRobustnessRankingResult(BaseModel):
    """Versioned ranking selected from eligible out-of-sample evidence."""

    model_config = ConfigDict(frozen=True)

    score_version: Literal["optimization-robustness-score-v1"] = "optimization-robustness-score-v1"
    objective: ExperimentComparisonMetric
    evaluated_trials: int = Field(ge=1)
    eligible_trials: int = Field(ge=1)
    rejected_trials: int = Field(ge=0)
    best_experiment_id: str = Field(min_length=1, max_length=100)
    entries: tuple[OptimizationRobustnessRankingEntry, ...] = Field(min_length=1)
    interpretation: Literal["historical_research_only"] = "historical_research_only"

    @model_validator(mode="after")
    def validate_ranking(self) -> Self:
        if self.evaluated_trials != self.eligible_trials + self.rejected_trials:
            raise ValueError("robustness ranking trial counts are inconsistent")
        if self.eligible_trials != len(self.entries):
            raise ValueError("robustness ranking entry count is inconsistent")
        for position, entry in enumerate(self.entries, start=1):
            if entry.position != position:
                raise ValueError("robustness ranking positions must be continuous")
        if self.entries[0].evaluation.experiment_id != self.best_experiment_id:
            raise ValueError("robustness ranking best experiment is inconsistent")
        return self


class OptimizationRobustnessScorer:
    """Score and rank trials using bounded out-of-sample evidence."""

    def evaluate(
        self,
        *,
        trial_number: int,
        experiment: ExperimentSummary,
        stability: WalkForwardStabilityReport,
        policy: OptimizationRobustnessPlan,
        objective: ExperimentComparisonMetric,
    ) -> OptimizationTrialEvaluation:
        if stability.total_folds != policy.total_folds:
            raise ValueError("walk-forward evidence does not match robustness plan")

        traded_folds = sum(fold.total_trades > 0 for fold in stability.folds)
        traded_fold_fraction = Decimal(traded_folds) / Decimal(stability.total_folds)
        in_sample_value = self._in_sample_value(
            experiment,
            objective=objective,
        )
        out_of_sample_value = self._out_of_sample_value(
            stability,
            objective=objective,
        )
        oriented_in_sample = self._oriented_value(
            in_sample_value,
            objective=objective,
        )
        oriented_out_of_sample = self._oriented_value(
            out_of_sample_value,
            objective=objective,
        )
        generalization_gap = max(
            Decimal("0"),
            oriented_in_sample - oriented_out_of_sample,
        )
        weights = policy.weights
        breakdown = OptimizationRobustnessBreakdown(
            out_of_sample_objective_contribution=(
                oriented_out_of_sample * weights.out_of_sample_objective
            ),
            median_excess_return_contribution=(
                stability.median_excess_return * weights.median_excess_return
            ),
            positive_fold_contribution=(
                stability.positive_return_fraction * weights.positive_fold_fraction
            ),
            traded_fold_contribution=(traded_fold_fraction * weights.traded_fold_fraction),
            return_dispersion_penalty=(
                stability.strategy_return_mean_absolute_deviation
                * weights.return_dispersion_penalty
            ),
            drawdown_penalty=(stability.worst_max_drawdown_fraction * weights.drawdown_penalty),
            generalization_gap_penalty=(generalization_gap * weights.generalization_gap_penalty),
            total_score=(
                oriented_out_of_sample * weights.out_of_sample_objective
                + stability.median_excess_return * weights.median_excess_return
                + stability.positive_return_fraction * weights.positive_fold_fraction
                + traded_fold_fraction * weights.traded_fold_fraction
                - stability.strategy_return_mean_absolute_deviation
                * weights.return_dispersion_penalty
                - stability.worst_max_drawdown_fraction * weights.drawdown_penalty
                - generalization_gap * weights.generalization_gap_penalty
            ),
        )

        rejection_reasons: tuple[OptimizationTrialRejectionReason, ...] = ()
        if traded_folds < policy.minimum_traded_folds:
            rejection_reasons = (OptimizationTrialRejectionReason.INSUFFICIENT_TRADED_FOLDS,)

        return OptimizationTrialEvaluation(
            trial_number=trial_number,
            experiment_id=experiment.experiment_id,
            walk_forward_run_id=stability.execution_id,
            objective=objective,
            total_folds=stability.total_folds,
            traded_folds=traded_folds,
            in_sample_objective_value=in_sample_value,
            out_of_sample_objective_value=out_of_sample_value,
            median_excess_return=stability.median_excess_return,
            positive_return_fraction=stability.positive_return_fraction,
            traded_fold_fraction=traded_fold_fraction,
            return_mean_absolute_deviation=(stability.strategy_return_mean_absolute_deviation),
            worst_max_drawdown_fraction=stability.worst_max_drawdown_fraction,
            generalization_gap=generalization_gap,
            eligible=not rejection_reasons,
            rejection_reasons=rejection_reasons,
            breakdown=breakdown,
        )

    def rank(
        self,
        *,
        evaluations: Sequence[OptimizationTrialEvaluation],
        objective: ExperimentComparisonMetric,
    ) -> OptimizationRobustnessRankingResult:
        selected = tuple(evaluations)
        if not selected:
            raise ValueError("at least one robustness evaluation is required")
        experiment_ids = {evaluation.experiment_id for evaluation in selected}
        if len(experiment_ids) != len(selected):
            raise ValueError("robustness evaluation experiment IDs must be unique")
        if any(evaluation.objective is not objective for evaluation in selected):
            raise ValueError("robustness evaluations must share the selected objective")

        eligible = tuple(evaluation for evaluation in selected if evaluation.eligible)
        if not eligible:
            raise ValueError("optimization contains no robustness-eligible trial")
        ordered = tuple(sorted(eligible, key=self._ranking_key))
        entries = tuple(
            OptimizationRobustnessRankingEntry(position=position, evaluation=evaluation)
            for position, evaluation in enumerate(ordered, start=1)
        )
        return OptimizationRobustnessRankingResult(
            objective=objective,
            evaluated_trials=len(selected),
            eligible_trials=len(eligible),
            rejected_trials=len(selected) - len(eligible),
            best_experiment_id=ordered[0].experiment_id,
            entries=entries,
        )

    @staticmethod
    def _ranking_key(
        evaluation: OptimizationTrialEvaluation,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal, str]:
        oriented_out_of_sample = OptimizationRobustnessScorer._oriented_value(
            evaluation.out_of_sample_objective_value,
            objective=evaluation.objective,
        )
        return (
            -evaluation.breakdown.total_score,
            -oriented_out_of_sample,
            -evaluation.median_excess_return,
            evaluation.worst_max_drawdown_fraction,
            evaluation.experiment_id,
        )

    @staticmethod
    def _in_sample_value(
        experiment: ExperimentSummary,
        *,
        objective: ExperimentComparisonMetric,
    ) -> Decimal:
        if objective is ExperimentComparisonMetric.TOTAL_RETURN:
            return experiment.total_return
        if objective is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return experiment.max_drawdown_fraction
        return experiment.excess_return

    @staticmethod
    def _out_of_sample_value(
        stability: WalkForwardStabilityReport,
        *,
        objective: ExperimentComparisonMetric,
    ) -> Decimal:
        if objective is ExperimentComparisonMetric.TOTAL_RETURN:
            return stability.average_strategy_return
        if objective is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return stability.worst_max_drawdown_fraction
        return stability.average_excess_return

    @staticmethod
    def _oriented_value(
        value: Decimal,
        *,
        objective: ExperimentComparisonMetric,
    ) -> Decimal:
        if objective is ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION:
            return -value
        return value
