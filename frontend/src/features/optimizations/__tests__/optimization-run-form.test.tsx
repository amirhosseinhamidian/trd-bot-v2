import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { DatasetSummary } from '@/features/datasets/api/types';
import OptimizationRunForm from '@/features/optimizations/optimization-run-form';
import type { ResearchStrategyMetadata } from '@/features/strategies/api/types';
import type { Page } from '@/lib/api/core/types';
import { optimizationSubmission } from '@/test/optimization-fixtures';

const apiMocks = vi.hoisted(() => ({
  createExecution: vi.fn(),
  getDatasets: vi.fn(),
  getExecution: vi.fn(),
  getStrategies: vi.fn(),
}));

const navigationMocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}));

vi.mock('@/features/datasets/api/client', () => ({
  getDatasets: apiMocks.getDatasets,
}));

vi.mock('@/features/optimizations/api/client', () => ({
  createOptimizationExecution: apiMocks.createExecution,
  getOptimizationExecution: apiMocks.getExecution,
}));

vi.mock('@/features/strategies/api/client', () => ({
  getResearchStrategies: apiMocks.getStrategies,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: navigationMocks.push,
    replace: navigationMocks.replace,
  }),
}));

vi.mock('@/components/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/ui')>();

  return {
    ...actual,
    Select: ({
      label,
      value,
      disabled,
      dir,
      children,
      onValueChange,
    }: {
      label: string;
      value: string;
      disabled?: boolean;
      dir?: 'ltr' | 'rtl';
      children: ReactNode;
      onValueChange: (value: string) => void;
    }) => (
      <label>
        <span>{label}</span>
        <select
          aria-label={label}
          value={value}
          disabled={disabled}
          dir={dir}
          onChange={(event) => onValueChange(event.target.value)}
        >
          {children}
        </select>
      </label>
    ),
    SelectOption: ({ value, children }: { value: string; children: ReactNode }) => (
      <option value={value}>{children}</option>
    ),
  };
});

const dataset: DatasetSummary = {
  dataset_id: 'dataset-btc-usdt-1h',
  schema_version: 1,
  name: 'BTC historical dataset',
  source: 'csv',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  start_time: '2026-01-01T00:00:00Z',
  end_time: '2026-01-10T00:00:00Z',
  created_at: '2026-09-26T12:00:00Z',
  candle_count: 240,
  checksum: 'a'.repeat(64),
};

const datasetPage: Page<DatasetSummary> = {
  items: [dataset],
  total: 1,
  limit: 100,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

const strategies: ResearchStrategyMetadata[] = [
  {
    name: 'ema-crossover',
    version: '1.0.0',
    display_name: 'EMA Crossover',
    description: 'Historical EMA research strategy.',
    parameters: [
      {
        name: 'fast_period',
        kind: 'integer',
        default_value: '9',
        minimum: '2',
        maximum: null,
        minimum_exclusive: false,
        maximum_exclusive: false,
      },
      {
        name: 'slow_period',
        kind: 'integer',
        default_value: '21',
        minimum: '3',
        maximum: null,
        minimum_exclusive: false,
        maximum_exclusive: false,
      },
    ],
  },
];

describe('OptimizationRunForm', () => {
  beforeEach(() => {
    apiMocks.createExecution.mockReset();
    apiMocks.getDatasets.mockReset();
    apiMocks.getExecution.mockReset();
    apiMocks.getStrategies.mockReset();
    navigationMocks.push.mockReset();
    navigationMocks.replace.mockReset();

    apiMocks.getDatasets.mockResolvedValue(datasetPage);
    apiMocks.getStrategies.mockResolvedValue(strategies);
    apiMocks.createExecution.mockResolvedValue(optimizationSubmission);
    apiMocks.getExecution.mockImplementation(() => new Promise(() => undefined));
  });

  it('estimates and queues a bounded robustness workload', async () => {
    const user = userEvent.setup();
    render(<OptimizationRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);

    const fastGrid = screen.getByLabelText('Fast moving-average period');
    const slowGrid = screen.getByLabelText('Slow moving-average period');

    await user.clear(fastGrid);
    await user.type(fastGrid, '10,20');
    await user.clear(slowGrid);
    await user.type(slowGrid, '15,30');

    const estimate = screen.getByText('Bounded workload estimate').parentElement;
    expect(estimate).toHaveTextContent('Requested combinations4');
    expect(estimate).toHaveTextContent('Valid trials3');
    expect(estimate).toHaveTextContent('Skipped combinations1');
    expect(estimate).toHaveTextContent('Trial-fold runs15');

    await user.click(screen.getByRole('button', { name: 'Queue optimization' }));

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledWith({
        dataset_id: dataset.dataset_id,
        strategy_name: 'ema-crossover',
        strategy_version: '1.0.0',
        objective: 'excess_return',
        parameter_grid: [
          { name: 'fast_period', values: ['10', '20'] },
          { name: 'slow_period', values: ['15', '30'] },
        ],
        horizon_candles: 1,
        backtest_config: {
          starting_balance: '10000',
          allocation_fraction: '0.10',
          fee_rate: '0.001',
          slippage_rate: '0.0005',
        },
        walk_forward_config: {
          train_candles: 120,
          test_candles: 24,
          step_candles: 24,
          gap_candles: 0,
          mode: 'rolling',
        },
      });
    });

    expect(navigationMocks.replace).toHaveBeenCalledWith(
      '/en/optimizations?execution=optimization-1234567890abcdef',
    );
  });

  it('blocks workloads above the trial-fold ceiling', async () => {
    const user = userEvent.setup();
    render(<OptimizationRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);

    const fastGrid = screen.getByLabelText('Fast moving-average period');
    const slowGrid = screen.getByLabelText('Slow moving-average period');

    await user.clear(fastGrid);
    await user.type(fastGrid, '2,3,4,5,6,7,8,9,10,11');
    await user.clear(slowGrid);
    await user.type(slowGrid, '30,31,32,33,34,35,36,37,38,39');
    await user.click(screen.getByRole('button', { name: 'Queue optimization' }));

    expect(
      await screen.findByText('The workload can contain at most 300 trial-fold runs.'),
    ).toBeInTheDocument();
    expect(apiMocks.createExecution).not.toHaveBeenCalled();
  });
});
