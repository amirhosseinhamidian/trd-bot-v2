import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ExperimentPerformanceCharts } from '@/features/experiments/experiment-performance-charts';
import type { ExperimentPerformanceSeries } from '@/lib/api/types';

const performanceSeries: ExperimentPerformanceSeries = {
  experiment_id: 'experiment-1234567890abcdef',
  dataset_id: 'dataset-btc-usdt',
  benchmark_type: 'buy_and_hold',
  period_start: '2026-01-01T00:00:00Z',
  period_end: '2026-01-31T23:00:00Z',
  strategy: {
    run_id: 'strategy-run',
    starting_balance: '10000',
    ending_balance: '10100',
    total_return: '0.01',
    max_drawdown_fraction: '0',
    points: [],
    chart_points: [
      {
        timestamp: '2026-01-01T00:00:00Z',
        balance: '10000',
        drawdown_fraction: '0',
        kind: 'period_start',
        trade_number: null,
      },
      {
        timestamp: '2026-01-15T00:00:00Z',
        balance: '10100',
        drawdown_fraction: '0',
        kind: 'trade_close',
        trade_number: 1,
      },
      {
        timestamp: '2026-01-31T23:00:00Z',
        balance: '10100',
        drawdown_fraction: '0',
        kind: 'period_end',
        trade_number: null,
      },
    ],
  },
  benchmark: {
    run_id: 'benchmark-run',
    starting_balance: '10000',
    ending_balance: '10200',
    total_return: '0.02',
    max_drawdown_fraction: '0',
    points: [],
    chart_points: [
      {
        timestamp: '2026-01-01T00:00:00Z',
        balance: '10000',
        drawdown_fraction: '0',
        kind: 'period_start',
        trade_number: null,
      },
      {
        timestamp: '2026-01-31T23:00:00Z',
        balance: '10200',
        drawdown_fraction: '0',
        kind: 'trade_close',
        trade_number: 1,
      },
    ],
  },
  interpretation: 'historical_research_only',
};

describe('ExperimentPerformanceCharts', () => {
  it('uses aligned chart points for strategy and benchmark time scales', () => {
    const { container } = render(
      <ExperimentPerformanceCharts locale="en" performanceSeries={performanceSeries} />,
    );

    expect(screen.getByRole('img', { name: 'Realized equity' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Realized drawdown' })).toBeInTheDocument();
    expect(container.querySelectorAll('circle')).toHaveLength(10);

    const equityPaths = screen
      .getByRole('img', { name: 'Realized equity' })
      .querySelectorAll('path');
    expect(equityPaths[0]?.getAttribute('d')?.split('L')).toHaveLength(5);
  });
});
