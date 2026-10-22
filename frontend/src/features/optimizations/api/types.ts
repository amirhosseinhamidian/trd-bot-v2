import type {
  BacktestConfig,
  ExperimentComparisonMetric,
  ExperimentExecutionStatus,
  ExperimentParameter,
} from '@/features/experiments/api/types';
import type { BackgroundJobSummary } from '@/features/jobs/api/types';
import type { ResearchStrategyName } from '@/features/strategies/api/types';
import type { WalkForwardConfig } from '@/features/walk-forward/api/types';

export type OptimizationExecutionStatus = ExperimentExecutionStatus;

export interface OptimizationParameterGrid {
  name: string;
  values: string[];
}

export interface CreateOptimizationExecutionRequest {
  dataset_id: string;
  strategy_name: ResearchStrategyName;
  strategy_version: string;
  objective: ExperimentComparisonMetric;
  parameter_grid: OptimizationParameterGrid[];
  horizon_candles: number;
  backtest_config: BacktestConfig;
  walk_forward_config: WalkForwardConfig;
}

export interface OptimizationTrial {
  trial_number: number;
  parameters: ExperimentParameter[];
}

export interface OptimizationPlan {
  strategy_name: string;
  strategy_version: string;
  objective: ExperimentComparisonMetric;
  requested_combinations: number;
  skipped_combinations: number;
  total_trials: number;
  trials: OptimizationTrial[];
}

export interface OptimizationRobustnessWeights {
  out_of_sample_objective: string;
  median_excess_return: string;
  positive_fold_fraction: string;
  traded_fold_fraction: string;
  return_dispersion_penalty: string;
  drawdown_penalty: string;
  generalization_gap_penalty: string;
}

export interface OptimizationRobustnessPlan {
  policy_version: 'optimization-robustness-v1';
  score_version: 'optimization-robustness-score-v1';
  walk_forward_config: WalkForwardConfig;
  walk_forward_plan_id: string;
  total_folds: number;
  minimum_traded_folds: number;
  validation_runs: number;
  weights: OptimizationRobustnessWeights;
}

export type OptimizationTrialRejectionReason = 'insufficient_traded_folds';

export interface OptimizationRobustnessBreakdown {
  out_of_sample_objective_contribution: string;
  median_excess_return_contribution: string;
  positive_fold_contribution: string;
  traded_fold_contribution: string;
  return_dispersion_penalty: string;
  drawdown_penalty: string;
  generalization_gap_penalty: string;
  total_score: string;
}

export interface OptimizationTrialEvaluation {
  trial_number: number;
  experiment_id: string;
  walk_forward_run_id: string;
  objective: ExperimentComparisonMetric;
  score_version: 'optimization-robustness-score-v1';
  total_folds: number;
  traded_folds: number;
  in_sample_objective_value: string;
  out_of_sample_objective_value: string;
  median_excess_return: string;
  positive_return_fraction: string;
  traded_fold_fraction: string;
  return_mean_absolute_deviation: string;
  worst_max_drawdown_fraction: string;
  generalization_gap: string;
  eligible: boolean;
  rejection_reasons: OptimizationTrialRejectionReason[];
  breakdown: OptimizationRobustnessBreakdown;
}

export interface OptimizationRobustnessRankingEntry {
  position: number;
  evaluation: OptimizationTrialEvaluation;
}

export interface OptimizationRobustnessRankingResult {
  score_version: 'optimization-robustness-score-v1';
  objective: ExperimentComparisonMetric;
  evaluated_trials: number;
  eligible_trials: number;
  rejected_trials: number;
  best_experiment_id: string;
  entries: OptimizationRobustnessRankingEntry[];
  interpretation: 'historical_research_only';
}

export interface OptimizationExecution {
  execution_id: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  status: OptimizationExecutionStatus;
  dataset_id: string;
  strategy_name: string;
  strategy_version: string;
  objective: ExperimentComparisonMetric;
  plan: OptimizationPlan;
  horizon_candles: number;
  backtest_config: BacktestConfig;
  robustness_plan: OptimizationRobustnessPlan | null;
  total_trials: number;
  completed_trials: number;
  experiment_ids: string[];
  trial_evaluations: OptimizationTrialEvaluation[];
  best_experiment_id: string | null;
  robustness_ranking: OptimizationRobustnessRankingResult | null;
  error_code: string | null;
  error_message: string | null;
}

export interface OptimizationExecutionSubmission {
  execution: OptimizationExecution;
  job: BackgroundJobSummary;
  created: boolean;
}
