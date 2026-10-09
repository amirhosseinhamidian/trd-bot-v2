import { afterEach, describe, expect, it, vi } from 'vitest';

import { getExperimentAnalytics } from '@/features/experiments/api/client';
import type { ExperimentAnalyticsReport } from '@/features/experiments/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';

const analytics: ExperimentAnalyticsReport = {
  experiment_id: 'experiment-1234567890abcdef',
  dataset_id: 'dataset-btc-usdt',
  analytics_version: 'research-analytics-v1',
  period_granularity: 'utc_calendar_month',
  period_start: '2026-01-01T00:00:00Z',
  period_end: '2026-01-31T23:00:00Z',
  starting_balance: '10000',
  ending_balance: '10000',
  strategy_total_return: '0',
  benchmark_total_return: '0.01',
  excess_return: '-0.01',
  strategy_max_drawdown_fraction: '0',
  benchmark_max_drawdown_fraction: '0',
  trade_distribution: {
    total_trades: 0,
    winning_trades: 0,
    losing_trades: 0,
    flat_trades: 0,
    long_trades: 0,
    short_trades: 0,
    win_rate: null,
    gross_profit: '0',
    gross_loss: '0',
    total_fees: '0',
    net_pnl: '0',
    profit_factor: null,
    average_net_pnl: null,
    median_net_pnl: null,
    best_net_pnl: null,
    worst_net_pnl: null,
  },
  returns_by_period: [
    {
      period: '2026-01',
      started_at: '2026-01-01T00:00:00Z',
      ended_at: '2026-01-31T23:00:00Z',
      opening_balance: '10000',
      ending_balance: '10000',
      net_pnl: '0',
      return_contribution: '0',
      total_trades: 0,
      winning_trades: 0,
      losing_trades: 0,
      flat_trades: 0,
    },
  ],
  drawdown_episodes: [],
  metric_definitions: [],
  interpretation: 'historical_research_only',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('experiment analytics client', () => {
  it('loads analytics using an encoded experiment ID', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(analytics), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getExperimentAnalytics('experiment/id')).resolves.toEqual(analytics);
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/experiments/experiment%2Fid/analytics`,
      expect.objectContaining({ cache: 'no-store' }),
    );
  });
});
