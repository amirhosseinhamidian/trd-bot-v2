import type {
  CandidateDecisionEvidence,
  CandidateDecisionLineageNode,
  ResearchCandidateSnapshot,
} from '@/features/candidates/api/types';
import type { TradingPair } from '@/features/datasets/api/types';

export type SimulatedPortfolioMode = 'paper' | 'shadow';

export type SimulatedPortfolioStatus = 'active' | 'completed';

export type SimulatedPositionSide = 'long' | 'short';

export type SimulatedPositionStatus = 'open' | 'closed';

export type PortfolioTimelineEventType =
  | 'portfolio_created'
  | 'position_opened'
  | 'position_marked'
  | 'position_closed'
  | 'portfolio_completed';

export interface SimulatedPosition {
  position_id: string;
  portfolio_id: string;
  pair: TradingPair;
  side: SimulatedPositionSide;
  status: SimulatedPositionStatus;
  quantity: string;
  entry_price: string;
  opened_at: string;
  current_price: string;
  current_at: string;
  reserved_notional: string;
  entry_fee: string;
  unrealized_pnl: string;
  exit_price: string | null;
  closed_at: string | null;
  exit_fee: string;
  gross_realized_pnl: string;
  realized_pnl: string;
}

export type PositionLineageStatus = 'complete' | 'unavailable' | 'conflict';

export interface PositionDetailReport {
  position_detail_version: 'position-detail-v1';
  as_of: string;
  dataset_id: string;
  position: SimulatedPosition;
  lineage_status: PositionLineageStatus;
  journal_id: string | null;
  candidate: ResearchCandidateSnapshot | null;
  decision_evidence: CandidateDecisionEvidence | null;
  nodes: CandidateDecisionLineageNode[];
  events: PortfolioTimelineEvent[];
  interpretation: 'historical_research_only';
}

export interface PortfolioTimelineEvent {
  event_id: string;
  portfolio_id: string;
  sequence_number: number;
  event_type: PortfolioTimelineEventType;
  occurred_at: string;
  equity: string;
  position_id: string | null;
  price: string | null;
  quantity: string | null;
  realized_pnl: string | null;
}

export interface SimulatedPortfolioSummary {
  portfolio_id: string;
  mode: SimulatedPortfolioMode;
  status: SimulatedPortfolioStatus;
  dataset_id: string;
  created_at: string;
  updated_at: string;
  starting_cash: string;
  cash: string;
  equity: string;
  fees_paid: string;
  realized_pnl: string;
  unrealized_pnl: string;
  position_count: number;
  event_count: number;
}

export interface SimulatedPortfolio {
  portfolio_id: string;
  mode: SimulatedPortfolioMode;
  status: SimulatedPortfolioStatus;
  dataset_id: string;
  created_at: string;
  updated_at: string;
  starting_cash: string;
  cash: string;
  equity: string;
  fee_rate: string;
  fees_paid: string;
  realized_pnl: string;
  unrealized_pnl: string;
  positions: SimulatedPosition[];
  timeline: PortfolioTimelineEvent[];
}

export interface PortfolioAnalyticsReport {
  analytics_version: 'portfolio-analytics-v1';
  portfolio_id: string;
  as_of: string;
  starting_equity: string;
  ending_equity: string;
  net_pnl: string;
  return_fraction: string;
  fees_paid: string;
  closed_net_pnl: string;
  open_gross_unrealized_pnl: string;
  open_entry_fees: string;
  open_net_pnl: string;
  closed_count: number;
  open_count: number;
  winning_count: number;
  losing_count: number;
  breakeven_count: number;
  win_rate: string | null;
  profit_factor: string | null;
  profit_factor_status: 'available' | 'no_closed_trades' | 'no_losses';
  expectancy: string | null;
  average_hold_seconds: string | null;
  duration_seconds: string;
  max_drawdown_fraction: string;
  max_drawdown_duration_seconds: string;
  current_drawdown_duration_seconds: string;
  open_exposure: string;
  exposure_fraction: string | null;
  equity_points: {
    event_id: string;
    sequence_number: number;
    timestamp: string;
    equity: string;
    return_fraction: string;
    drawdown_fraction: string;
    drawdown_duration_seconds: string;
  }[];
  trades_by_pair: {
    pair: TradingPair;
    closed_count: number;
    open_count: number;
    net_realized_pnl: string;
    fees_paid: string;
  }[];
  exit_mix: { reason: string; count: number }[];
  interpretation: 'historical_research_only';
}
