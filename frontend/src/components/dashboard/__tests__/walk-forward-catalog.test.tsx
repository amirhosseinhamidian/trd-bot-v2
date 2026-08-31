import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import WalkForwardCatalog from '@/components/dashboard/walk-forward-catalog';
import type { Page, WalkForwardRunSummary } from '@/lib/api/types';

vi.mock('@/components/dashboard/walk-forward-run-form', () => ({
  default: function MockWalkForwardRunForm({
    initialValues,
  }: {
    initialValues?: { strategyName?: string };
  }) {
    return (
      <div data-testid="walk-forward-run-form">
        {initialValues?.strategyName ?? 'no-initial-strategy'}
      </div>
    );
  },
}));

vi.mock('@/components/dashboard/walk-forward-filter-panel', () => ({
  DEFAULT_WALK_FORWARD_FILTERS: {
    sourceDatasetId: '',
    planId: '',
    strategyName: '',
    strategyVersion: '',
    horizonCandles: '',
    createdAtFrom: '',
    createdAtTo: '',
    sortBy: 'created_at',
    sortDirection: 'desc',
  },
  default: function MockWalkForwardFilterPanel() {
    return <div data-testid="walk-forward-filter-panel" />;
  },
}));

const rsiRun: WalkForwardRunSummary = {
  execution_id: 'walk-forward-rsi-000001',
  created_at: '2026-08-30T08:00:00Z',
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
    train_candles: 100,
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
  total_folds: 3,
  total_signals: 4,
  folds_with_trades: 2,
  strategy_wins: 2,
  benchmark_wins: 1,
  ties: 0,
  average_strategy_return: '0.02',
  average_benchmark_return: '0.01',
  average_excess_return: '0.01',
  worst_max_drawdown_fraction: '0.03',
};

const page: Page<WalkForwardRunSummary> = {
  items: [rsiRun],
  total: 1,
  limit: 12,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

describe('WalkForwardCatalog', () => {
  it('passes strategy preselection into the run form', () => {
    render(
      <WalkForwardCatalog
        locale="en"
        initialPage={page}
        initialRunValues={{ strategyName: 'rsi-threshold' }}
      />,
    );

    expect(screen.getByTestId('walk-forward-run-form')).toHaveTextContent('rsi-threshold');
  });

  it('presents RSI strategy identity and localized parameter labels', () => {
    render(<WalkForwardCatalog locale="en" initialPage={page} />);

    expect(screen.getByText('RSI Threshold')).toBeInTheDocument();
    expect(screen.getByText('RSI period=14')).toBeInTheDocument();
    expect(screen.getByText('Oversold threshold=30')).toBeInTheDocument();
  });
});
