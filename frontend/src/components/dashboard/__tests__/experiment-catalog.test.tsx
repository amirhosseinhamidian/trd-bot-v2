import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ExperimentCatalog from '@/components/dashboard/experiment-catalog';
import type { ExperimentSummary, Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getExperiments: vi.fn(),
  filterInstance: 0,
}));

vi.mock('@/lib/api/client', () => ({
  getExperiments: mocks.getExperiments,
}));

vi.mock('@/components/dashboard/experiment-run-form', () => ({
  default: function MockExperimentRunForm({
    onCreated,
  }: {
    onCreated: (experiment: { experiment_id: string }) => Promise<void> | void;
  }) {
    return (
      <button
        type="button"
        onClick={() =>
          void onCreated({
            experiment_id: 'experiment-new',
          })
        }
      >
        Complete experiment
      </button>
    );
  },
}));

vi.mock('@/components/dashboard/experiment-filter-panel', async () => {
  const { useState } = await import('react');

  return {
    DEFAULT_EXPERIMENT_FILTERS: {
      datasetId: '',
      strategyName: '',
      strategyVersion: '',
      horizonCandles: '',
      createdAtFrom: '',
      createdAtTo: '',
      sortBy: 'created_at',
      sortDirection: 'desc',
    },
    default: function MockExperimentFilterPanel() {
      const [instance] = useState(() => {
        mocks.filterInstance += 1;
        return mocks.filterInstance;
      });

      return <div data-testid="filter-instance">{instance}</div>;
    },
  };
});

vi.mock('@/components/dashboard/experiment-comparison-panel', () => ({
  default: function MockExperimentComparisonPanel() {
    return <div data-testid="comparison-panel" />;
  },
}));

const experiment: ExperimentSummary = {
  experiment_id: 'experiment-new',
  created_at: '2026-08-25T12:00:00Z',
  dataset_id: 'dataset-btc-usdt-1h',
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  horizon_candles: 1,
  parameters: [
    {
      name: 'fast_period',
      value: '9',
    },
    {
      name: 'slow_period',
      value: '21',
    },
  ],
  generated_signals: 2,
  total_trades: 1,
  net_pnl: '100',
  total_return: '0.01',
  win_rate: '1',
  max_drawdown_fraction: '0',
  profit_factor: '2',
  benchmark_type: 'buy_and_hold',
  benchmark_return: '0.005',
  excess_return: '0.005',
  benchmark_max_drawdown_fraction: '0.01',
  max_drawdown_fraction_delta: '-0.01',
  strategy_has_lower_drawdown: true,
  comparison_outcome: 'strategy',
};

const initialPage: Page<ExperimentSummary> = {
  items: [],
  total: 0,
  limit: 12,
  offset: 0,
  count: 0,
  has_next: false,
  has_previous: false,
};

const refreshedPage: Page<ExperimentSummary> = {
  items: [experiment],
  total: 1,
  limit: 12,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

describe('ExperimentCatalog', () => {
  beforeEach(() => {
    mocks.getExperiments.mockReset();
    mocks.filterInstance = 0;
  });

  it('reloads the first page and resets filters after creating an experiment', async () => {
    const user = userEvent.setup();

    mocks.getExperiments.mockResolvedValue(refreshedPage);

    render(<ExperimentCatalog locale="en" initialPage={initialPage} />);

    expect(screen.getByTestId('filter-instance')).toHaveTextContent('1');

    await user.click(
      screen.getByRole('button', {
        name: 'Complete experiment',
      }),
    );

    await waitFor(() => {
      expect(mocks.getExperiments).toHaveBeenCalledTimes(1);
    });

    expect(mocks.getExperiments).toHaveBeenCalledWith(
      expect.objectContaining({
        limit: 12,
        offset: 0,
        sortBy: 'created_at',
        sortDirection: 'desc',
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId('filter-instance')).toHaveTextContent('2');
    });

    expect(await screen.findByText('EMA Crossover')).toBeInTheDocument();

    expect(screen.getByText('experiment-new')).toBeInTheDocument();
  });
});
