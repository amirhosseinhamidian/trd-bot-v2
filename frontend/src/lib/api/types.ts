export type ResearchStage =
  'empty' | 'data_available' | 'experiments_available' | 'walk_forward_available';

export type ResearchActivityType = 'dataset' | 'experiment' | 'walk_forward_run';

export type DatasetTimeframe = '15m' | '1h' | '4h' | '1d';

export type MarketType = 'spot';

export type MarketDataConnectionState = 'disabled' | 'enabled';

export type MarketDataConnectionHealth = 'untested' | 'healthy' | 'unhealthy';

export type MarketDataProviderAccessMode = 'direct' | 'vpn_required';

export type MarketDataProviderErrorCode =
  | 'provider_request_failed'
  | 'provider_timeout'
  | 'provider_rate_limited'
  | 'provider_http_error'
  | 'provider_response_invalid'
  | 'provider_unavailable';

export interface MarketDataProviderSummary {
  provider_id: string;
  display_name: string;
  requires_credentials: boolean;
  supported_market_types: MarketType[];
  supported_timeframes: DatasetTimeframe[];
  default_pair: TradingPair;
  access_mode: MarketDataProviderAccessMode;
  max_closed_candles: number | null;
  normalization_version?: string | null;
}

export interface MarketDataConnection {
  connection_id: string;
  provider_id: string;
  display_name: string;
  state: MarketDataConnectionState;
  health_status: MarketDataConnectionHealth;
  created_at: string;
  updated_at: string;
  last_tested_at: string | null;
  last_error_code: MarketDataProviderErrorCode | null;
  last_error: string | null;
}

export interface MarketDataConnectionCreateRequest {
  provider_id: string;
  display_name: string;
}

export type MarketDataQualityIssueCode =
  | 'empty_data'
  | 'mixed_series'
  | 'duplicate_timestamp'
  | 'out_of_order'
  | 'missing_candle'
  | 'open_candle'
  | 'incomplete_start'
  | 'incomplete_end'
  | 'outside_requested_range'
  | 'unaligned_candle';

export interface MarketDataQualityIssue {
  code: MarketDataQualityIssueCode;
  message: string;
  timestamp: string | null;
}

export interface MarketDataCoverageReport {
  requested_start_time: string;
  requested_end_time: string;
  expected_first_open_time: string | null;
  expected_last_open_time: string | null;
  actual_first_open_time: string | null;
  actual_last_close_time: string | null;
  expected_candles: number;
  received_candles: number;
  missing_candles: number;
  coverage_percent: number;
  complete: boolean;
}

export interface MarketDataQualityScore {
  score_version: 'quality-score-v1';
  score_percent: number;
  coverage_percent: number;
  integrity_percent: number;
}

export interface MarketDataQualityAcceptance {
  policy_version: 'strict-quality-v1';
  accepted: boolean;
  minimum_score_percent: number;
  blocking_issue_codes: MarketDataQualityIssueCode[];
}

export interface MarketDataQualityReport {
  candles_checked: number;
  issues: MarketDataQualityIssue[];
  coverage: MarketDataCoverageReport | null;
  score: MarketDataQualityScore | null;
  acceptance: MarketDataQualityAcceptance | null;
}

export interface HistoricalDatasetImportRequest {
  name: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  start_time: string;
  end_time: string;
}

export interface HistoricalDatasetCommitRequest extends HistoricalDatasetImportRequest {
  preview_checksum: string;
}

export interface HistoricalDatasetImportPreview {
  connection_id: string;
  provider_id: string;
  name: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  requested_start_time: string;
  requested_end_time: string;
  candle_count: number;
  first_open_time: string | null;
  last_close_time: string | null;
  preview_checksum: string;
  quality_report: MarketDataQualityReport;
  ready_to_import: boolean;
}

export type BackgroundJobKind =
  | 'experiment_execution'
  | 'walk_forward_execution'
  | 'market_data_import'
  | 'dataset_file_import'
  | 'optimization_execution';

export type BackgroundJobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface BackgroundJobSummary {
  job_id: string;
  kind: BackgroundJobKind;
  status: BackgroundJobStatus;
  progress_percent: number;
  attempt_count: number;
  max_attempts: number;
  run_after: string;
  lease_expires_at: string | null;
  cancel_requested: boolean;
  result_reference: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export type MarketDataImportStatus = 'succeeded' | 'failed';

export type MarketDataImportOperation = 'import' | 'refresh';

export interface MarketDataImportRecord {
  import_id: string;
  connection_id: string;
  provider_id: string;
  dataset_name: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  requested_start_time: string;
  requested_end_time: string;
  created_at: string;
  completed_at: string;
  status: MarketDataImportStatus;
  candle_count: number;
  dataset_id: string | null;
  error_code: string | null;
  error_message: string | null;
  quality_report: MarketDataQualityReport | null;
  operation: MarketDataImportOperation;
  source_dataset_id: string | null;
  root_import_id: string | null;
  parent_import_id: string | null;
  version_number: number | null;
  content_changed: boolean | null;
}

export type DatasetSortField = 'created_at' | 'start_time' | 'candle_count';

export type DatasetSortDirection = 'asc' | 'desc';

export type ExperimentSortField = 'created_at' | 'horizon_candles';

export type ExperimentSortDirection = 'asc' | 'desc';

export type WalkForwardRunSortField = 'created_at' | 'horizon_candles';

export type WalkForwardRunSortDirection = 'asc' | 'desc';

export type WalkForwardMode = 'rolling' | 'expanding';

export interface TradingPair {
  base_asset: string;
  quote_asset: string;
  market_type: MarketType;
}

export interface DatasetSummary {
  dataset_id: string;
  schema_version: number;
  name: string;
  source: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  start_time: string;
  end_time: string;
  created_at: string;
  candle_count: number;
  checksum: string;
}

export type DatasetProvenanceKind = 'legacy' | 'generated' | 'manual_upload' | 'market_data_import';

export interface DatasetProvenance {
  kind: DatasetProvenanceKind;
  connection_id: string | null;
  provider_id: string | null;
  import_id: string | null;
  requested_start_time: string | null;
  requested_end_time: string | null;
  normalization_version?: string | null;
  original_filename: string | null;
  original_file_format: DatasetFileFormat | null;
  original_file_checksum: string | null;
  column_mapping: Record<string, string> | null;
}

export interface DatasetDetailSummary extends DatasetSummary {
  provenance: DatasetProvenance;
  quality_report: MarketDataQualityReport | null;
}

export interface DatasetImportCandle {
  open_time: string;
  close_time: string;
  open_price: string;

  high_price: string;
  low_price: string;
  close_price: string;
  volume: string;
  is_closed?: boolean;
}

export interface DatasetImportRequest {
  name: string;
  source: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  candles: DatasetImportCandle[];
}

export type DatasetFileFormat = 'csv' | 'json' | 'parquet';

export type DatasetFileField =
  | 'open_time'
  | 'close_time'
  | 'open_price'
  | 'high_price'
  | 'low_price'
  | 'close_price'
  | 'volume'
  | 'is_closed';

export interface DatasetColumnMapping {
  open_time: string;
  open_price: string;
  high_price: string;
  low_price: string;
  close_price: string;
  volume: string;
  close_time: string | null;
  is_closed: string | null;
}

export interface DatasetFileInspection {
  file_name: string;
  file_format: DatasetFileFormat;
  file_size_bytes: number;
  file_checksum: string;
  row_count: number;
  columns: string[];
  suggested_mapping: Partial<Record<DatasetFileField, string>>;
  missing_required_fields: DatasetFileField[];
  can_preview: boolean;
}

export interface DatasetFilePreviewRequest {
  name: string;
  source: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  column_mapping: DatasetColumnMapping;
}

export interface DatasetFileCommitRequest extends DatasetFilePreviewRequest {
  preview_checksum: string;
}

export interface DatasetFileImportPreview {
  inspection: DatasetFileInspection;
  column_mapping: DatasetColumnMapping;
  candle_count: number;
  first_open_time: string;
  last_close_time: string;
  preview_checksum: string;
  quality_report: MarketDataQualityReport;
  ready_to_import: boolean;
}

export type ResearchStrategyName = 'ema-crossover' | 'rsi-threshold' | 'sma-crossover';

export type StrategyParameterKind = 'integer' | 'decimal';

export interface StrategyParameterMetadata {
  name: string;
  kind: StrategyParameterKind;
  default_value: string;
  minimum: string | null;
  maximum: string | null;
  minimum_exclusive: boolean;
  maximum_exclusive: boolean;
}

export interface ResearchStrategyMetadata {
  name: string;
  version: string;
  display_name: string;
  description: string;
  parameters: StrategyParameterMetadata[];
  lifecycle_status?: 'active' | 'deprecated';
  supersedes_version?: string | null;
  behavior_fingerprint?: string;
}

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

export type WalkForwardExecutionStatus = ExperimentExecutionStatus;

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

export interface CreatedResearchExperiment {
  experiment_id: string;
}

export interface OHLCVCandle {
  source: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  open_time: string;
  close_time: string;
  received_at: string;
  open_price: string;
  high_price: string;
  low_price: string;
  close_price: string;
  volume: string;
  is_closed: boolean;
}

export interface DatasetSnapshot extends DatasetSummary {
  candles: OHLCVCandle[];
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

export interface WalkForwardConfig {
  train_candles: number;
  test_candles: number;
  step_candles: number;
  gap_candles: number;
  mode: WalkForwardMode;
}

export interface BacktestConfig {
  starting_balance: string;
  allocation_fraction: string;
  fee_rate: string;
  slippage_rate: string;
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

export interface ResearchOverview {
  dataset_count: number;
  experiment_count: number;
  walk_forward_run_count: number;
  acceptance_policy_preset_count: number;
  research_stage: ResearchStage;
  acceptance_policy_presets: AcceptancePolicyPreset[];
  latest_dataset: DatasetSummary | null;
  latest_experiment: ExperimentSummary | null;
  latest_walk_forward_run: WalkForwardRunSummary | null;
}

export interface ResearchActivityItem {
  activity_type: ResearchActivityType;
  resource_id: string;
  created_at: string;
  label: string;
  dataset_id: string;
  strategy_name: string | null;
  strategy_version: string | null;
  horizon_candles: number | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  count: number;
  has_next: boolean;
  has_previous: boolean;
}

export type MonitoringOverallStatus = 'healthy' | 'warning' | 'critical';

export type SystemMetricName =
  | 'api_request_latency_p95'
  | 'api_error_rate'
  | 'api_repeated_read_ratio'
  | 'database_query_latency_p95'
  | 'database_pool_utilization'
  | 'database_cpu_utilization'
  | 'database_disk_utilization'
  | 'job_queue_wait_p95'
  | 'backtest_failure_rate'
  | 'market_data_lag'
  | 'invalid_candle_ratio'
  | 'candle_storage_share'
  | 'time_series_query_latency_p95'
  | 'analytical_query_latency_p95'
  | 'analytical_database_resource_share';

export type ArchitectureCandidate = 'postgresql_tuning' | 'redis' | 'timescaledb' | 'clickhouse';

export type RecommendationSeverity = 'info' | 'warning' | 'critical';

export type RecommendationStatus = 'active' | 'resolved' | 'dismissed';

export interface SystemMetricSample {
  sample_id: string;
  metric_name: SystemMetricName;
  source: string;
  value: string;
  unit: string;
  recorded_at: string;
}

export interface ArchitectureRecommendation {
  recommendation_id: string;
  candidate: ArchitectureCandidate;
  severity: RecommendationSeverity;
  status: RecommendationStatus;
  title: string;
}

export interface OperationalFailureReason {
  error_code: string;
  count: number;
}

export interface ConnectionHealthSummary {
  total_count: number;
  enabled_count: number;
  healthy_count: number;
  unhealthy_count: number;
  untested_count: number;
  latest_tested_at: string | null;
  latest_error_at: string | null;
  latest_error_code: string | null;
}

export interface ImportOperationsSummary {
  sample_size: number;
  succeeded_count: number;
  failed_count: number;
  failure_rate: string | null;
  latest_success_at: string | null;
  latest_failure_at: string | null;
  latest_failure_code: string | null;
}

export interface JobQueueSummary {
  total_count: number;
  queued_count: number;
  running_count: number;
  stuck_count: number;
  succeeded_count: number;
  failed_count: number;
  cancelled_count: number;
  recent_terminal_sample_size: number;
  average_duration_seconds: string | null;
  latest_success_at: string | null;
  latest_failure_at: string | null;
  failure_reasons: OperationalFailureReason[];
  recent_jobs: OperationalJobSummary[];
}

export type OperationalJobSummary = Omit<BackgroundJobSummary, 'error_message'>;

export interface OperationalMonitoringSummary {
  summary_version: 'operational-monitoring-v1';
  generated_at: string;
  connections: ConnectionHealthSummary;
  imports: ImportOperationsSummary;
  jobs: JobQueueSummary;
}

export interface MonitoringSummary {
  overall_status: MonitoringOverallStatus;
  latest_metrics: SystemMetricSample[];
  active_recommendations: ArchitectureRecommendation[];
  operations: OperationalMonitoringSummary | null;
  interpretation: 'capacity_planning_only';
}

export type SignalDirection = 'long' | 'short' | 'neutral';

export type ExperimentSignalSortDirection = 'asc' | 'desc';

export interface StrategyFeature {
  name: string;
  value: string;
}

export interface StrategySignal {
  signal_id: string;
  strategy_name: string;
  strategy_version: string;
  dataset_id: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  candle_open_time: string;
  candle_close_time: string;
  generated_at: string;
  direction: SignalDirection;
  score: string;
  reason: string;
  features: StrategyFeature[];
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

export type SimulatedPortfolioMode = 'paper' | 'shadow';

export type SimulatedPortfolioStatus = 'active' | 'completed';

export type SimulatedPositionSide = 'long' | 'short';

export type SimulatedPositionStatus = 'open' | 'closed';

export type PortfolioTimelineEventType =
  | 'portfolio_created'
  | 'position_opened'
  | 'position_marked'
  | 'position_closed'
  | 'portfolio_completed';

export interface SimulatedPosition {
  position_id: string;
  portfolio_id: string;
  pair: TradingPair;
  side: SimulatedPositionSide;
  status: SimulatedPositionStatus;
  quantity: string;
  entry_price: string;
  opened_at: string;
  current_price: string;
  current_at: string;
  reserved_notional: string;
  entry_fee: string;
  unrealized_pnl: string;
  exit_price: string | null;
  closed_at: string | null;
  exit_fee: string;
  gross_realized_pnl: string;
  realized_pnl: string;
}

export type PositionLineageStatus = 'complete' | 'unavailable' | 'conflict';

export interface PositionDetailReport {
  position_detail_version: 'position-detail-v1';
  as_of: string;
  dataset_id: string;
  position: SimulatedPosition;
  lineage_status: PositionLineageStatus;
  journal_id: string | null;
  candidate: ResearchCandidateSnapshot | null;
  decision_evidence: CandidateDecisionEvidence | null;
  nodes: CandidateDecisionLineageNode[];
  events: PortfolioTimelineEvent[];
  interpretation: 'historical_research_only';
}

export interface PortfolioTimelineEvent {
  event_id: string;
  portfolio_id: string;
  sequence_number: number;
  event_type: PortfolioTimelineEventType;
  occurred_at: string;
  equity: string;
  position_id: string | null;
  price: string | null;
  quantity: string | null;
  realized_pnl: string | null;
}

export interface SimulatedPortfolioSummary {
  portfolio_id: string;
  mode: SimulatedPortfolioMode;
  status: SimulatedPortfolioStatus;
  dataset_id: string;
  created_at: string;
  updated_at: string;
  starting_cash: string;
  cash: string;
  equity: string;
  fees_paid: string;
  realized_pnl: string;
  unrealized_pnl: string;
  position_count: number;
  event_count: number;
}

export interface SimulatedPortfolio {
  portfolio_id: string;
  mode: SimulatedPortfolioMode;
  status: SimulatedPortfolioStatus;
  dataset_id: string;
  created_at: string;
  updated_at: string;
  starting_cash: string;
  cash: string;
  equity: string;
  fee_rate: string;
  fees_paid: string;
  realized_pnl: string;
  unrealized_pnl: string;
  positions: SimulatedPosition[];
  timeline: PortfolioTimelineEvent[];
}

export type CandidateStatus = 'candidate' | 'selected' | 'stale' | 'invalidated';

export type CandidateAction = 'long' | 'short' | 'neutral' | 'no_trade';

export type CandidateReplayStatus = 'opened' | 'risk_rejected' | 'no_fill';

export type CandidateRiskDecision = 'approved' | 'rejected';

export type CandidateOccurrenceType = 'attempted' | 'skipped';

export type CandidateReplaySkipReason = 'position_opened';

export type CandidateRiskCheckName =
  | 'candidate_selectable'
  | 'portfolio_active'
  | 'dataset_match'
  | 'portfolio_capacity'
  | 'rank_limit'
  | 'ranking_score'
  | 'reward_risk'
  | 'simulated_budget';

export interface RiskDecisionSummary {
  evaluated_count: number;
  approved_count: number;
  rejected_count: number;
  approval_rate: string | null;
}

export interface RiskRejectionReasonSummary {
  name: CandidateRiskCheckName;
  rejected_decisions: number;
}

export interface RiskDecisionEvent {
  event_id: string;
  journal_id: string;
  candidate_id: string;
  portfolio_id: string;
  evaluated_at: string;
  decision: CandidateRiskDecision;
  replay_status: CandidateReplayStatus;
  primary_rejection_reason: CandidateRiskCheckName | null;
  failed_check_names: CandidateRiskCheckName[];
  risk_budget: string;
  risk_consumed: string;
  selected: boolean;
  position_id: string | null;
}

export interface RiskBudgetUtilization {
  opened_decisions: number;
  allocated_risk_budget: string;
  consumed_risk: string;
  consumption_fraction: string | null;
}

export interface PortfolioRiskSnapshot {
  latest_event_at: string | null;
  portfolio_count: number;
  open_position_count: number;
  total_equity: string;
  simulated_exposure: string;
  exposure_fraction: string | null;
  exposure_limit_fraction: string;
  exposure_within_limit: boolean | null;
  largest_pair: TradingPair | null;
  concentration_exposure: string;
  concentration_fraction: string | null;
  concentration_limit_fraction: string;
  concentration_within_limit: boolean | null;
  max_drawdown_fraction: string | null;
  drawdown_limit_fraction: string;
  drawdown_within_limit: boolean | null;
}

export interface RiskDashboardReport {
  dashboard_version: 'risk-dashboard-v1';
  generated_at: string;
  from_time: string | null;
  to_time: string | null;
  portfolio_id: string | null;
  decision_window: 'inclusive_risk_assessment_evaluated_at';
  portfolio_snapshot_rule: 'latest_event_at_or_before_to_time';
  drawdown_window_rule: 'baseline_at_from_time_then_events_in_range';
  decisions: RiskDecisionSummary;
  rejection_reasons: RiskRejectionReasonSummary[];
  budget: RiskBudgetUtilization;
  portfolio_risk: PortfolioRiskSnapshot;
  decision_events: RiskDecisionEvent[];
  interpretation: 'historical_research_only';
}

export type CandidateRankingEvidenceComponentName = 'confidence' | 'signal_quality' | 'freshness';

export interface CandidateRankingEvidenceComponent {
  name: CandidateRankingEvidenceComponentName;
  source_component: 'confidence' | 'signal_strength' | 'freshness';
  raw_value: string;
  weight: string;
  weighted_value: string;
  formula: 'round_half_up(raw_value * weight, 0.000001)';
}

export interface CandidateRankingTieBreakEvidence {
  tie_break_version: 'candidate-ranking-tie-break-v1';
  rule: 'total_score_desc_then_candidate_id_asc';
  applied: boolean;
  tied_candidate_ids: string[];
  position_within_tie: number | null;
}

export interface CandidateRankingBreakdown {
  score_version: 'candidate-ranking-score-v1';
  candidate_id: string;
  rank: number;
  total_score: string;
  formula: 'sum(weighted_components)';
  components: CandidateRankingEvidenceComponent[];
  tie_break: CandidateRankingTieBreakEvidence;
}

export interface CandidateRiskCheck {
  name: CandidateRiskCheckName;
  passed: boolean;
  actual_value: string;
  limit_value: string | null;
  reason: string;
}

export interface CandidateRiskCompatibilityBreakdown {
  compatibility_version: 'candidate-risk-compatibility-v1';
  status: 'evaluated' | 'not_evaluated';
  affects_ranking_score: false;
  decision: CandidateRiskDecision | null;
  passed_checks: number;
  failed_checks: number;
  compatibility_fraction: string | null;
  failed_check_names: CandidateRiskCheckName[];
  checks: CandidateRiskCheck[];
  not_evaluated_reason: CandidateReplaySkipReason | null;
}

export interface CandidateDecisionEvidence {
  evidence_version: 'candidate-decision-evidence-v1';
  candidate_id: string;
  ranking: CandidateRankingBreakdown;
  risk_compatibility: CandidateRiskCompatibilityBreakdown;
}

export type CandidateExitReason =
  | 'invalidation'
  | 'target'
  | 'trend_reversal'
  | 'portfolio_risk'
  | 'data_unreliable'
  | 'time_expiry'
  | 'end_of_data';

export interface CandidateProjectionSummary {
  candidate_id: string;
  status: CandidateStatus;
  action: CandidateAction;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  strategy_name: string;
  strategy_version: string;
  confidence: string;
  signal_score: string;
  created_at: string;
  valid_until: string;
  occurrence_count: number;
  latest_journal_id: string;
  latest_recorded_at: string;
  latest_rank: number;
  latest_ranking_score: string;
  latest_decision_evidence: CandidateDecisionEvidence | null;
  latest_occurrence_type: CandidateOccurrenceType;
  latest_replay_status: CandidateReplayStatus | null;
  latest_risk_decision: CandidateRiskDecision | null;
  latest_skip_reason: CandidateReplaySkipReason | null;
  selected: boolean;
  position_id: string | null;
  exit_reason: CandidateExitReason | null;
}

export interface ResearchCandidateSnapshot {
  candidate_id: string;
  status: CandidateStatus;
  action: CandidateAction;
  dataset_id: string;
  experiment_id: string;
  signal_id: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  strategy_name: string;
  strategy_version: string;
  confidence: string;
  signal_score: string;
  created_at: string;
  valid_until: string;
}

export interface CandidateJournalOccurrence {
  journal_id: string;
  recorded_at: string;
  evaluated_at: string;
  portfolio_id: string;
  candidate: ResearchCandidateSnapshot;
  rank: number;
  ranking_score: string;
  occurrence_type: CandidateOccurrenceType;
  replay_status: CandidateReplayStatus | null;
  risk_decision: CandidateRiskDecision | null;
  skip_reason: CandidateReplaySkipReason | null;
  selected: boolean;
  position_id: string | null;
  exit_reason: CandidateExitReason | null;
  decision_evidence: CandidateDecisionEvidence | null;
}

export type CandidateDecisionLineageKind =
  'dataset' | 'experiment' | 'signal' | 'candidate' | 'risk' | 'position' | 'exit';

export type CandidateDecisionLineageStatus =
  'available' | 'not_created' | 'not_evaluated' | 'unavailable';

export interface CandidateDecisionLineageNode {
  kind: CandidateDecisionLineageKind;
  status: CandidateDecisionLineageStatus;
  resource_id: string | null;
  portfolio_id: string | null;
  outcome: string | null;
  reason: string | null;
}

export interface CandidateDecisionLineage {
  lineage_version: 'candidate-decision-lineage-v1';
  journal_id: string;
  nodes: CandidateDecisionLineageNode[];
}

export interface CandidateRankHistoryEntry {
  journal_id: string;
  recorded_at: string;
  rank: number;
  ranking_score: string;
  selected: boolean;
  evidence_available: boolean;
}

export interface CandidateProjectionDetail {
  candidate: ResearchCandidateSnapshot;
  occurrence_count: number;
  journal_ids: string[];
  rank_history: CandidateRankHistoryEntry[];
  decision_lineage: CandidateDecisionLineage;
  latest: CandidateJournalOccurrence;
}

export interface CandidateComparisonEntry {
  comparison_position: number;
  occurrence: CandidateJournalOccurrence;
}

export interface CandidateComparisonResult {
  journal_id: string;
  compared_candidates: number;
  entries: CandidateComparisonEntry[];
  interpretation: 'historical_research_only';
}
