import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SignalFilterPanel from '@/components/dashboard/signal-filter-panel';
import type { ExperimentSummary } from '@/lib/api/types';

const rsiExperiment: ExperimentSummary = {
  experiment_id: 'experiment-rsi-000001',
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

describe('SignalFilterPanel', () => {
  it('presents the versioned strategy identity for the selected experiment', () => {
    render(
      <SignalFilterPanel
        experiments={[rsiExperiment]}
        initialExperimentId={rsiExperiment.experiment_id}
        isLoading={false}
        locale="en"
        onApply={vi.fn()}
      />,
    );

    const experimentSelect = screen.getByRole('combobox', {
      name: 'Experiment',
    });

    expect(experimentSelect).toHaveTextContent(/RSI Threshold\s*·\s*v\s*1\.0\.0\s*·\s*000001/);
    expect(screen.queryByText(/rsi-threshold/)).not.toBeInTheDocument();
  });
});
