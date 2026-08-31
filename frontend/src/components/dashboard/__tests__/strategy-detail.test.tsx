import { render, screen } from '@testing-library/react';
import { type AnchorHTMLAttributes, type ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import StrategyDetail from '@/components/dashboard/strategy-detail';
import type { ResearchStrategyMetadata } from '@/lib/api/types';

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

describe('StrategyDetail', () => {
  it('renders exact version metadata and generic parameter constraints', () => {
    render(<StrategyDetail locale="en" strategy={strategy} />);

    expect(screen.getByRole('heading', { name: 'Future Strategy' })).toBeInTheDocument();
    expect(screen.getByText('future-strategy')).toBeInTheDocument();
    expect(screen.getAllByText('2.1.0').length).toBeGreaterThanOrEqual(1);

    expect(screen.getByText('lookback')).toBeInTheDocument();
    expect(screen.getByText('threshold')).toBeInTheDocument();
    expect(screen.getByText('> 0')).toBeInTheDocument();
    expect(screen.getByText('≤ 1')).toBeInTheDocument();
    expect(screen.getByText('No recorded maximum')).toBeInTheDocument();

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
    ).toHaveAttribute('href', '/en/experiments?strategy=ema-crossover');
    expect(
      screen.getByRole('link', { name: 'Start Walk-forward with this strategy' }),
    ).toHaveAttribute('href', '/en/walk-forward?strategy=ema-crossover');
    expect(screen.queryByText('Direct execution is unavailable for this version')).toBeNull();
  });
});
