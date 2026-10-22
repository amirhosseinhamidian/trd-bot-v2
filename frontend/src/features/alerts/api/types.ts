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

export interface AlertPublicationPolicy {
  schema_version: 'alert-publication-policy-v1';
  policy_id: 'alert-publication-policy-default';
  policy_version: number;
  quiet_hours_enabled: boolean;
  quiet_hours_start_minute: number;
  quiet_hours_end_minute: number;
  timezone_name: string;
  critical_bypass_quiet_hours: boolean;
  updated_by: string;
  updated_at: string;
  policy_checksum: string;
}

export interface AlertPublicationPolicyInput {
  quiet_hours_enabled: boolean;
  quiet_hours_start_minute: number;
  quiet_hours_end_minute: number;
  timezone_name: string;
  critical_bypass_quiet_hours: boolean;
}

export interface AlertExpirySummary {
  schema_version: 'alert-expiry-summary-v1';
  evaluated_at: string;
  expired_total: number;
  materialized_total: number;
  pending_total: number;
}

export interface AlertExpirySweepResult {
  schema_version: 'alert-expiry-sweep-v1';
  evaluated_at: string;
  recorded_by: string;
  recorded_count: number;
  expiry_ids: string[];
  remaining_pending: number;
}

export type AlertSimulationMode = 'paper' | 'shadow';
export type AlertSimulationStatus = 'observing' | 'awaiting_outcome';

export interface AlertSimulationRecord {
  schema_version: 'alert-simulation-v1';
  simulation_id: string;
  alert_id: string;
  alert_checksum: string;
  source_reference_id: string;
  source_reference_checksum: string;
  rule_id: string;
  rule_version: number;
  rule_definition_checksum: string;
  mode: AlertSimulationMode;
  expected_trend: MarketTrendRegime;
  horizon_seconds: number;
  started_at: string;
  ends_at: string;
  started_by: string;
  offline_only: true;
  external_order_submission_allowed: false;
  record_checksum: string;
}

export interface AlertSimulationView {
  schema_version: 'alert-simulation-view-v1';
  simulation: AlertSimulationRecord;
  status: AlertSimulationStatus;
  evaluated_at: string;
  seconds_remaining: number;
}

export interface AlertSimulationSummary {
  schema_version: 'alert-simulation-summary-v1';
  evaluated_at: string;
  total: number;
  paper: number;
  shadow: number;
  observing: number;
  awaiting_outcome: number;
}

export interface AlertSimulationStartResult {
  schema_version: 'alert-simulation-start-result-v1';
  created: boolean;
  view: AlertSimulationView;
}

export type AlertOutcomeClassification = 'confirmed' | 'neutral' | 'false_positive';

export interface AlertOutcomeRecord {
  schema_version: 'alert-outcome-v1';
  outcome_id: string;
  simulation_id: string;
  simulation_checksum: string;
  alert_id: string;
  alert_checksum: string;
  mode: AlertSimulationMode;
  expected_trend: MarketTrendRegime;
  observed_trend: MarketTrendRegime;
  reference_price: string;
  end_price: string;
  high_price: string;
  low_price: string;
  raw_return: string;
  directional_return: string;
  max_favorable_excursion: string;
  max_adverse_excursion: string;
  classification: AlertOutcomeClassification;
  false_positive: boolean;
  drifted: boolean;
  policy_version: 'alert-outcome-policy-v1';
  policy_checksum: string;
  classification_threshold: string;
  observed_at: string;
  recorded_at: string;
  recorded_by: string;
  offline_only: true;
  external_order_submission_allowed: false;
  record_checksum: string;
}

export interface AlertOutcomeInput {
  reference_price: string;
  end_price: string;
  high_price: string;
  low_price: string;
  observed_trend: MarketTrendRegime;
}

export interface AlertOutcomeRecordResult {
  schema_version: 'alert-outcome-record-result-v1';
  created: boolean;
  outcome: AlertOutcomeRecord;
}

export interface AlertOutcomeSummary {
  schema_version: 'alert-outcome-summary-v1';
  evaluated_at: string;
  completed: number;
  awaiting_outcome: number;
  confirmed: number;
  neutral: number;
  false_positive: number;
  drifted: number;
  paper: number;
  shadow: number;
  false_positive_rate: string;
  drift_rate: string;
  average_directional_return: string;
}
