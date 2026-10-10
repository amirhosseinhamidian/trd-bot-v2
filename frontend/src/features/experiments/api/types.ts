import type { ResearchStrategyName } from '@/features/strategies/api/types';
import type { BackgroundJobSummary } from '@/features/jobs/api/types';

export type ExperimentSortField = 'created_at' | 'horizon_candles';

export type ExperimentSortDirection = 'asc' | 'desc';

export interface StoredDatasetHistoricalExecutionRequest {
  dataset_id: string;
  horizon_candles: number;
  starting_balance: string;
  allocation_fraction: string;
  fee_rate: string;
  slippage_rate: string;
}

export interface StoredDatasetEMACrossoverRequest extends StoredDatasetHistoricalExecutionRequest {
  fast_period: number;
  slow_period: number;
}

export interface StoredDatasetRSIThresholdRequest extends StoredDatasetHistoricalExecutionRequest {
  period: number;
  oversold_threshold: string;
  overbought_threshold: string;
}

export interface StoredDatasetSMACrossoverRequest extends StoredDatasetHistoricalExecutionRequest {
  fast_period: number;
  slow_period: number;
}

export interface StoredDatasetEMACrossoverExecutionRequest extends StoredDatasetEMACrossoverRequest {
  strategy_name: 'ema-crossover';
  strategy_version: '1.0.0';
}

export interface StoredDatasetRSIThresholdExecutionRequest extends StoredDatasetRSIThresholdRequest {
  strategy_name: 'rsi-threshold';
  strategy_version: '1.0.0';
}

export interface StoredDatasetSMACrossoverExecutionRequest extends StoredDatasetSMACrossoverRequest {
  strategy_name: 'sma-crossover';
  strategy_version: '1.0.0';
}

export type StoredDatasetStrategyExecutionRequest =
  | StoredDatasetEMACrossoverExecutionRequest
  | StoredDatasetRSIThresholdExecutionRequest
  | StoredDatasetSMACrossoverExecutionRequest;

export type ExperimentExecutionStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface HistoricalExecutionParameters {
  horizon_candles: number;
  starting_balance: string;
  allocation_fraction: string;
  fee_rate: string;
  slippage_rate: string;
}

export interface EMACrossoverExecutionParameters extends HistoricalExecutionParameters {
  fast_period: number;
  slow_period: number;
}

export interface RSIThresholdExecutionParameters extends HistoricalExecutionParameters {
  period: number;
  oversold_threshold: string;
  overbought_threshold: string;
}

export interface SMACrossoverExecutionParameters extends HistoricalExecutionParameters {
  fast_period: number;
  slow_period: number;
}

export type ExperimentExecutionParameters =
  | EMACrossoverExecutionParameters
  | RSIThresholdExecutionParameters
  | SMACrossoverExecutionParameters;

export interface ExperimentExecution {
  execution_id: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  status: ExperimentExecutionStatus;
  progress_percent: number;
  dataset_id: string;
  strategy_name: ResearchStrategyName;
  strategy_version: string;
  parameters: ExperimentExecutionParameters;
  experiment_id: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface ExperimentExecutionSubmission extends ExperimentExecution {
  job: BackgroundJobSummary;
  created: boolean;
}

export interface CreatedResearchExperiment {
  experiment_id: string;
}

export interface ExperimentParameter {
  name: string;
  value: string;
}

export interface ExperimentSummary {
  experiment_id: string;
  created_at: string;
  dataset_id: string;
  strategy_name: string;
  strategy_version: string;
  strategy_fingerprint?: string | null;
  horizon_candles: number;
  parameters: ExperimentParameter[];
  generated_signals: number;
  total_trades: number;
  net_pnl: string;
  total_return: string;
  win_rate: string | null;
  max_drawdown_fraction: string;
  profit_factor: string | null;
  benchmark_type: 'buy_and_hold';
  benchmark_return: string;
  excess_return: string;
  benchmark_max_drawdown_fraction: string;
  max_drawdown_fraction_delta: string;
  strategy_has_lower_drawdown: boolean;
  comparison_outcome: 'strategy' | 'benchmark' | 'tie';
}

export type ExperimentReplayStatus = 'verified' | 'mismatch' | 'unverifiable';

export type ExperimentReplayCode =
  | 'verified'
  | 'legacy_fingerprint_missing'
  | 'dataset_not_found'
  | 'dataset_integrity_mismatch'
  | 'strategy_version_not_found'
  | 'strategy_fingerprint_mismatch'
  | 'invalid_strategy_parameters'
  | 'replay_failed'
  | 'result_mismatch';

export interface ExperimentReplayVerification {
  experiment_id: string;
  checked_at: string;
  status: ExperimentReplayStatus;
  code: ExperimentReplayCode;
  dataset_id: string;
  strategy_name: string;
  strategy_version: string;
  recorded_strategy_fingerprint: string | null;
  current_strategy_fingerprint: string | null;
  recorded_result_checksum: string;
  replayed_result_checksum: string | null;
  mismatch_fields: string[];
}

export type ExperimentComparisonMetric = 'excess_return' | 'total_return' | 'max_drawdown_fraction';

export type ExperimentComparisonRankingDirection = 'higher_is_better' | 'lower_is_better';

export interface ExperimentComparisonRequest {
  experiment_ids: string[];
  metric: ExperimentComparisonMetric;
}

export interface ExperimentComparisonEntry {
  position: number;
  metric_value: string;
  experiment: ExperimentSummary;
}

export interface ExperimentComparisonResult {
  dataset_id: string;
  horizon_candles: number;
  metric: ExperimentComparisonMetric;
  ranking_direction: ExperimentComparisonRankingDirection;
  compared_experiments: number;
  best_experiment_id: string;
  entries: ExperimentComparisonEntry[];
  interpretation: 'historical_research_only';
}

export type ResearchMetricKey =
  | 'total_return'
  | 'excess_return'
  | 'max_drawdown_fraction'
  | 'win_rate'
  | 'profit_factor'
  | 'period_return_contribution'
  | 'median_fold_return'
  | 'worst_fold_return'
  | 'traded_fold_fraction'
  | 'return_consistency'
  | 'fold_drawdown';

export interface ResearchMetricDefinition {
  key: ResearchMetricKey;
  unit: 'fraction' | 'currency' | 'count' | 'ratio';
  preference: 'higher_is_better' | 'lower_is_better' | 'context_only';
  definition: string;
  formula: string;
}

export interface BacktestConfig {
  starting_balance: string;
  allocation_fraction: string;
  fee_rate: string;
  slippage_rate: string;
}

export interface AcceptancePolicy {
  minimum_total_trades: number;
  minimum_excess_return: string;
  maximum_drawdown_fraction: string;
}

export interface AcceptancePolicyPreset {
  preset_id: string;
  name: string;
  version: number;
  description: string;
  policy: AcceptancePolicy;
  interpretation: 'historical_research_only';
}

export type ExperimentAcceptanceOutcome = 'accepted' | 'rejected' | 'insufficient_data';

export type ExperimentAcceptanceCheckName =
  'minimum_total_trades' | 'minimum_excess_return' | 'maximum_drawdown_fraction';

export type ExperimentAcceptanceComparison = 'greater_than_or_equal' | 'less_than_or_equal';

export interface ExperimentAcceptanceCheck {
  name: ExperimentAcceptanceCheckName;
  passed: boolean;
  actual_value: string;
  threshold_value: string;
  comparison: ExperimentAcceptanceComparison;
}

export interface ExperimentAcceptanceResult {
  experiment_id: string;
  outcome: ExperimentAcceptanceOutcome;
  policy: AcceptancePolicy;
  checks: ExperimentAcceptanceCheck[];
  interpretation: 'historical_research_only';
}

export interface HistoricalBenchmarkContext {
  benchmark_type: 'buy_and_hold';
  strategy_total_return: string;
  benchmark_return: string;
  excess_return: string;
  comparison_outcome: 'strategy' | 'benchmark' | 'tie';
  strategy_max_drawdown_fraction: string;
  benchmark_max_drawdown_fraction: string;
  drawdown_comparison: 'lower' | 'equal' | 'higher';
}

export interface ExperimentResearchReport {
  experiment: ExperimentSummary;
  benchmark_context: HistoricalBenchmarkContext;
  acceptance: ExperimentAcceptanceResult;
  passed_checks: number;
  failed_checks: number;
  interpretation: 'historical_research_only';
}

export interface PresetExperimentResearchReport {
  preset: AcceptancePolicyPreset;
  report: ExperimentResearchReport;
  interpretation: 'historical_research_only';
}

export interface HistoricalEquityPoint {
  trade_number: number;
  timestamp: string;
  balance: string;
  peak_balance: string;
  drawdown: string;
  drawdown_fraction: string;
}

export type HistoricalPerformancePointKind = 'period_start' | 'trade_close' | 'period_end';

export interface HistoricalPerformancePoint {
  timestamp: string;
  balance: string;
  drawdown_fraction: string;
  kind: HistoricalPerformancePointKind;
  trade_number: number | null;
}

export interface HistoricalPerformanceSeries {
  run_id: string;
  starting_balance: string;
  ending_balance: string;
  total_return: string;
  max_drawdown_fraction: string;
  points: HistoricalEquityPoint[];
  chart_points: HistoricalPerformancePoint[];
}

export interface ExperimentPerformanceSeries {
  experiment_id: string;
  dataset_id: string;
  benchmark_type: 'buy_and_hold';
  period_start: string;
  period_end: string;
  strategy: HistoricalPerformanceSeries;
  benchmark: HistoricalPerformanceSeries;
  interpretation: 'historical_research_only';
}

export interface ExperimentTradeDistribution {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  flat_trades: number;
  long_trades: number;
  short_trades: number;
  win_rate: string | null;
  gross_profit: string;
  gross_loss: string;
  total_fees: string;
  net_pnl: string;
  profit_factor: string | null;
  average_net_pnl: string | null;
  median_net_pnl: string | null;
  best_net_pnl: string | null;
  worst_net_pnl: string | null;
}

export interface ExperimentPeriodReturn {
  period: string;
  started_at: string;
  ended_at: string;
  opening_balance: string;
  ending_balance: string;
  net_pnl: string;
  return_contribution: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  flat_trades: number;
}

export type HistoricalDrawdownEpisodeStatus = 'recovered' | 'unrecovered';

export interface HistoricalDrawdownEpisode {
  episode_number: number;
  started_at: string;
  trough_at: string;
  recovered_at: string | null;
  peak_balance: string;
  trough_balance: string;
  max_drawdown: string;
  max_drawdown_fraction: string;
  trades_underwater: number;
  status: HistoricalDrawdownEpisodeStatus;
}

export interface ExperimentAnalyticsReport {
  experiment_id: string;
  dataset_id: string;
  analytics_version: 'research-analytics-v1';
  period_granularity: 'utc_calendar_month';
  period_start: string;
  period_end: string;
  starting_balance: string;
  ending_balance: string;
  strategy_total_return: string;
  benchmark_total_return: string;
  excess_return: string;
  strategy_max_drawdown_fraction: string;
  benchmark_max_drawdown_fraction: string;
  trade_distribution: ExperimentTradeDistribution;
  returns_by_period: ExperimentPeriodReturn[];
  drawdown_episodes: HistoricalDrawdownEpisode[];
  metric_definitions: ResearchMetricDefinition[];
  interpretation: 'historical_research_only';
}
