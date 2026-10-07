export type DatasetTimeframe = '15m' | '1h' | '4h' | '1d';

export type MarketType = 'spot';

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

export type DatasetSortField = 'created_at' | 'start_time' | 'candle_count';

export type DatasetSortDirection = 'asc' | 'desc';

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
