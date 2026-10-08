import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ExperimentAnalytics } from '@/features/experiments/experiment-analytics';
import type { ExperimentAnalyticsReport } from '@/features/experiments/api/types';

const analytics: ExperimentAnalyticsReport = {
  experiment_id: 'experiment-1234567890abcdef',
  dataset_id: 'dataset-btc-usdt',
  analytics_version: 'research-analytics-v1',
  period_granularity: 'utc_calendar_month',
  period_start: '2026-01-01T00:00:00Z',
  period_end: '2026-02-28T23:00:00Z',
  starting_balance: '1000',
  ending_balance: '1030',
  strategy_total_return: '0.03',
  benchmark_total_return: '0.01',
  excess_return: '0.02',
  strategy_max_drawdown_fraction: '0.05',
  benchmark_max_drawdown_fraction: '0.08',
  trade_distribution: {
    total_trades: 3,
    winning_trades: 2,
    losing_trades: 1,
    flat_trades: 0,
    long_trades: 2,
    short_trades: 1,
    win_rate: '0.6666666667',
    gross_profit: '50',
    gross_loss: '20',
    total_fees: '2',
    net_pnl: '30',
    profit_factor: '2.5',
    average_net_pnl: '10',
    median_net_pnl: '8',
    best_net_pnl: '42',
    worst_net_pnl: '-20',
  },
  returns_by_period: [
    {
      period: '2026-01',
      started_at: '2026-01-01T00:00:00Z',
      ended_at: '2026-02-01T00:00:00Z',
      opening_balance: '1000',
      ending_balance: '1010',
      net_pnl: '10',
      return_contribution: '0.01',
      total_trades: 1,
      winning_trades: 1,
      losing_trades: 0,
      flat_trades: 0,
    },
    {
      period: '2026-02',
      started_at: '2026-02-01T00:00:00Z',
      ended_at: '2026-02-28T23:00:00Z',
      opening_balance: '1010',
      ending_balance: '1030',
      net_pnl: '20',
      return_contribution: '0.02',
      total_trades: 2,
      winning_trades: 1,
      losing_trades: 1,
      flat_trades: 0,
    },
  ],
  drawdown_episodes: [
    {
      episode_number: 1,
      started_at: '2026-02-10T00:00:00Z',
      trough_at: '2026-02-10T00:00:00Z',
      recovered_at: '2026-02-20T00:00:00Z',
      peak_balance: '1010',
      trough_balance: '959.5',
      max_drawdown: '50.5',
      max_drawdown_fraction: '0.05',
      trades_underwater: 1,
      status: 'recovered',
    },
  ],
  metric_definitions: [
    {
      key: 'total_return',
      unit: 'fraction',
      preference: 'higher_is_better',
      definition: 'Realized net profit relative to starting capital.',
      formula: 'strategy_net_pnl / starting_balance',
    },
  ],
  interpretation: 'historical_research_only',
};

describe('ExperimentAnalytics', () => {
  it('renders trade, monthly return, drawdown, and metric evidence', () => {
    render(<ExperimentAnalytics analytics={analytics} locale="en" />);

    expect(
      screen.getByRole('img', { name: 'Trade outcome distribution chart' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: 'Monthly return contribution chart' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Recovered')).toBeInTheDocument();
    expect(screen.getByText('strategy_net_pnl / starting_balance')).toBeInTheDocument();
    expect(screen.getByText('Worst trade')).toBeInTheDocument();
    expect(screen.getByText('-20')).toBeInTheDocument();
  });

  it('renders the explicit no-drawdown state', () => {
    render(
      <ExperimentAnalytics
        analytics={{
          ...analytics,
          trade_distribution: {
            ...analytics.trade_distribution,
            total_trades: 0,
            winning_trades: 0,
            losing_trades: 0,
            flat_trades: 0,
            long_trades: 0,
            short_trades: 0,
          },
          drawdown_episodes: [],
        }}
        locale="en"
      />,
    );

    expect(
      screen.getByText('No closed trades are available for distribution analysis.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('No realized drawdown episode was recorded for this experiment.'),
    ).toBeInTheDocument();
  });
});
