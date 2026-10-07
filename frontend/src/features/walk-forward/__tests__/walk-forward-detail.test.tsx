import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { WalkForwardDetail } from '@/features/walk-forward/walk-forward-detail';
import type { WalkForwardRunSummary, WalkForwardStabilityReport } from '@/lib/api/types';

const run: WalkForwardRunSummary = {
  execution_id: 'walk-forward-execution-1234567890abcdef',
  created_at: '2026-09-20T10:00:00Z',
  source_dataset_id: 'dataset-btc-usdt',
  plan_id: 'walk-forward-fedcba0987654321',
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  horizon_candles: 1,
  strategy_parameters: [
    { name: 'fast_period', value: '9' },
    { name: 'slow_period', value: '21' },
  ],
  walk_forward_config: {
    train_candles: 120,
    test_candles: 24,
    step_candles: 24,
    gap_candles: 0,
    mode: 'rolling',
  },
  backtest_config: {
    starting_balance: '10000',
    allocation_fraction: '0.1',
    fee_rate: '0.001',
    slippage_rate: '0.0005',
  },
  total_folds: 2,
  total_signals: 4,
  folds_with_trades: 1,
  strategy_wins: 1,
  benchmark_wins: 1,
  ties: 0,
  average_strategy_return: '0.01',
  average_benchmark_return: '0.015',
  average_excess_return: '-0.005',
  worst_max_drawdown_fraction: '0.05',
};

const stability: WalkForwardStabilityReport = {
  stability_version: 'walk-forward-stability-v1',
  execution_id: run.execution_id,
  total_folds: 2,
  folds_with_trades: 1,
  folds_without_trades: 1,
  traded_fold_fraction: '0.5',
  positive_return_folds: 1,
  negative_return_folds: 0,
  flat_return_folds: 1,
  positive_return_fraction: '0.5',
  outperforming_benchmark_folds: 1,
  underperforming_benchmark_folds: 1,
  benchmark_ties: 0,
  average_strategy_return: '0.01',
  median_strategy_return: '0.01',
  best_strategy_return: '0.02',
  worst_strategy_return: '0',
  strategy_return_range: '0.02',
  strategy_return_mean_absolute_deviation: '0.01',
  return_consistency: '0.5',
  average_excess_return: '-0.005',
  median_excess_return: '-0.005',
  worst_max_drawdown_fraction: '0.05',
  worst_return_fold_number: 2,
  worst_drawdown_fold_number: 1,
  folds: [
    {
      fold_number: 1,
      total_trades: 3,
      has_trades: true,
      strategy_return: '0.02',
      benchmark_return: '0.01',
      excess_return: '0.01',
      max_drawdown_fraction: '0.05',
      benchmark_max_drawdown_fraction: '0.08',
      return_direction: 'positive',
    },
    {
      fold_number: 2,
      total_trades: 0,
      has_trades: false,
      strategy_return: '0',
      benchmark_return: '0.02',
      excess_return: '-0.02',
      max_drawdown_fraction: '0',
      benchmark_max_drawdown_fraction: '0.03',
      return_direction: 'flat',
    },
  ],
  metric_definitions: [
    {
      key: 'return_consistency',
      unit: 'fraction',
      preference: 'higher_is_better',
      definition: 'Normalized fold-return stability.',
      formula: '1 - normalized_dispersion',
    },
  ],
  interpretation: 'historical_research_only',
};

describe('WalkForwardDetail', () => {
  it('makes fold return, drawdown, consistency, and no-trade evidence explicit', () => {
    render(<WalkForwardDetail locale="en" run={run} stability={stability} />);

    expect(screen.getByRole('img', { name: 'Return by fold chart' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Drawdown by fold chart' })).toBeInTheDocument();
    expect(screen.getByText('Folds without trades')).toBeInTheDocument();
    expect(screen.getByText('No trades')).toBeInTheDocument();
    expect(screen.getByText('Benchmark drawdown')).toBeInTheDocument();
    expect(screen.getByText('1 - normalized_dispersion')).toBeInTheDocument();
  });
});
