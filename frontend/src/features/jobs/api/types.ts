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
