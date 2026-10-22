import type {
  DatasetTimeframe,
  MarketDataQualityReport,
  MarketType,
  TradingPair,
} from '@/features/datasets/api/types';

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
