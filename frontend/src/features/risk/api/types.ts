import type {
  CandidateReplayStatus,
  CandidateRiskCheckName,
  CandidateRiskDecision,
} from '@/features/candidates/api/types';
import type { TradingPair } from '@/features/datasets/api/types';

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
