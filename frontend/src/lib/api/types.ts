export type ResearchStage =
  'empty' | 'data_available' | 'experiments_available' | 'walk_forward_available';

export type ResearchActivityType = 'dataset' | 'experiment' | 'walk_forward_run';

export type DatasetTimeframe = '15m' | '1h' | '4h' | '1d';

export type MarketType = 'spot';

export type MarketDataConnectionState = 'disabled' | 'enabled';

export type MarketDataConnectionHealth = 'untested' | 'healthy' | 'unhealthy';

export interface MarketDataProviderSummary {
  provider_id: string;
  display_name: string;
  requires_credentials: boolean;
  supported_market_types: MarketType[];
  supported_timeframes: DatasetTimeframe[];
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
  last_error: string | null;
}

export interface MarketDataConnectionCreateRequest {
  provider_id: string;
  display_name: string;
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
  strategy_return: string;
  benchmark_return: string;
  excess_return: string;
  max_drawdown_fraction: string;
  benchmark_max_drawdown_fraction: string;
  return_direction: HistoricalFoldReturnDirection;
}

export interface WalkForwardStabilityReport {
  execution_id: string;
  total_folds: number;
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
  average_excess_return: string;
  median_excess_return: string;
  worst_max_drawdown_fraction: string;
  folds: WalkForwardFoldStatistics[];
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

export interface MonitoringSummary {
  overall_status: MonitoringOverallStatus;
  latest_metrics: SystemMetricSample[];
  active_recommendations: ArchitectureRecommendation[];
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

export interface HistoricalPerformanceSeries {
  run_id: string;
  starting_balance: string;
  ending_balance: string;
  total_return: string;
  max_drawdown_fraction: string;
  points: HistoricalEquityPoint[];
}

export interface ExperimentPerformanceSeries {
  experiment_id: string;
  dataset_id: string;
  benchmark_type: 'buy_and_hold';
  strategy: HistoricalPerformanceSeries;
  benchmark: HistoricalPerformanceSeries;
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
}

export interface CandidateProjectionDetail {
  candidate: ResearchCandidateSnapshot;
  occurrence_count: number;
  journal_ids: string[];
  latest: CandidateJournalOccurrence;
}
