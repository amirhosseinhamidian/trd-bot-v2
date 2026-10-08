import type { DatasetSummary } from '@/features/datasets/api/types';
import type { AcceptancePolicyPreset, ExperimentSummary } from '@/features/experiments/api/types';
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
export type {
  PortfolioRiskSnapshot,
  RiskBudgetUtilization,
  RiskDashboardReport,
  RiskDecisionEvent,
  RiskDecisionSummary,
  RiskRejectionReasonSummary,
} from '@/features/risk/api/types';
export type {
  PortfolioAnalyticsReport,
  PortfolioTimelineEvent,
  PortfolioTimelineEventType,
  PositionDetailReport,
  PositionLineageStatus,
  SimulatedPortfolio,
  SimulatedPortfolioMode,
  SimulatedPortfolioStatus,
  SimulatedPortfolioSummary,
  SimulatedPosition,
  SimulatedPositionSide,
  SimulatedPositionStatus,
} from '@/features/portfolios/api/types';

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
