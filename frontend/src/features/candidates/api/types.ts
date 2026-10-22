import type { DatasetTimeframe, TradingPair } from '@/features/datasets/api/types';

export type CandidateStatus = 'candidate' | 'selected' | 'stale' | 'invalidated';

export type CandidateAction = 'long' | 'short' | 'neutral' | 'no_trade';

export type CandidateReplayStatus = 'opened' | 'risk_rejected' | 'no_fill';

export type CandidateRiskDecision = 'approved' | 'rejected';

export type CandidateOccurrenceType = 'attempted' | 'skipped';

export type CandidateReplaySkipReason = 'position_opened';

export type CandidateRiskCheckName =
  | 'candidate_selectable'
  | 'portfolio_active'
  | 'dataset_match'
  | 'portfolio_capacity'
  | 'rank_limit'
  | 'ranking_score'
  | 'reward_risk'
  | 'simulated_budget';

export type CandidateRankingEvidenceComponentName = 'confidence' | 'signal_quality' | 'freshness';

export interface CandidateRankingEvidenceComponent {
  name: CandidateRankingEvidenceComponentName;
  source_component: 'confidence' | 'signal_strength' | 'freshness';
  raw_value: string;
  weight: string;
  weighted_value: string;
  formula: 'round_half_up(raw_value * weight, 0.000001)';
}

export interface CandidateRankingTieBreakEvidence {
  tie_break_version: 'candidate-ranking-tie-break-v1';
  rule: 'total_score_desc_then_candidate_id_asc';
  applied: boolean;
  tied_candidate_ids: string[];
  position_within_tie: number | null;
}

export interface CandidateRankingBreakdown {
  score_version: 'candidate-ranking-score-v1';
  candidate_id: string;
  rank: number;
  total_score: string;
  formula: 'sum(weighted_components)';
  components: CandidateRankingEvidenceComponent[];
  tie_break: CandidateRankingTieBreakEvidence;
}

export interface CandidateRiskCheck {
  name: CandidateRiskCheckName;
  passed: boolean;
  actual_value: string;
  limit_value: string | null;
  reason: string;
}

export interface CandidateRiskCompatibilityBreakdown {
  compatibility_version: 'candidate-risk-compatibility-v1';
  status: 'evaluated' | 'not_evaluated';
  affects_ranking_score: false;
  decision: CandidateRiskDecision | null;
  passed_checks: number;
  failed_checks: number;
  compatibility_fraction: string | null;
  failed_check_names: CandidateRiskCheckName[];
  checks: CandidateRiskCheck[];
  not_evaluated_reason: CandidateReplaySkipReason | null;
}

export interface CandidateDecisionEvidence {
  evidence_version: 'candidate-decision-evidence-v1';
  candidate_id: string;
  ranking: CandidateRankingBreakdown;
  risk_compatibility: CandidateRiskCompatibilityBreakdown;
}

export type CandidateExitReason =
  | 'invalidation'
  | 'target'
  | 'trend_reversal'
  | 'portfolio_risk'
  | 'data_unreliable'
  | 'time_expiry'
  | 'end_of_data';

export interface CandidateProjectionSummary {
  candidate_id: string;
  status: CandidateStatus;
  action: CandidateAction;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  strategy_name: string;
  strategy_version: string;
  confidence: string;
  signal_score: string;
  created_at: string;
  valid_until: string;
  occurrence_count: number;
  latest_journal_id: string;
  latest_recorded_at: string;
  latest_rank: number;
  latest_ranking_score: string;
  latest_decision_evidence: CandidateDecisionEvidence | null;
  latest_occurrence_type: CandidateOccurrenceType;
  latest_replay_status: CandidateReplayStatus | null;
  latest_risk_decision: CandidateRiskDecision | null;
  latest_skip_reason: CandidateReplaySkipReason | null;
  selected: boolean;
  position_id: string | null;
  exit_reason: CandidateExitReason | null;
}

export interface ResearchCandidateSnapshot {
  candidate_id: string;
  status: CandidateStatus;
  action: CandidateAction;
  dataset_id: string;
  experiment_id: string;
  signal_id: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  strategy_name: string;
  strategy_version: string;
  confidence: string;
  signal_score: string;
  created_at: string;
  valid_until: string;
}

export interface CandidateJournalOccurrence {
  journal_id: string;
  recorded_at: string;
  evaluated_at: string;
  portfolio_id: string;
  candidate: ResearchCandidateSnapshot;
  rank: number;
  ranking_score: string;
  occurrence_type: CandidateOccurrenceType;
  replay_status: CandidateReplayStatus | null;
  risk_decision: CandidateRiskDecision | null;
  skip_reason: CandidateReplaySkipReason | null;
  selected: boolean;
  position_id: string | null;
  exit_reason: CandidateExitReason | null;
  decision_evidence: CandidateDecisionEvidence | null;
}

export type CandidateDecisionLineageKind =
  'dataset' | 'experiment' | 'signal' | 'candidate' | 'risk' | 'position' | 'exit';

export type CandidateDecisionLineageStatus =
  'available' | 'not_created' | 'not_evaluated' | 'unavailable';

export interface CandidateDecisionLineageNode {
  kind: CandidateDecisionLineageKind;
  status: CandidateDecisionLineageStatus;
  resource_id: string | null;
  portfolio_id: string | null;
  outcome: string | null;
  reason: string | null;
}

export interface CandidateDecisionLineage {
  lineage_version: 'candidate-decision-lineage-v1';
  journal_id: string;
  nodes: CandidateDecisionLineageNode[];
}

export interface CandidateRankHistoryEntry {
  journal_id: string;
  recorded_at: string;
  rank: number;
  ranking_score: string;
  selected: boolean;
  evidence_available: boolean;
}

export interface CandidateProjectionDetail {
  candidate: ResearchCandidateSnapshot;
  occurrence_count: number;
  journal_ids: string[];
  rank_history: CandidateRankHistoryEntry[];
  decision_lineage: CandidateDecisionLineage;
  latest: CandidateJournalOccurrence;
}

export interface CandidateComparisonEntry {
  comparison_position: number;
  occurrence: CandidateJournalOccurrence;
}

export interface CandidateComparisonResult {
  journal_id: string;
  compared_candidates: number;
  entries: CandidateComparisonEntry[];
  interpretation: 'historical_research_only';
}
