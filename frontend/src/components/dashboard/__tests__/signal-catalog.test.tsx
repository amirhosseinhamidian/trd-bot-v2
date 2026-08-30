import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SignalCatalog from '@/components/dashboard/signal-catalog';
import type { ExperimentSummary, Page, StrategySignal } from '@/lib/api/types';

vi.mock('@/components/dashboard/signal-filter-panel', () => ({
  default: function MockSignalFilterPanel() {
    return <div data-testid="signal-filter-panel" />;
  },
}));

const experiment: ExperimentSummary = {
  experiment_id: 'experiment-0123456789abcdef',
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
  generated_signals: 1,
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
};

const signal: StrategySignal = {
  signal_id: 'signal-0123456789abcdef',
  strategy_name: 'rsi-threshold',
  strategy_version: '1.0.0',
  dataset_id: 'dataset-rsi',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  candle_open_time: '2026-08-30T08:00:00Z',
  candle_close_time: '2026-08-30T09:00:00Z',
  generated_at: '2026-08-30T09:00:00Z',
  direction: 'long',
  score: '0.4',
  reason: 'RSI crossed into the oversold region.',
  features: [
    { name: 'previous_rsi', value: '35' },
    { name: 'rsi', value: '28' },
    { name: 'threshold', value: '30' },
  ],
};

const page: Page<StrategySignal> = {
  items: [signal],
  total: 1,
  limit: 20,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

describe('SignalCatalog', () => {
  it('presents RSI identity while preserving versioned historical lineage', () => {
    render(
      <SignalCatalog
        experiments={[experiment]}
        initialExperimentId={experiment.experiment_id}
        initialPage={page}
        locale="en"
      />,
    );

    expect(screen.getByRole('heading', { name: 'RSI Threshold' })).toBeInTheDocument();
    expect(screen.getByText('RSI Threshold v1.0.0')).toBeInTheDocument();
    expect(screen.getByText(signal.signal_id)).toBeInTheDocument();
    expect(screen.getByText(signal.dataset_id)).toBeInTheDocument();
  });
});
