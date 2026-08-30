import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import OverviewDashboard from '@/components/dashboard/overview-dashboard';
import type { Page, ResearchActivityItem, ResearchOverview } from '@/lib/api/types';

vi.mock('@/components/dashboard/activity-feed', () => ({
  default: function MockActivityFeed() {
    return <div data-testid="activity-feed" />;
  },
}));

const activityPage: Page<ResearchActivityItem> = {
  items: [],
  total: 0,
  limit: 10,
  offset: 0,
  count: 0,
  has_next: false,
  has_previous: false,
};

const overview: ResearchOverview = {
  dataset_count: 1,
  experiment_count: 2,
  walk_forward_run_count: 1,
  acceptance_policy_preset_count: 0,
  research_stage: 'walk_forward_available',
  acceptance_policy_presets: [],
  latest_dataset: {
    dataset_id: 'dataset-rsi',
    schema_version: 1,
    name: 'Historical RSI fixture',
    source: 'test-fixture',
    pair: {
      base_asset: 'BTC',
      quote_asset: 'USDT',
      market_type: 'spot',
    },
    timeframe: '1h',
    start_time: '2026-08-29T00:00:00Z',
    end_time: '2026-08-30T00:00:00Z',
    created_at: '2026-08-30T07:00:00Z',
    candle_count: 100,
    checksum: 'checksum-rsi',
  },
  latest_experiment: {
    experiment_id: 'experiment-rsi',
    created_at: '2026-08-30T08:00:00Z',
    dataset_id: 'dataset-rsi',
    strategy_name: 'rsi-threshold',
    strategy_version: '1.0.0',
    horizon_candles: 3,
    parameters: [
      { name: 'period', value: '14' },
      { name: 'oversold_threshold', value: '30' },
      { name: 'overbought_threshold', value: '70' },
    ],
    generated_signals: 2,
    total_trades: 1,
    net_pnl: '10',
    total_return: '0.01',
    win_rate: '1',
    max_drawdown_fraction: '0.01',
    profit_factor: '2',
    benchmark_type: 'buy_and_hold',
    benchmark_return: '0.005',
    excess_return: '0.005',
    benchmark_max_drawdown_fraction: '0.02',
    max_drawdown_fraction_delta: '-0.01',
    strategy_has_lower_drawdown: true,
    comparison_outcome: 'strategy',
  },
  latest_walk_forward_run: {
    execution_id: 'walk-forward-rsi',
    created_at: '2026-08-30T09:00:00Z',
    source_dataset_id: 'dataset-rsi',
    plan_id: 'plan-rsi',
    strategy_name: 'rsi-threshold',
    strategy_version: '1.0.0',
    horizon_candles: 3,
    strategy_parameters: [
      { name: 'period', value: '14' },
      { name: 'oversold_threshold', value: '30' },
      { name: 'overbought_threshold', value: '70' },
    ],
    walk_forward_config: {
      train_candles: 60,
      test_candles: 20,
      step_candles: 20,
      gap_candles: 0,
      mode: 'rolling',
    },
    backtest_config: {
      starting_balance: '10000',
      allocation_fraction: '0.1',
      fee_rate: '0.001',
      slippage_rate: '0.001',
    },
    total_folds: 2,
    total_signals: 3,
    folds_with_trades: 2,
    strategy_wins: 1,
    benchmark_wins: 1,
    ties: 0,
    average_strategy_return: '0.02',
    average_benchmark_return: '0.01',
    average_excess_return: '0.01',
    worst_max_drawdown_fraction: '0.03',
  },
};

describe('OverviewDashboard', () => {
  it('presents RSI identity for latest experiment and walk-forward results', () => {
    render(<OverviewDashboard activityPage={activityPage} locale="en" overview={overview} />);

    expect(screen.getAllByText('RSI Threshold')).toHaveLength(2);
    expect(screen.getAllByText('v1.0.0')).toHaveLength(2);
    expect(screen.getByText('Historical RSI fixture')).toBeInTheDocument();
  });
});
