import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ExperimentComparisonPanel from '@/components/dashboard/experiment-comparison-panel';
import type { ExperimentComparisonResult, ExperimentSummary } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  compareExperiments: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  compareExperiments: mocks.compareExperiments,
}));

function buildExperiment(
  experimentId: string,
  strategyName: string,
  parameters: ExperimentSummary['parameters'],
): ExperimentSummary {
  return {
    experiment_id: experimentId,
    created_at: '2026-08-30T08:00:00Z',
    dataset_id: 'dataset-shared',
    strategy_name: strategyName,
    strategy_version: '1.0.0',
    horizon_candles: 3,
    parameters,
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
  };
}

const emaExperiment = buildExperiment('experiment-ema-000001', 'ema-crossover', [
  { name: 'fast_period', value: '9' },
  { name: 'slow_period', value: '21' },
]);

const rsiExperiment = buildExperiment('experiment-rsi-000002', 'rsi-threshold', [
  { name: 'period', value: '14' },
  { name: 'oversold_threshold', value: '30' },
  { name: 'overbought_threshold', value: '70' },
]);

const result: ExperimentComparisonResult = {
  dataset_id: 'dataset-shared',
  horizon_candles: 3,
  metric: 'excess_return',
  ranking_direction: 'higher_is_better',
  compared_experiments: 2,
  best_experiment_id: rsiExperiment.experiment_id,
  entries: [
    {
      position: 1,
      metric_value: '0.02',
      experiment: rsiExperiment,
    },
    {
      position: 2,
      metric_value: '0.01',
      experiment: emaExperiment,
    },
  ],
  interpretation: 'historical_research_only',
};

describe('ExperimentComparisonPanel', () => {
  it('presents EMA and RSI identities and parameters in one historical comparison', async () => {
    const user = userEvent.setup();
    mocks.compareExperiments.mockResolvedValueOnce(result);

    render(
      <ExperimentComparisonPanel
        locale="en"
        onClearSelection={() => undefined}
        selectedExperiments={[emaExperiment, rsiExperiment]}
      />,
    );

    expect(screen.getByText(/EMA Crossover/)).toBeInTheDocument();
    expect(screen.getByText(/RSI Threshold/)).toBeInTheDocument();

    await user.click(
      screen.getByRole('button', {
        name: 'Run historical comparison',
      }),
    );

    expect(await screen.findByText('RSI period=14')).toBeInTheDocument();
    expect(screen.getByText('Oversold threshold=30')).toBeInTheDocument();
    expect(screen.getByText('Fast EMA period=9')).toBeInTheDocument();
  });
});
