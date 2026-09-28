import type { TradingPair } from '@/lib/api/types';

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
