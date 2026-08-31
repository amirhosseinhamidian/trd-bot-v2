import { render, screen } from '@testing-library/react';
import { type AnchorHTMLAttributes, type ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import StrategyCatalog from '@/components/dashboard/strategy-catalog';
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

const strategies: ResearchStrategyMetadata[] = [
  {
    name: 'ema-crossover',
    version: '1.0.0',
    display_name: 'EMA Crossover',
    description: 'Historical EMA crossover strategy.',
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
    ],
  },
  {
    name: 'future-strategy',
    version: '2.1.0',
    display_name: 'Future Strategy',
    description: 'A catalog entry that is not hard-coded in the frontend.',
    parameters: [],
  },
];

describe('StrategyCatalog', () => {
  it('renders backend catalog entries without restricting the workspace to executable names', () => {
    render(<StrategyCatalog locale="en" strategies={strategies} />);

    expect(screen.getByRole('heading', { name: 'Research strategies' })).toBeInTheDocument();
    expect(screen.getByText('EMA Crossover')).toBeInTheDocument();
    expect(screen.getByText('Future Strategy')).toBeInTheDocument();
    expect(screen.getByText('future-strategy@2.1.0')).toBeInTheDocument();

    const detailLinks = screen.getAllByRole('link', { name: 'View strategy details' });
    expect(detailLinks).toHaveLength(2);
    expect(detailLinks[1]).toHaveAttribute('href', '/en/strategies/future-strategy/2.1.0');
  });

  it('renders an explicit empty state when the registry exposes no metadata', () => {
    render(<StrategyCatalog locale="en" strategies={[]} />);

    expect(screen.getByText('No registered strategies')).toBeInTheDocument();
  });
});
