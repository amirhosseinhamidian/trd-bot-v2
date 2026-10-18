import type { TradingPair } from '@/features/datasets/api/types';
import type {
  MarketContextAssessmentStatus,
  MarketContextUnavailableReason,
  MarketTrendRegime,
  MarketVolatilityRegime,
} from '@/features/market-context/api/types';

export type AlertSeverity = 'info' | 'warning' | 'critical';
export type AlertInboxStatus = 'active' | 'snoozed' | 'acknowledged' | 'expired';

export interface AlertRuleReference {
  schema_version: 'alert-rule-reference-v1';
  rule_id: string;
  rule_version: number;
  state: 'enabled' | 'disabled';
  severity: AlertSeverity;
  expires_after_seconds: number;
  definition_checksum: string;
}

export interface AlertSourceReference {
  schema_version: 'market-context-alert-source-v1';
  reference_id: string;
  source_kind: 'market_context';
  source_event_id: string;
  source_event_schema_version: 'market-regime-assessment-v1';
  source_event_checksum: string;
  source: string;
  pair: TradingPair;
  event_time: string;
  assessed_at: string;
  expires_at: string;
  evaluated_at: string;
  expected_as_of: string;
  assessment_status: MarketContextAssessmentStatus;
  trend: MarketTrendRegime;
  volatility: MarketVolatilityRegime;
  confidence: string;
  consumable: boolean;
  unavailable_reasons: MarketContextUnavailableReason[];
  reference_checksum: string;
}

export interface AlertDraft {
  schema_version: 'alert-draft-v1';
  alert_id: string;
  deduplication_key: string;
  rule: AlertRuleReference;
  source: AlertSourceReference;
  delivery_channel: 'in_app';
  severity: AlertSeverity;
  title: string;
  message: string;
  created_at: string;
  expires_at: string;
  draft_checksum: string;
}

export interface AlertInboxState {
  schema_version: 'alert-inbox-state-v1';
  alert_id: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  snoozed_until: string | null;
  snoozed_by: string | null;
  updated_at: string;
}

export interface AlertInboxItem {
  schema_version: 'alert-inbox-item-v1';
  alert: AlertDraft;
  state: AlertInboxState;
  status: AlertInboxStatus;
  evaluated_at: string;
  seconds_until_expiry: number;
  seconds_until_unsnooze: number;
  can_acknowledge: boolean;
  can_snooze: boolean;
}

export interface AlertInboxSummary {
  schema_version: 'alert-inbox-summary-v1';
  evaluated_at: string;
  total: number;
  active: number;
  snoozed: number;
  acknowledged: number;
  expired: number;
}
