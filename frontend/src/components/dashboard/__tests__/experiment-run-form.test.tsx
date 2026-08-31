import type { ReactNode } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ExperimentRunForm from '@/components/dashboard/experiment-run-form';
import { ApiRequestError } from '@/lib/api/client';
import type {
  DatasetSummary,
  ExperimentExecution,
  ExperimentExecutionStatus,
  Page,
  ResearchStrategyMetadata,
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
    createExperimentExecution: apiMocks.createExecution,
    getExperimentExecution: apiMocks.getExecution,
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
  created_at: '2026-08-25T12:00:00Z',
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

function buildExecution(
  status: ExperimentExecutionStatus,
  progressPercent: number,
  experimentId: string | null = null,
): ExperimentExecution {
  return {
    execution_id: 'execution-1234567890abcdef',
    created_at: '2026-08-25T12:00:00Z',
    updated_at: '2026-08-25T12:00:01Z',
    started_at: status === 'queued' ? null : '2026-08-25T12:00:00Z',
    finished_at: status === 'succeeded' || status === 'failed' ? '2026-08-25T12:00:01Z' : null,
    status,
    progress_percent: progressPercent,
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
    experiment_id: experimentId,
    error_code: status === 'failed' ? 'execution_failed' : null,
    error_message: status === 'failed' ? 'The historical experiment could not be completed.' : null,
  };
}

function buildRsiExecution(
  status: ExperimentExecutionStatus,
  progressPercent: number,
  experimentId: string | null = null,
): ExperimentExecution {
  return {
    ...buildExecution(status, progressPercent, experimentId),
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
}

describe('ExperimentRunForm', () => {
  beforeEach(() => {
    apiMocks.getDatasets.mockReset();
    apiMocks.getStrategies.mockReset();
    apiMocks.createExecution.mockReset();
    apiMocks.getExecution.mockReset();
    navigationMocks.push.mockReset();
    navigationMocks.replace.mockReset();

    apiMocks.getDatasets.mockResolvedValue(datasetPage);
    apiMocks.getStrategies.mockResolvedValue(strategyCatalog);
  });

  it('queues an execution, persists its ID, polls its status and opens the result', async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();

    apiMocks.createExecution.mockResolvedValue(buildExecution('queued', 0));
    apiMocks.getExecution.mockResolvedValue(buildExecution('succeeded', 100, 'experiment-ema-btc'));

    render(<ExperimentRunForm locale="en" onCreated={onCreated} />);

    const datasetSelect = await screen.findByLabelText('Dataset');

    expect(
      screen.getByRole('button', {
        name: 'Run historical backtest',
      }),
    ).toHaveClass('w-full', 'sm:w-auto');

    await user.selectOptions(datasetSelect, dataset.dataset_id);

    await user.click(
      screen.getByRole('button', {
        name: 'Run historical backtest',
      }),
    );

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledTimes(1);
    });

    expect(apiMocks.createExecution).toHaveBeenCalledWith({
      dataset_id: 'dataset-btc-usdt-1h',
      strategy_name: 'ema-crossover',
      strategy_version: '1.0.0',
      fast_period: 9,
      slow_period: 21,
      horizon_candles: 1,
      starting_balance: '10000',
      allocation_fraction: '0.10',
      fee_rate: '0.001',
      slippage_rate: '0.0005',
    });

    expect(navigationMocks.replace).toHaveBeenCalledWith(
      '/en/experiments?execution=execution-1234567890abcdef',
    );

    await waitFor(
      () => {
        expect(apiMocks.getExecution).toHaveBeenCalledWith('execution-1234567890abcdef');
      },
      {
        timeout: 2500,
      },
    );

    await waitFor(
      () => {
        expect(onCreated).toHaveBeenCalledWith({
          experiment_id: 'experiment-ema-btc',
        });
      },
      {
        timeout: 2500,
      },
    );

    expect(navigationMocks.push).toHaveBeenCalledWith('/en/experiments/experiment-ema-btc');

    expect(
      screen.getByRole('link', {
        name: 'View experiment result',
      }),
    ).toHaveAttribute('href', '/en/experiments/experiment-ema-btc');
  });

  it('resumes an existing execution without creating a new execution', async () => {
    const onCreated = vi.fn();

    apiMocks.getExecution.mockResolvedValue(buildExecution('succeeded', 100, 'experiment-resumed'));

    render(
      <ExperimentRunForm
        locale="en"
        initialExecutionId="execution-1234567890abcdef"
        onCreated={onCreated}
      />,
    );

    await screen.findByLabelText('Dataset');

    await waitFor(() => {
      expect(apiMocks.getExecution).toHaveBeenCalledWith('execution-1234567890abcdef');
    });

    expect(apiMocks.createExecution).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith({
        experiment_id: 'experiment-resumed',
      });
    });

    expect(navigationMocks.push).toHaveBeenCalledWith('/en/experiments/experiment-resumed');
  });

  it('shows running progress while polling', async () => {
    const user = userEvent.setup();

    apiMocks.createExecution.mockResolvedValue(buildExecution('queued', 0));
    apiMocks.getExecution.mockResolvedValue(buildExecution('running', 45));

    const { unmount } = render(<ExperimentRunForm locale="en" />);

    const datasetSelect = await screen.findByLabelText('Dataset');

    await user.selectOptions(datasetSelect, dataset.dataset_id);

    await user.click(
      screen.getByRole('button', {
        name: 'Run historical backtest',
      }),
    );

    const progressbar = await screen.findByRole('progressbar', {
      name: 'Execution progress',
    });

    await waitFor(() => {
      expect(progressbar).toHaveAttribute('aria-valuenow', '45');
    });

    expect(screen.getByText('The historical backtest is running.')).toBeInTheDocument();

    expect(screen.getByText('The historical backtest is running.')).toBeInTheDocument();

    unmount();
  });

  it('shows a safe localized message when execution fails', async () => {
    const user = userEvent.setup();

    apiMocks.createExecution.mockResolvedValue(buildExecution('queued', 0));
    apiMocks.getExecution.mockResolvedValue(buildExecution('failed', 20));

    render(<ExperimentRunForm locale="en" />);

    const datasetSelect = await screen.findByLabelText('Dataset');

    await user.selectOptions(datasetSelect, dataset.dataset_id);

    await user.click(
      screen.getByRole('button', {
        name: 'Run historical backtest',
      }),
    );

    expect(
      await screen.findByRole(
        'alert',
        {},
        {
          timeout: 2500,
        },
      ),
    ).toHaveTextContent(
      'The historical backtest failed. You can review the parameters and try again.',
    );

    expect(
      screen.queryByText('The historical experiment could not be completed.'),
    ).not.toBeInTheDocument();

    expect(navigationMocks.push).not.toHaveBeenCalled();
  });

  it('uses catalog defaults for strategy-specific fields', async () => {
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

    render(<ExperimentRunForm locale="en" />);

    await screen.findByLabelText('Strategy');

    expect(screen.getByLabelText('Fast moving-average period')).toHaveValue(8);
    expect(screen.getByLabelText('Slow moving-average period')).toHaveValue(20);

    await user.selectOptions(screen.getByLabelText('Strategy'), 'rsi-threshold');

    expect(screen.getByLabelText('RSI period')).toHaveValue(13);
    expect(screen.getByLabelText('Oversold threshold')).toHaveValue(25);
    expect(screen.getByLabelText('Overbought threshold')).toHaveValue(75);
  });

  it('rejects a slow EMA period that is not greater than the fast period', async () => {
    const user = userEvent.setup();

    render(<ExperimentRunForm locale="en" />);

    const datasetSelect = await screen.findByLabelText('Dataset');

    await user.selectOptions(datasetSelect, dataset.dataset_id);

    const fastPeriodInput = screen.getByLabelText('Fast moving-average period');

    await user.clear(fastPeriodInput);
    await user.type(fastPeriodInput, '21');

    await user.click(
      screen.getByRole('button', {
        name: 'Run historical backtest',
      }),
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Slow moving-average period must be greater than the fast moving-average period.',
    );

    expect(apiMocks.createExecution).not.toHaveBeenCalled();
  });

  it('switches to RSI fields and queues an RSI threshold execution', async () => {
    const user = userEvent.setup();

    apiMocks.createExecution.mockResolvedValue(buildRsiExecution('queued', 0));
    apiMocks.getExecution.mockResolvedValue(
      buildRsiExecution('succeeded', 100, 'experiment-rsi-btc'),
    );

    render(<ExperimentRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.selectOptions(screen.getByLabelText('Strategy'), 'rsi-threshold');

    expect(screen.queryByLabelText('Fast moving-average period')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Slow moving-average period')).not.toBeInTheDocument();
    expect(screen.getByLabelText('RSI period')).toHaveValue(14);
    expect(screen.getByLabelText('Oversold threshold')).toHaveValue(30);
    expect(screen.getByLabelText('Overbought threshold')).toHaveValue(70);

    await user.click(screen.getByRole('button', { name: 'Run historical backtest' }));

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledWith({
        dataset_id: dataset.dataset_id,
        strategy_name: 'rsi-threshold',
        strategy_version: '1.0.0',
        period: 14,
        oversold_threshold: '30',
        overbought_threshold: '70',
        horizon_candles: 1,
        starting_balance: '10000',
        allocation_fraction: '0.10',
        fee_rate: '0.001',
        slippage_rate: '0.0005',
      });
    });

    await waitFor(() => {
      expect(navigationMocks.push).toHaveBeenCalledWith('/en/experiments/experiment-rsi-btc');
    });
  });

  it('queues an SMA crossover execution with moving-average parameters', async () => {
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
      ...buildExecution('queued', 0),
      strategy_name: 'sma-crossover',
    });
    apiMocks.getExecution.mockResolvedValue({
      ...buildExecution('succeeded', 100, 'experiment-sma-btc'),
      strategy_name: 'sma-crossover',
    });

    render(<ExperimentRunForm locale="en" />);

    await user.selectOptions(await screen.findByLabelText('Dataset'), dataset.dataset_id);
    await user.selectOptions(screen.getByLabelText('Strategy'), 'sma-crossover');

    expect(screen.getByLabelText('Fast moving-average period')).toHaveValue(9);
    expect(screen.getByLabelText('Slow moving-average period')).toHaveValue(21);

    await user.click(screen.getByRole('button', { name: 'Run historical backtest' }));

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledWith({
        dataset_id: dataset.dataset_id,
        strategy_name: 'sma-crossover',
        strategy_version: '1.0.0',
        fast_period: 9,
        slow_period: 21,
        horizon_candles: 1,
        starting_balance: '10000',
        allocation_fraction: '0.10',
        fee_rate: '0.001',
        slippage_rate: '0.0005',
      });
    });

    await waitFor(() => {
      expect(navigationMocks.push).toHaveBeenCalledWith('/en/experiments/experiment-sma-btc');
    });
  });

  it('shows a safe message when the selected dataset no longer exists', async () => {
    const user = userEvent.setup();

    apiMocks.createExecution.mockRejectedValue(
      new ApiRequestError('API request failed with status 404', 404, {
        detail: 'dataset not found',
      }),
    );

    render(<ExperimentRunForm locale="en" />);

    const datasetSelect = await screen.findByLabelText('Dataset');

    await user.selectOptions(datasetSelect, dataset.dataset_id);

    await user.click(
      screen.getByRole('button', {
        name: 'Run historical backtest',
      }),
    );

    expect(await screen.findByText('The selected dataset no longer exists.')).toBeInTheDocument();

    expect(screen.queryByText('API request failed with status 404')).not.toBeInTheDocument();

    expect(navigationMocks.push).not.toHaveBeenCalled();
  });

  it('prefills and submits values from a previous experiment', async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();

    apiMocks.createExecution.mockResolvedValue({
      ...buildExecution('queued', 0),
      parameters: {
        fast_period: 12,
        slow_period: 34,
        horizon_candles: 3,
        starting_balance: '25000',
        allocation_fraction: '0.20',
        fee_rate: '0.002',
        slippage_rate: '0.0008',
      },
    });

    apiMocks.getExecution.mockResolvedValue({
      ...buildExecution('succeeded', 100, 'experiment-rerun'),
      parameters: {
        fast_period: 12,
        slow_period: 34,
        horizon_candles: 3,
        starting_balance: '25000',
        allocation_fraction: '0.20',
        fee_rate: '0.002',
        slippage_rate: '0.0008',
      },
    });

    render(
      <ExperimentRunForm
        locale="en"
        initialValues={{
          datasetId: 'dataset-btc-usdt-1h',
          fastPeriod: '12',
          slowPeriod: '34',
          horizonCandles: '3',
          startingBalance: '25000',
          allocationFraction: '0.20',
          feeRate: '0.002',
          slippageRate: '0.0008',
        }}
        onCreated={onCreated}
      />,
    );

    const datasetSelect = await screen.findByLabelText('Dataset');

    expect(datasetSelect).toHaveValue('dataset-btc-usdt-1h');
    expect(screen.getByLabelText('Fast moving-average period')).toHaveValue(12);
    expect(screen.getByLabelText('Slow moving-average period')).toHaveValue(34);
    expect(screen.getByLabelText('Evaluation horizon')).toHaveValue(3);
    expect(screen.getByLabelText('Starting balance')).toHaveValue(25000);
    expect(screen.getByLabelText('Allocation fraction')).toHaveValue(0.2);
    expect(screen.getByLabelText('Fee rate')).toHaveValue(0.002);
    expect(screen.getByLabelText('Slippage rate')).toHaveValue(0.0008);

    await user.click(
      screen.getByRole('button', {
        name: 'Run historical backtest',
      }),
    );

    await waitFor(() => {
      expect(apiMocks.createExecution).toHaveBeenCalledWith({
        dataset_id: 'dataset-btc-usdt-1h',
        strategy_name: 'ema-crossover',
        strategy_version: '1.0.0',
        fast_period: 12,
        slow_period: 34,
        horizon_candles: 3,
        starting_balance: '25000',
        allocation_fraction: '0.20',
        fee_rate: '0.002',
        slippage_rate: '0.0008',
      });
    });

    await waitFor(
      () => {
        expect(onCreated).toHaveBeenCalledWith({
          experiment_id: 'experiment-rerun',
        });
      },
      {
        timeout: 2500,
      },
    );

    expect(navigationMocks.push).toHaveBeenCalledWith('/en/experiments/experiment-rerun');
  });
});
