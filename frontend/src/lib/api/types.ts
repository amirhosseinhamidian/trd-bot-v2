import type { DatasetSummary, DatasetTimeframe, TradingPair } from '@/features/datasets/api/types';
import type {
  AcceptancePolicyPreset,
  BacktestConfig,
  ExperimentComparisonMetric,
  ExperimentExecutionParameters,
  ExperimentExecutionStatus,
  ExperimentParameter,
  ExperimentSummary,
  ResearchMetricDefinition,
  StoredDatasetEMACrossoverRequest,
  StoredDatasetRSIThresholdRequest,
  StoredDatasetSMACrossoverRequest,
} from '@/features/experiments/api/types';
import type { ResearchStrategyName } from '@/features/strategies/api/types';

export type {
  DatasetColumnMapping,
  DatasetDetailSummary,
  DatasetFileCommitRequest,
  DatasetFileField,
  DatasetFileFormat,
  DatasetFileImportPreview,
  DatasetFileInspection,
  DatasetFilePreviewRequest,
  DatasetImportCandle,
  DatasetImportRequest,
  DatasetProvenance,
  DatasetProvenanceKind,
  DatasetSnapshot,
  DatasetSortDirection,
  DatasetSortField,
  DatasetSummary,
  DatasetTimeframe,
  MarketDataCoverageReport,
  MarketDataQualityAcceptance,
  MarketDataQualityIssue,
  MarketDataQualityIssueCode,
  MarketDataQualityReport,
  MarketDataQualityScore,
  MarketType,
  OHLCVCandle,
  TradingPair,
} from '@/features/datasets/api/types';
export type {
  HistoricalDatasetCommitRequest,
  HistoricalDatasetImportPreview,
  HistoricalDatasetImportRequest,
  MarketDataConnection,
  MarketDataConnectionCreateRequest,
  MarketDataConnectionHealth,
  MarketDataConnectionState,
  MarketDataImportOperation,
  MarketDataImportRecord,
  MarketDataImportStatus,
  MarketDataProviderAccessMode,
  MarketDataProviderErrorCode,
  MarketDataProviderSummary,
} from '@/features/connections/api/types';
export type {
  AcceptancePolicy,
  AcceptancePolicyPreset,
  BacktestConfig,
  CreatedResearchExperiment,
  EMACrossoverExecutionParameters,
  ExperimentAcceptanceCheck,
  ExperimentAcceptanceCheckName,
  ExperimentAcceptanceComparison,
  ExperimentAcceptanceOutcome,
  ExperimentAcceptanceResult,
  ExperimentAnalyticsReport,
  ExperimentComparisonEntry,
  ExperimentComparisonMetric,
  ExperimentComparisonRankingDirection,
  ExperimentComparisonRequest,
  ExperimentComparisonResult,
  ExperimentExecution,
  ExperimentExecutionParameters,
  ExperimentExecutionStatus,
  ExperimentParameter,
  ExperimentPerformanceSeries,
  ExperimentPeriodReturn,
  ExperimentReplayCode,
  ExperimentReplayStatus,
  ExperimentReplayVerification,
  ExperimentResearchReport,
  ExperimentSortDirection,
  ExperimentSortField,
  ExperimentSummary,
  ExperimentTradeDistribution,
  HistoricalBenchmarkContext,
  HistoricalDrawdownEpisode,
  HistoricalDrawdownEpisodeStatus,
  HistoricalEquityPoint,
  HistoricalExecutionParameters,
  HistoricalPerformancePoint,
  HistoricalPerformancePointKind,
  HistoricalPerformanceSeries,
  PresetExperimentResearchReport,
  ResearchMetricDefinition,
  ResearchMetricKey,
  RSIThresholdExecutionParameters,
  SMACrossoverExecutionParameters,
  StoredDatasetEMACrossoverExecutionRequest,
  StoredDatasetEMACrossoverRequest,
  StoredDatasetHistoricalExecutionRequest,
  StoredDatasetRSIThresholdExecutionRequest,
  StoredDatasetRSIThresholdRequest,
  StoredDatasetSMACrossoverExecutionRequest,
  StoredDatasetSMACrossoverRequest,
  StoredDatasetStrategyExecutionRequest,
} from '@/features/experiments/api/types';
export type {
  ResearchStrategyMetadata,
  ResearchStrategyName,
  StrategyParameterKind,
  StrategyParameterMetadata,
} from '@/features/strategies/api/types';

export type ResearchStage =
  'empty' | 'data_available' | 'experiments_available' | 'walk_forward_available';

export type ResearchActivityType = 'dataset' | 'experiment' | 'walk_forward_run';

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

export interface WalkForwardConfig {
  train_candles: number;
  test_candles: number;
  step_candles: number;
  gap_candles: number;
  mode: WalkForwardMode;
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
