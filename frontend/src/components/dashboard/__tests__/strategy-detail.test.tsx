import { render, screen } from '@testing-library/react';
import { type AnchorHTMLAttributes, type ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import StrategyDetail from '@/components/dashboard/strategy-detail';
import type { ExperimentSummary, Page, ResearchStrategyMetadata } from '@/lib/api/types';

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const strategy: ResearchStrategyMetadata = {
  name: 'future-strategy',
  version: '2.1.0',
  display_name: 'Future Strategy',
  description: 'Generic metadata should remain presentable without a frontend-specific branch.',
  lifecycle_status: 'active',
  supersedes_version: '2.0.0',
  behavior_fingerprint: `sha256:${'a'.repeat(64)}`,
  parameters: [
    {
      name: 'lookback',
      kind: 'integer',
      default_value: '20',
      minimum: '2',
      maximum: null,
      minimum_exclusive: false,
      maximum_exclusive: false,
    },
    {
      name: 'threshold',
      kind: 'decimal',
      default_value: '0.5',
      minimum: '0',
      maximum: '1',
      minimum_exclusive: true,
      maximum_exclusive: false,
    },
  ],
};

const recordedExperiment: ExperimentSummary = {
  experiment_id: 'experiment-1234567890abcdef',
  created_at: '2026-09-26T08:00:00Z',
  dataset_id: 'dataset-1234567890abcdef',
  strategy_name: strategy.name,
  strategy_version: strategy.version,
  strategy_fingerprint: strategy.behavior_fingerprint,
  horizon_candles: 1,
  parameters: [],
  generated_signals: 2,
  total_trades: 1,
  net_pnl: '10',
  total_return: '0.01',
  win_rate: '1',
  max_drawdown_fraction: '0',
  profit_factor: null,
  benchmark_type: 'buy_and_hold',
  benchmark_return: '0.005',
  excess_return: '0.005',
  benchmark_max_drawdown_fraction: '0.01',
  max_drawdown_fraction_delta: '-0.01',
  strategy_has_lower_drawdown: true,
  comparison_outcome: 'strategy',
};

const experimentHistory: Page<ExperimentSummary> = {
  items: [recordedExperiment],
  total: 1,
  limit: 5,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

describe('StrategyDetail', () => {
  it('renders exact version metadata and generic parameter constraints', () => {
    render(
      <StrategyDetail locale="en" strategy={strategy} experimentHistory={experimentHistory} />,
    );

    expect(screen.getByRole('heading', { name: 'Future Strategy' })).toBeInTheDocument();
    expect(screen.getByText('future-strategy')).toBeInTheDocument();
    expect(screen.getAllByText('2.1.0').length).toBeGreaterThanOrEqual(1);

    expect(screen.getByText('lookback')).toBeInTheDocument();
    expect(screen.getByText('threshold')).toBeInTheDocument();
    expect(screen.getByText('> 0')).toBeInTheDocument();
    expect(screen.getByText('≤ 1')).toBeInTheDocument();
    expect(screen.getByText('No recorded maximum')).toBeInTheDocument();
    expect(screen.getByText(strategy.behavior_fingerprint!)).toBeInTheDocument();
    expect(screen.getByText(recordedExperiment.experiment_id)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View experiment' })).toHaveAttribute(
      'href',
      `/en/experiments/${recordedExperiment.experiment_id}`,
    );

    expect(screen.getByRole('link', { name: /Back to strategies/u })).toHaveAttribute(
      'href',
      '/en/strategies',
    );

    expect(screen.queryByRole('link', { name: 'Start Experiment with this strategy' })).toBeNull();
    expect(
      screen.getByText('Direct execution is unavailable for this version'),
    ).toBeInTheDocument();
  });

  it('offers research launch links only for an exact executable strategy version', () => {
    render(
      <StrategyDetail
        locale="en"
        strategy={{
          ...strategy,
          name: 'ema-crossover',
          version: '1.0.0',
          display_name: 'EMA Crossover',
        }}
      />,
    );

    expect(
      screen.getByRole('link', { name: 'Start Experiment with this strategy' }),
    ).toHaveAttribute('href', '/en/experiments?strategy=ema-crossover&strategy_version=1.0.0');
    expect(
      screen.getByRole('link', { name: 'Start Walk-forward with this strategy' }),
    ).toHaveAttribute('href', '/en/walk-forward?strategy=ema-crossover&strategy_version=1.0.0');
    expect(screen.queryByText('Direct execution is unavailable for this version')).toBeNull();
  });
});
