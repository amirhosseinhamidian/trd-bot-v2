import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import OptimizationDetail from '@/features/optimizations/optimization-detail';
import { successfulOptimizationExecution } from '@/test/optimization-fixtures';

const mocks = vi.hoisted(() => ({
  getExecution: vi.fn(),
}));

vi.mock('@/features/optimizations/api/client', () => ({
  getOptimizationExecution: mocks.getExecution,
}));

describe('OptimizationDetail', () => {
  it('renders ranked and rejected out-of-sample evidence with lineage links', () => {
    render(<OptimizationDetail locale="en" initialExecution={successfulOptimizationExecution} />);

    expect(
      screen.getByRole('heading', { name: 'Out-of-sample robustness ranking' }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('optimization-robustness-score-v1')).toHaveLength(2);
    expect(screen.getByText('Insufficient traded folds')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'experiment-1234567890abcdef' })).toHaveAttribute(
      'href',
      '/en/experiments/experiment-1234567890abcdef',
    );
    expect(
      screen.getByRole('link', {
        name: 'walk-forward-execution-fedcba0987654321',
      }),
    ).toHaveAttribute('href', '/en/walk-forward/walk-forward-execution-fedcba0987654321');
    expect(screen.getAllByText('Fast moving-average period=9').length).toBeGreaterThan(0);
    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('keeps each heavy research table in a uniquely labeled scroll region', () => {
    render(<OptimizationDetail locale="en" initialExecution={successfulOptimizationExecution} />);

    const planRegion = screen.getByRole('region', {
      name: 'Parameter plan table; scroll horizontally to view all columns',
    });
    const rankingRegion = screen.getByRole('region', {
      name: 'Out-of-sample robustness ranking table; scroll horizontally to view all columns',
    });
    const rejectedRegion = screen.getByRole('region', {
      name: 'Rejected trial evidence table; scroll horizontally to view all columns',
    });

    for (const region of [planRegion, rankingRegion, rejectedRegion]) {
      expect(region).toHaveAttribute('tabindex', '0');
      expect(region).toHaveClass(
        'min-w-0',
        'max-w-full',
        'touch-pan-x',
        'touch-pan-y',
        'overflow-x-auto',
        'overflow-y-hidden',
      );
    }

    expect(within(planRegion).getByRole('table')).toHaveClass('min-w-[38rem]');
    expect(within(rankingRegion).getByRole('table')).toHaveClass('min-w-[92rem]');
    expect(within(rejectedRegion).getByRole('table')).toHaveClass('min-w-[52rem]');
  });
});
