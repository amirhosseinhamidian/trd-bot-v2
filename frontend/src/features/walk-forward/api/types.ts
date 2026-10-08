import type {
  BacktestConfig,
  ExperimentExecutionParameters,
  ExperimentExecutionStatus,
  ExperimentParameter,
  ResearchMetricDefinition,
  StoredDatasetEMACrossoverRequest,
  StoredDatasetRSIThresholdRequest,
  StoredDatasetSMACrossoverRequest,
} from '@/features/experiments/api/types';
import type { ResearchStrategyName } from '@/features/strategies/api/types';

export type WalkForwardRunSortField = 'created_at' | 'horizon_candles';

export type WalkForwardRunSortDirection = 'asc' | 'desc';

export type WalkForwardMode = 'rolling' | 'expanding';

export interface WalkForwardExecutionRequest {
  train_candles: number;
  test_candles: number;
  step_candles: number;
  gap_candles: number;
  mode: WalkForwardMode;
}

export interface StoredDatasetEMACrossoverWalkForwardRequest
  extends StoredDatasetEMACrossoverRequest, WalkForwardExecutionRequest {}

export interface StoredDatasetRSIThresholdWalkForwardRequest
  extends StoredDatasetRSIThresholdRequest, WalkForwardExecutionRequest {}

export interface StoredDatasetSMACrossoverWalkForwardRequest
  extends StoredDatasetSMACrossoverRequest, WalkForwardExecutionRequest {}

export interface StoredDatasetEMACrossoverWalkForwardExecutionRequest extends StoredDatasetEMACrossoverWalkForwardRequest {
  strategy_name: 'ema-crossover';
  strategy_version: '1.0.0';
}

export interface StoredDatasetRSIThresholdWalkForwardExecutionRequest extends StoredDatasetRSIThresholdWalkForwardRequest {
  strategy_name: 'rsi-threshold';
  strategy_version: '1.0.0';
}

export interface StoredDatasetSMACrossoverWalkForwardExecutionRequest extends StoredDatasetSMACrossoverWalkForwardRequest {
  strategy_name: 'sma-crossover';
  strategy_version: '1.0.0';
}

export type StoredDatasetStrategyWalkForwardExecutionRequest =
  | StoredDatasetEMACrossoverWalkForwardExecutionRequest
  | StoredDatasetRSIThresholdWalkForwardExecutionRequest
  | StoredDatasetSMACrossoverWalkForwardExecutionRequest;

export type WalkForwardExecutionStatus = ExperimentExecutionStatus;

export interface WalkForwardConfig {
  train_candles: number;
  test_candles: number;
  step_candles: number;
  gap_candles: number;
  mode: WalkForwardMode;
}

export interface WalkForwardExecution {
  execution_id: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  status: WalkForwardExecutionStatus;
  progress_percent: number;
  dataset_id: string;
  strategy_name: ResearchStrategyName;
  strategy_version: string;
  parameters: ExperimentExecutionParameters;
  walk_forward_config: WalkForwardConfig;
  total_folds: number;
  completed_folds: number;
  walk_forward_run_id: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface WalkForwardRunSummary {
  execution_id: string;
  created_at: string;
  source_dataset_id: string;
  plan_id: string;
  strategy_name: string;
  strategy_version: string;
  horizon_candles: number;
  strategy_parameters: ExperimentParameter[];
  walk_forward_config: WalkForwardConfig;
  backtest_config: BacktestConfig;
  total_folds: number;
  total_signals: number;
  folds_with_trades: number;
  strategy_wins: number;
  benchmark_wins: number;
  ties: number;
  average_strategy_return: string;
  average_benchmark_return: string;
  average_excess_return: string;
  worst_max_drawdown_fraction: string;
}

export type HistoricalFoldReturnDirection = 'positive' | 'negative' | 'flat';

export interface WalkForwardFoldStatistics {
  fold_number: number;
  total_trades: number;
  has_trades: boolean;
  strategy_return: string;
  benchmark_return: string;
  excess_return: string;
  max_drawdown_fraction: string;
  benchmark_max_drawdown_fraction: string;
  return_direction: HistoricalFoldReturnDirection;
}

export interface WalkForwardStabilityReport {
  stability_version: 'walk-forward-stability-v1';
  execution_id: string;
  total_folds: number;
  folds_with_trades: number;
  folds_without_trades: number;
  traded_fold_fraction: string;
  positive_return_folds: number;
  negative_return_folds: number;
  flat_return_folds: number;
  positive_return_fraction: string;
  outperforming_benchmark_folds: number;
  underperforming_benchmark_folds: number;
  benchmark_ties: number;
  average_strategy_return: string;
  median_strategy_return: string;
  best_strategy_return: string;
  worst_strategy_return: string;
  strategy_return_range: string;
  strategy_return_mean_absolute_deviation: string;
  return_consistency: string;
  average_excess_return: string;
  median_excess_return: string;
  worst_max_drawdown_fraction: string;
  worst_return_fold_number: number;
  worst_drawdown_fold_number: number;
  folds: WalkForwardFoldStatistics[];
  metric_definitions: ResearchMetricDefinition[];
  interpretation: 'historical_research_only';
}
