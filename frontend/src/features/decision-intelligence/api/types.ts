import type { DatasetTimeframe, TradingPair } from '@/features/datasets/api/types';

export type DecisionMode = 'research' | 'shadow' | 'paper';
export type DecisionStage =
  'strategy_evaluation' | 'candidate_ranking' | 'risk_gate' | 'portfolio_simulation';
export type DecisionDisposition = 'accepted' | 'rejected' | 'deferred' | 'unavailable';
export type PortfolioRecommendation = 'accept' | 'reject' | 'unavailable';

export interface DecisionStageOutcome {
  outcome_id: string;
  evaluation_id: string;
  stage: DecisionStage;
  disposition: DecisionDisposition;
  reason_codes: string[];
  evaluated_at: string;
}

export interface DecisionEvaluationSummary {
  evaluation_id: string;
  mode: DecisionMode;
  requested_at: string;
  dataset_id: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  strategy_name: string;
  strategy_version: string;
  market_context_assessment_id: string;
  latest_stage: DecisionStage | null;
  disposition: DecisionDisposition | null;
  reason_codes: string[];
  completed_stage_count: number;
  signal_count: number;
  top_candidate_id: string | null;
  risk_decision: 'approved' | 'rejected' | null;
  portfolio_recommendation: PortfolioRecommendation | null;
  portfolio_id: string | null;
  offline_only: true;
  external_order_submission_allowed: false;
}

export interface DecisionStrategySignal {
  signal_id: string;
  direction: 'long' | 'short' | 'neutral';
  score: string;
  candle_close_time: string;
  reason: string;
}

export interface DecisionStrategyEvaluation {
  outcome: DecisionStageOutcome;
  signal_count: number;
  signals: DecisionStrategySignal[];
  compatibility_policy_version: string;
  compatibility_policy_checksum: string;
}

export interface DecisionCandidateRankingEntry {
  rank: number;
  total_score: string;
  candidate: {
    candidate_id: string;
    signal_id: string;
    action: 'long' | 'short';
    valid_until: string;
    trade_plan: {
      entry_price: string;
      invalidation_price: string;
      target_price: string;
      reward_risk_ratio: string;
    };
  };
  components: Array<{
    name: string;
    raw_value: string;
    weight: string;
    weighted_value: string;
  }>;
}

export interface DecisionCandidateRanking {
  outcome: DecisionStageOutcome;
  entries: DecisionCandidateRankingEntry[];
  candidate_count: number;
  excluded_signal_count: number;
  top_candidate_id: string | null;
}

export interface DecisionRiskGate {
  outcome: DecisionStageOutcome;
  assessment: {
    assessment_id: string;
    candidate_id: string;
    decision: 'approved' | 'rejected';
    checks: Array<{
      name: string;
      passed: boolean;
      actual_value: string;
      limit_value: string;
      explanation: string;
    }>;
    position_sizing: {
      quantity: string;
      notional: string;
      maximum_loss: string;
      risk_budget: string;
    } | null;
  };
}

export interface DecisionPortfolioIntelligence {
  outcome: DecisionStageOutcome;
  recommendation: PortfolioRecommendation;
  analysis: {
    snapshot: {
      portfolio_id: string | null;
      equity: string;
      open_positions: Array<{ position_id: string }>;
    };
    exposure: {
      current_exposure_fraction: string;
      projected_exposure_fraction: string;
      projected_asset_concentration_fraction: string;
    };
    correlation: {
      status: 'available' | 'unavailable' | 'not_applicable';
      maximum_absolute_correlation: string | null;
      evidence: string;
    };
    scenarios: Array<{
      shock_fraction: string;
      projected_equity: string;
      loss_fraction: string;
    }>;
    checks: Array<{
      name: string;
      passed: boolean;
      actual_value: string;
      limit_value: string;
      explanation: string;
    }>;
    exit_recommendations: Array<{
      position_id: string;
      action: 'hold' | 'exit_risk' | 'exit_regime';
      reason_codes: string[];
    }>;
  } | null;
}

export interface DecisionEvaluationDetail {
  summary: DecisionEvaluationSummary;
  intent: {
    evaluation_id: string;
    mode: DecisionMode;
    requested_at: string;
    dataset: {
      dataset_id: string;
      reference_checksum: string;
    };
    strategy: {
      strategy_name: string;
      strategy_version: string;
      reference_checksum: string;
    };
    market_context: {
      assessment_id: string;
      trend: string;
      volatility: string;
      confidence: string;
      reference_checksum: string;
    };
    policy: {
      policy_id: string;
      policy_version: number;
      definition_checksum: string;
    };
    intent_checksum: string;
    offline_only: true;
    external_order_submission_allowed: false;
  };
  outcomes: DecisionStageOutcome[];
  strategy_evaluation: DecisionStrategyEvaluation | null;
  candidate_ranking: DecisionCandidateRanking | null;
  risk_gate: DecisionRiskGate | null;
  portfolio_intelligence: DecisionPortfolioIntelligence | null;
}
