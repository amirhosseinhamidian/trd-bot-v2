import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WalkForwardRunForm from '@/components/dashboard/walk-forward-run-form';
import { ApiRequestError } from '@/lib/api/client';
import type {
  DatasetSummary,
  Page,
  ResearchStrategyMetadata,
  WalkForwardExecution,
} from '@/lib/api/types';

const apiMocks = vi.hoisted(() => ({
  getDatasets: vi.fn(),
  getStrategies: vi.fn(),
  createExecution: vi.fn(),
  getExecution: vi.fn(),
}));

const navigationMocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}));

vi.mock('@/lib/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/client')>();

  return {
    ...actual,
    getDatasets: apiMocks.getDatasets,
    getResearchStrategies: apiMocks.getStrategies,
    createWalkForwardExecution: apiMocks.createExecution,
    getWalkForwardExecution: apiMocks.getExecution,
  };
});

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

const strategyCatalog: ResearchStrategyMetadata[] = [
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
  {
    name: 'rsi-threshold',
    version: '1.0.0',
    display_name: 'RSI Threshold',
    description: 'Historical RSI research strategy.',
    parameters: [
      {
        name: 'period',
        kind: 'integer',
        default_value: '14',
        minimum: '2',
        maximum: null,
        minimum_exclusive: false,
        maximum_exclusive: false,
      },
      {
        name: 'oversold_threshold',
        kind: 'decimal',
        default_value: '30',
        minimum: '0',
        maximum: '50',
        minimum_exclusive: true,
        maximum_exclusive: true,
      },
      {
        name: 'overbought_threshold',
        kind: 'decimal',
        default_value: '70',
        minimum: '50',
        maximum: '100',
        minimum_exclusive: true,
        maximum_exclusive: true,
      },
    ],
  },
];

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
  created_at: '2026-08-26T12:00:00Z',
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

const queuedExecution: WalkForwardExecution = {
  execution_id: 'walk-forward-job-1234567890abcdef',
  created_at: '2026-08-26T12:00:00Z',
  updated_at: '2026-08-26T12:00:00Z',
  started_at: null,
  finished_at: null,
  status: 'queued',
  progress_percent: 0,
  dataset_id: dataset.dataset_id,
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  parameters: {
    fast_period: 9,
    slow_period: 21,
    horizon_candles: 1,
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
  total_folds: 5,
  completed_folds: 0,
  walk_forward_run_id: null,
  error_code: null,
  error_message: null,
};

const queuedRsiExecution: WalkForwardExecution = {
  ...queuedExecution,
  strategy_name: 'rsi-threshold',
  parameters: {
    period: 14,
    oversold_threshold: '30',
    overbought_threshold: '70',
    horizon_candles: 1,
    starting_balance: '10000',
    allocation_fraction: '0.10',
    fee_rate: '0.001',
    slippage_rate: '0.0005',
  },
};

describe('WalkForwardRunForm', () => {
  beforeEach(() => {
    apiMocks.getDatasets.mockReset();
    apiMocks.getStrategies.mockReset();
    apiMocks.createExecution.mockReset();
    apiMocks.getExecution.mockReset();
    navigationMocks.push.mockReset();
    navigationMocks.replace.mockReset();
    apiMocks.getDatasets.mockResolvedValue(datasetPage);
    apiMocks.getStrategies.mockResolvedValue(strategyCatalog);
    apiMocks.getExecution.mockImplementation(() => new Promise(() => undefined));
  });

  it('shows the estimated fold count and queues an execution', async () => {
    const user = userEvent.setup();
    apiMocks.createExecution.mockResolvedValue(queuedExecution);

    render(<WalkForwardRunForm locale="en" />);

    expect(
      await screen.findByRole('button', {
        name: 'Queue historical walk-forward',
      }),
    ).toHaveClass('w-full', 'sm:w-auto');

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);

    const estimateRegion = screen.getByText('Estimated execution').parentElement;
    expect(estimateRegion).toHaveTextContent('Estimated folds');
    expect(estimateRegion).toHaveTextContent('5');

    await user.click(
      screen.getByRole('button', {
        name: 'Queue historical walk-forward',
      }),
    );

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledWith({
        dataset_id: dataset.dataset_id,
        strategy_name: 'ema-crossover',
        strategy_version: '1.0.0',
        fast_period: 9,
        slow_period: 21,
        horizon_candles: 1,
        train_candles: 120,
        test_candles: 24,
        step_candles: 24,
        gap_candles: 0,
        mode: 'rolling',
        starting_balance: '10000',
        allocation_fraction: '0.10',
        fee_rate: '0.001',
        slippage_rate: '0.0005',
      });
    });

    expect(navigationMocks.replace).toHaveBeenCalledWith(
      '/en/walk-forward?execution=walk-forward-job-1234567890abcdef',
    );
    expect(screen.getByText('The walk-forward execution is waiting to start.')).toBeInTheDocument();
  });

  it('switches to RSI fields and queues an RSI threshold walk-forward execution', async () => {
    const user = userEvent.setup();

    apiMocks.createExecution.mockResolvedValue(queuedRsiExecution);

    render(<WalkForwardRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.selectOptions(screen.getByLabelText('Strategy'), 'rsi-threshold');

    expect(screen.queryByLabelText('Fast moving-average period')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Slow moving-average period')).not.toBeInTheDocument();
    expect(screen.getByLabelText('RSI period')).toHaveValue(14);
    expect(screen.getByLabelText('Oversold threshold')).toHaveValue(30);
    expect(screen.getByLabelText('Overbought threshold')).toHaveValue(70);

    await user.click(screen.getByRole('button', { name: 'Queue historical walk-forward' }));

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledWith({
        dataset_id: dataset.dataset_id,
        strategy_name: 'rsi-threshold',
        strategy_version: '1.0.0',
        period: 14,
        oversold_threshold: '30',
        overbought_threshold: '70',
        horizon_candles: 1,
        train_candles: 120,
        test_candles: 24,
        step_candles: 24,
        gap_candles: 0,
        mode: 'rolling',
        starting_balance: '10000',
        allocation_fraction: '0.10',
        fee_rate: '0.001',
        slippage_rate: '0.0005',
      });
    });
  });

  it('queues an SMA crossover walk-forward execution with moving-average parameters', async () => {
    const user = userEvent.setup();

    apiMocks.getStrategies.mockResolvedValue([
      ...strategyCatalog,
      {
        ...strategyCatalog[0],
        name: 'sma-crossover',
        display_name: 'SMA Crossover',
        description: 'Historical SMA research strategy.',
      },
    ]);
    apiMocks.createExecution.mockResolvedValue({
      ...queuedExecution,
      strategy_name: 'sma-crossover',
    });

    render(<WalkForwardRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.selectOptions(screen.getByLabelText('Strategy'), 'sma-crossover');

    expect(screen.getByLabelText('Fast moving-average period')).toHaveValue(9);
    expect(screen.getByLabelText('Slow moving-average period')).toHaveValue(21);

    await user.click(screen.getByRole('button', { name: 'Queue historical walk-forward' }));

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledWith({
        dataset_id: dataset.dataset_id,
        strategy_name: 'sma-crossover',
        strategy_version: '1.0.0',
        fast_period: 9,
        slow_period: 21,
        horizon_candles: 1,
        train_candles: 120,
        test_candles: 24,
        step_candles: 24,
        gap_candles: 0,
        mode: 'rolling',
        starting_balance: '10000',
        allocation_fraction: '0.10',
        fee_rate: '0.001',
        slippage_rate: '0.0005',
      });
    });
  });

  it('uses catalog defaults for strategy-specific walk-forward fields', async () => {
    const user = userEvent.setup();

    apiMocks.getStrategies.mockResolvedValue([
      {
        ...strategyCatalog[0],
        parameters: strategyCatalog[0].parameters.map((parameter) =>
          parameter.name === 'fast_period'
            ? { ...parameter, default_value: '8' }
            : parameter.name === 'slow_period'
              ? { ...parameter, default_value: '20' }
              : parameter,
        ),
      },
      {
        ...strategyCatalog[1],
        parameters: strategyCatalog[1].parameters.map((parameter) =>
          parameter.name === 'period'
            ? { ...parameter, default_value: '13' }
            : parameter.name === 'oversold_threshold'
              ? { ...parameter, default_value: '25' }
              : parameter.name === 'overbought_threshold'
                ? { ...parameter, default_value: '75' }
                : parameter,
        ),
      },
    ]);

    render(<WalkForwardRunForm locale="en" />);

    await screen.findByLabelText('Strategy');

    expect(screen.getByLabelText('Fast moving-average period')).toHaveValue(8);
    expect(screen.getByLabelText('Slow moving-average period')).toHaveValue(20);

    await user.selectOptions(screen.getByLabelText('Strategy'), 'rsi-threshold');

    expect(screen.getByLabelText('RSI period')).toHaveValue(13);
    expect(screen.getByLabelText('Oversold threshold')).toHaveValue(25);
    expect(screen.getByLabelText('Overbought threshold')).toHaveValue(75);
  });

  it('submits expanding mode', async () => {
    const user = userEvent.setup();
    apiMocks.createExecution.mockResolvedValue({
      ...queuedExecution,
      walk_forward_config: {
        ...queuedExecution.walk_forward_config,
        mode: 'expanding',
      },
    });

    render(<WalkForwardRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.selectOptions(screen.getByLabelText('Window mode'), 'expanding');
    await user.click(screen.getByRole('button', { name: 'Queue historical walk-forward' }));

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: 'expanding',
        }),
      );
    });
  });

  it('rejects a step smaller than the test window', async () => {
    const user = userEvent.setup();
    render(<WalkForwardRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    const stepInput = screen.getByLabelText('Step candles');
    await user.clear(stepInput);
    await user.type(stepInput, '12');
    await user.click(screen.getByRole('button', { name: 'Queue historical walk-forward' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Step candles must be greater than or equal to test candles.',
    );
    expect(apiMocks.createExecution).not.toHaveBeenCalled();
  });

  it('rejects a dataset that cannot contain one fold', async () => {
    const user = userEvent.setup();
    apiMocks.getDatasets.mockResolvedValue({
      ...datasetPage,
      items: [
        {
          ...dataset,
          candle_count: 100,
        },
      ],
    });

    render(<WalkForwardRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.click(screen.getByRole('button', { name: 'Queue historical walk-forward' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'The selected dataset does not contain enough candles for one complete fold.',
    );
    expect(apiMocks.createExecution).not.toHaveBeenCalled();
  });

  it('shows a safe message when the selected dataset no longer exists', async () => {
    const user = userEvent.setup();
    apiMocks.createExecution.mockRejectedValue(
      new ApiRequestError('API request failed with status 404', 404, {
        detail: 'dataset not found',
      }),
    );

    render(<WalkForwardRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.click(screen.getByRole('button', { name: 'Queue historical walk-forward' }));

    expect(await screen.findByText('The selected dataset no longer exists.')).toBeInTheDocument();
    expect(screen.queryByText('API request failed with status 404')).not.toBeInTheDocument();
  });

  it('resumes an execution after refresh and opens its stability report', async () => {
    apiMocks.getExecution.mockResolvedValue({
      ...queuedExecution,
      status: 'succeeded',
      progress_percent: 100,
      started_at: '2026-08-26T12:00:01Z',
      finished_at: '2026-08-26T12:00:03Z',
      completed_folds: 5,
      walk_forward_run_id: 'walk-forward-execution-fedcba0987654321',
    });

    render(
      <WalkForwardRunForm locale="en" initialExecutionId="walk-forward-job-1234567890abcdef" />,
    );

    await screen.findByLabelText('Dataset');

    await waitFor(() => {
      expect(apiMocks.getExecution).toHaveBeenCalledWith('walk-forward-job-1234567890abcdef');
    });

    expect(apiMocks.createExecution).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(navigationMocks.push).toHaveBeenCalledWith(
        '/en/walk-forward/walk-forward-execution-fedcba0987654321',
      );
    });
  });

  it('shows fold progress while polling a running execution', async () => {
    const user = userEvent.setup();

    apiMocks.createExecution.mockResolvedValue(queuedExecution);
    apiMocks.getExecution.mockResolvedValue({
      ...queuedExecution,
      status: 'running',
      progress_percent: 40,
      started_at: '2026-08-26T12:00:01Z',
      completed_folds: 2,
    });

    const { unmount } = render(<WalkForwardRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.click(screen.getByRole('button', { name: 'Queue historical walk-forward' }));

    const progressbar = await screen.findByRole('progressbar', {
      name: 'Fold progress',
    });

    await waitFor(() => {
      expect(progressbar).toHaveAttribute('aria-valuenow', '40');
    });

    expect(screen.getByText(/Completed folds/u)).toHaveTextContent('2/5');

    unmount();
  });

  it('shows a safe localized message when the background execution fails', async () => {
    const user = userEvent.setup();

    apiMocks.createExecution.mockResolvedValue(queuedExecution);
    apiMocks.getExecution.mockResolvedValue({
      ...queuedExecution,
      status: 'failed',
      progress_percent: 40,
      started_at: '2026-08-26T12:00:01Z',
      finished_at: '2026-08-26T12:00:03Z',
      completed_folds: 2,
      error_code: 'walk_forward_execution_failed',
      error_message: 'Internal details must not be shown.',
    });

    render(<WalkForwardRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.click(screen.getByRole('button', { name: 'Queue historical walk-forward' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The historical walk-forward execution failed.',
    );
    expect(screen.queryByText('Internal details must not be shown.')).not.toBeInTheDocument();
    expect(navigationMocks.push).not.toHaveBeenCalled();
  });
});
