import type { DatasetTimeframe, TradingPair } from '@/features/datasets/api/types';

export type MarketContextAssessmentStatus = 'ready' | 'insufficient_data' | 'stale';
export type MarketTrendRegime = 'trending_up' | 'trending_down' | 'ranging' | 'undetermined';
export type MarketVolatilityRegime = 'low' | 'normal' | 'high' | 'undetermined';
export type MarketContextUnavailableReason =
  'assessment_expired' | 'assessment_not_ready' | 'boundary_mismatch';

export interface MarketContextEvidence {
  feature_key: string;
  timeframe: DatasetTimeframe;
  value: string;
  calculation_version: string;
  window_reference_checksums: string[];
}

export interface MarketRegimeAssessment {
  schema_version: 'market-regime-assessment-v1';
  assessment_id: string;
  source: string;
  pair: TradingPair;
  as_of: string;
  input_manifest_id: string;
  input_checksum: string;
  feature_set_version: string;
  feature_set_checksum: string;
  feature_snapshot_id: string | null;
  feature_snapshot_checksum: string | null;
  algorithm_version: string;
  status: MarketContextAssessmentStatus;
  trend: MarketTrendRegime;
  volatility: MarketVolatilityRegime;
  confidence: string;
  evidence: MarketContextEvidence[];
  issue_codes: string[];
  assessed_at: string;
  expires_at: string;
}

export interface MarketContextProductView {
  schema_version: 'market-context-product-view-v1';
  evaluated_at: string;
  expected_as_of: string;
  consumable: boolean;
  unavailable_reasons: MarketContextUnavailableReason[];
  boundary_lag_seconds: number;
  seconds_until_expiry: number;
  assessment: MarketRegimeAssessment;
}
