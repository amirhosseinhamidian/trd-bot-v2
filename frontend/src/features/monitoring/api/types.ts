import type { BackgroundJobStatus, BackgroundJobSummary } from '@/features/jobs/api/types';

export type MonitoringOverallStatus = 'healthy' | 'warning' | 'critical';

export type MarketDataMonitoringOverallStatus = MonitoringOverallStatus | 'no_data';
export type MarketDataFreshnessStatus = 'fresh' | 'stale' | 'no_data';
export type MarketDataStreamHealthStatus = 'healthy' | 'degraded' | 'paused' | 'no_data';
export type MarketDataWatchlistState = 'active' | 'paused';
export type MarketDataConnectionState = 'enabled' | 'disabled';
export type MarketDataConnectionHealth = 'healthy' | 'unhealthy' | 'untested';
export type MarketDataPollRunStatus = 'succeeded' | 'no_data' | 'failed';

export interface MarketDataProviderRouteHealth {
  ordinal: number;
  provider_id: string;
  connection_id: string;
  connection_state: MarketDataConnectionState | null;
  health_status: MarketDataConnectionHealth | null;
  last_tested_at: string | null;
  last_error_code: string | null;
}

export interface MarketDataStreamHealth {
  watchlist_id: string;
  pair: {
    base_asset: string;
    quote_asset: string;
    market_type: 'spot';
  };
  timeframe: '15m' | '1h' | '4h' | '1d';
  watchlist_state: MarketDataWatchlistState;
  health_status: MarketDataStreamHealthStatus;
  freshness_status: MarketDataFreshnessStatus;
  provider_routes: MarketDataProviderRouteHealth[];
  selected_provider_id: string | null;
  latest_poll_status: MarketDataPollRunStatus | null;
  latest_poll_completed_at: string | null;
  latest_poll_error_code: string | null;
  latest_finalized_window_end: string | null;
  latest_watermark_time: string | null;
  data_age_seconds: number | null;
  lag_seconds: number | null;
  freshness_target_seconds: number;
  poll_overdue_seconds: number;
  finalization_backlog_count: number;
}

export interface MarketDataReplayHealth {
  replay_id: string;
  decision_id: string;
  window_id: string;
  reason:
    | 'new_window'
    | 'provisional_update'
    | 'duplicate_payload'
    | 'late_arrival'
    | 'finalized_window_conflict';
  requested_by: string;
  requested_at: string;
  job_id: string;
  job_status: BackgroundJobStatus;
  error_code: string | null;
  revision_id: string | null;
  revision_kind: 'late_insert' | 'correction' | null;
  revised_version: number | null;
  completed_at: string | null;
}

export interface MarketDataBacklogSummary {
  poll_jobs: number;
  replay_jobs: number;
  overdue_watchlists: number;
  finalization_windows: number;
  unrequested_revisions: number;
  pending_replays: number;
  failed_replays: number;
  completed_revisions: number;
}

export interface MarketDataMonitoringSummary {
  schema_version: 'market-data-monitoring-v1';
  generated_at: string;
  overall_status: MarketDataMonitoringOverallStatus;
  stream_count: number;
  healthy_count: number;
  degraded_count: number;
  stale_count: number;
  no_data_count: number;
  paused_count: number;
  backlog: MarketDataBacklogSummary;
  streams: MarketDataStreamHealth[];
  recent_replays: MarketDataReplayHealth[];
}

export type MarketContextMonitoringOverallStatus = MonitoringOverallStatus | 'no_data';
export type MarketContextFreshnessStatus = 'fresh' | 'stale' | 'no_data';
export type MarketContextStreamHealthStatus = 'healthy' | 'degraded' | 'no_data';
export type MarketContextAssessmentStatus = 'ready' | 'insufficient_data' | 'stale';
export type MarketContextHealthIssueCode =
  | 'assessment_expired'
  | 'assessment_missing'
  | 'assessment_not_ready'
  | 'boundary_lagging'
  | 'evaluation_failed'
  | 'evaluation_pending'
  | 'evaluation_retrying';

export interface MarketContextStreamHealth {
  source: string;
  pair: {
    base_asset: string;
    quote_asset: string;
    market_type: 'spot';
  };
  health_status: MarketContextStreamHealthStatus;
  freshness_status: MarketContextFreshnessStatus;
  issue_codes: MarketContextHealthIssueCode[];
  expected_as_of: string;
  latest_assessment_id: string | null;
  latest_assessment_status: MarketContextAssessmentStatus | null;
  latest_assessment_as_of: string | null;
  assessed_at: string | null;
  expires_at: string | null;
  assessment_age_seconds: number | null;
  boundary_lag_seconds: number | null;
  feature_set_version: string | null;
  algorithm_version: string | null;
  latest_job_id: string | null;
  latest_job_status: BackgroundJobStatus | null;
  latest_job_as_of: string | null;
  latest_job_updated_at: string | null;
  latest_job_progress_percent: number | null;
  latest_job_attempt_count: number | null;
  latest_job_max_attempts: number | null;
  latest_job_error_code: string | null;
}

export interface MarketContextBacklogSummary {
  queued_jobs: number;
  running_jobs: number;
  retrying_jobs: number;
  failed_streams: number;
  expired_assessments: number;
  lagging_streams: number;
  missing_assessments: number;
}

export interface MarketContextMonitoringSummary {
  schema_version: 'market-context-monitoring-v1';
  generated_at: string;
  overall_status: MarketContextMonitoringOverallStatus;
  stream_count: number;
  healthy_count: number;
  degraded_count: number;
  stale_count: number;
  no_data_count: number;
  backlog: MarketContextBacklogSummary;
  streams: MarketContextStreamHealth[];
}

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
