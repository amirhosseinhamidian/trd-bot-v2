import type { BackgroundJobSummary } from '@/features/jobs/api/types';

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
