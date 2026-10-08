import type { DatasetSummary, TradingPair } from '@/features/datasets/api/types';
import type { AcceptancePolicyPreset, ExperimentSummary } from '@/features/experiments/api/types';
import type {
  CandidateDecisionEvidence,
  CandidateDecisionLineageNode,
  CandidateReplayStatus,
  CandidateRiskCheckName,
  CandidateRiskDecision,
  ResearchCandidateSnapshot,
} from '@/features/candidates/api/types';
import type { WalkForwardRunSummary } from '@/features/walk-forward/api/types';

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
export type {
  HistoricalFoldReturnDirection,
  StoredDatasetEMACrossoverWalkForwardExecutionRequest,
  StoredDatasetEMACrossoverWalkForwardRequest,
  StoredDatasetRSIThresholdWalkForwardExecutionRequest,
  StoredDatasetRSIThresholdWalkForwardRequest,
  StoredDatasetSMACrossoverWalkForwardExecutionRequest,
  StoredDatasetSMACrossoverWalkForwardRequest,
  StoredDatasetStrategyWalkForwardExecutionRequest,
  WalkForwardConfig,
  WalkForwardExecution,
  WalkForwardExecutionRequest,
  WalkForwardExecutionStatus,
  WalkForwardFoldStatistics,
  WalkForwardMode,
  WalkForwardRunSortDirection,
  WalkForwardRunSortField,
  WalkForwardRunSummary,
  WalkForwardStabilityReport,
} from '@/features/walk-forward/api/types';
export type {
  CreateOptimizationExecutionRequest,
  OptimizationExecution,
  OptimizationExecutionStatus,
  OptimizationExecutionSubmission,
  OptimizationParameterGrid,
  OptimizationPlan,
  OptimizationRobustnessBreakdown,
  OptimizationRobustnessPlan,
  OptimizationRobustnessRankingEntry,
  OptimizationRobustnessRankingResult,
  OptimizationRobustnessWeights,
  OptimizationTrial,
  OptimizationTrialEvaluation,
  OptimizationTrialRejectionReason,
} from '@/features/optimizations/api/types';
export type {
  ExperimentSignalSortDirection,
  SignalDirection,
  StrategyFeature,
  StrategySignal,
} from '@/features/signals/api/types';
export type {
  CandidateAction,
  CandidateComparisonEntry,
  CandidateComparisonResult,
  CandidateDecisionEvidence,
  CandidateDecisionLineage,
  CandidateDecisionLineageKind,
  CandidateDecisionLineageNode,
  CandidateDecisionLineageStatus,
  CandidateExitReason,
  CandidateJournalOccurrence,
  CandidateOccurrenceType,
  CandidateProjectionDetail,
  CandidateProjectionSummary,
  CandidateRankHistoryEntry,
  CandidateRankingBreakdown,
  CandidateRankingEvidenceComponent,
  CandidateRankingEvidenceComponentName,
  CandidateRankingTieBreakEvidence,
  CandidateReplaySkipReason,
  CandidateReplayStatus,
  CandidateRiskCheck,
  CandidateRiskCheckName,
  CandidateRiskCompatibilityBreakdown,
  CandidateRiskDecision,
  CandidateStatus,
  ResearchCandidateSnapshot,
} from '@/features/candidates/api/types';

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
