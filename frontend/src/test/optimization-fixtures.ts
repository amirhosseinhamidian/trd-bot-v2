import type {
  OptimizationExecution,
  OptimizationExecutionSubmission,
  OptimizationRobustnessPlan,
  OptimizationTrialEvaluation,
} from '@/features/optimizations/api/types';
import type { BackgroundJobSummary } from '@/features/jobs/api/types';

const backtestConfig = {
  starting_balance: '10000',
  allocation_fraction: '0.10',
  fee_rate: '0.001',
  slippage_rate: '0.0005',
};

const robustnessPlan: OptimizationRobustnessPlan = {
  policy_version: 'optimization-robustness-v1',
  score_version: 'optimization-robustness-score-v1',
  walk_forward_config: {
    train_candles: 120,
    test_candles: 24,
    step_candles: 24,
    gap_candles: 0,
    mode: 'rolling',
  },
  walk_forward_plan_id: 'walk-forward-1234567890abcdef',
  total_folds: 5,
  minimum_traded_folds: 1,
  validation_runs: 10,
  weights: {
    out_of_sample_objective: '0.45',
    median_excess_return: '0.15',
    positive_fold_fraction: '0.10',
    traded_fold_fraction: '0.10',
    return_dispersion_penalty: '0.05',
    drawdown_penalty: '0.05',
    generalization_gap_penalty: '0.10',
  },
};

function evaluation(
  trialNumber: number,
  experimentId: string,
  walkForwardRunId: string,
  eligible: boolean,
): OptimizationTrialEvaluation {
  return {
    trial_number: trialNumber,
    experiment_id: experimentId,
    walk_forward_run_id: walkForwardRunId,
    objective: 'excess_return',
    score_version: 'optimization-robustness-score-v1',
    total_folds: 5,
    traded_folds: eligible ? 4 : 0,
    in_sample_objective_value: eligible ? '0.08' : '0.04',
    out_of_sample_objective_value: eligible ? '0.04' : '-0.01',
    median_excess_return: eligible ? '0.02' : '-0.005',
    positive_return_fraction: eligible ? '0.8' : '0.2',
    traded_fold_fraction: eligible ? '0.8' : '0',
    return_mean_absolute_deviation: eligible ? '0.01' : '0.03',
    worst_max_drawdown_fraction: eligible ? '0.02' : '0.08',
    generalization_gap: eligible ? '0.04' : '0.05',
    eligible,
    rejection_reasons: eligible ? [] : ['insufficient_traded_folds'],
    breakdown: {
      out_of_sample_objective_contribution: eligible ? '0.018' : '-0.0045',
      median_excess_return_contribution: eligible ? '0.003' : '-0.00075',
      positive_fold_contribution: eligible ? '0.08' : '0.02',
      traded_fold_contribution: eligible ? '0.08' : '0',
      return_dispersion_penalty: eligible ? '0.0005' : '0.0015',
      drawdown_penalty: eligible ? '0.001' : '0.004',
      generalization_gap_penalty: eligible ? '0.004' : '0.005',
      total_score: eligible ? '0.1755' : '0.00425',
    },
  };
}

const plan = {
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  objective: 'excess_return' as const,
  requested_combinations: 2,
  skipped_combinations: 0,
  total_trials: 2,
  trials: [
    {
      trial_number: 1,
      parameters: [
        { name: 'fast_period', value: '9' },
        { name: 'slow_period', value: '21' },
      ],
    },
    {
      trial_number: 2,
      parameters: [
        { name: 'fast_period', value: '12' },
        { name: 'slow_period', value: '26' },
      ],
    },
  ],
};

export const queuedOptimizationExecution: OptimizationExecution = {
  execution_id: 'optimization-1234567890abcdef',
  created_at: '2026-09-26T12:00:00Z',
  updated_at: '2026-09-26T12:00:00Z',
  started_at: null,
  finished_at: null,
  status: 'queued',
  dataset_id: 'dataset-btc-usdt-1h',
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  objective: 'excess_return',
  plan,
  horizon_candles: 1,
  backtest_config: backtestConfig,
  robustness_plan: robustnessPlan,
  total_trials: 2,
  completed_trials: 0,
  experiment_ids: [],
  trial_evaluations: [],
  best_experiment_id: null,
  robustness_ranking: null,
  error_code: null,
  error_message: null,
};

const firstEvaluation = evaluation(
  1,
  'experiment-1234567890abcdef',
  'walk-forward-execution-1234567890abcdef',
  true,
);
const secondEvaluation = evaluation(
  2,
  'experiment-fedcba0987654321',
  'walk-forward-execution-fedcba0987654321',
  false,
);

export const successfulOptimizationExecution: OptimizationExecution = {
  ...queuedOptimizationExecution,
  updated_at: '2026-09-26T12:05:00Z',
  started_at: '2026-09-26T12:00:01Z',
  finished_at: '2026-09-26T12:05:00Z',
  status: 'succeeded',
  completed_trials: 2,
  experiment_ids: [firstEvaluation.experiment_id, secondEvaluation.experiment_id],
  trial_evaluations: [firstEvaluation, secondEvaluation],
  best_experiment_id: firstEvaluation.experiment_id,
  robustness_ranking: {
    score_version: 'optimization-robustness-score-v1',
    objective: 'excess_return',
    evaluated_trials: 2,
    eligible_trials: 1,
    rejected_trials: 1,
    best_experiment_id: firstEvaluation.experiment_id,
    entries: [
      {
        position: 1,
        evaluation: firstEvaluation,
      },
    ],
    interpretation: 'historical_research_only',
  },
};

const job: BackgroundJobSummary = {
  job_id: 'job-1234567890abcdef',
  kind: 'optimization_execution',
  status: 'queued',
  progress_percent: 0,
  attempt_count: 0,
  max_attempts: 3,
  run_after: '2026-09-26T12:00:00Z',
  lease_expires_at: null,
  cancel_requested: false,
  result_reference: null,
  error_code: null,
  error_message: null,
  created_at: '2026-09-26T12:00:00Z',
  updated_at: '2026-09-26T12:00:00Z',
  started_at: null,
  finished_at: null,
};

export const optimizationSubmission: OptimizationExecutionSubmission = {
  execution: queuedOptimizationExecution,
  job,
  created: true,
};
