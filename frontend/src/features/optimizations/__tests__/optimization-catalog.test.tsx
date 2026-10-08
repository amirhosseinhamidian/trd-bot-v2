import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { OptimizationExecution } from '@/features/optimizations/api/types';
import OptimizationCatalog from '@/features/optimizations/optimization-catalog';
import type { Page } from '@/lib/api/types';
import { queuedOptimizationExecution } from '@/test/optimization-fixtures';

vi.mock('@/features/optimizations/optimization-run-form', () => ({
  default: function MockOptimizationRunForm({
    initialExecutionId,
  }: {
    initialExecutionId?: string;
  }) {
    return <div data-testid="optimization-run-form">{initialExecutionId ?? 'new'}</div>;
  },
}));

const page: Page<OptimizationExecution> = {
  items: [queuedOptimizationExecution],
  total: 1,
  limit: 12,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

describe('OptimizationCatalog', () => {
  it('renders durable execution state and preserves a resumed execution ID', () => {
    render(
      <OptimizationCatalog
        locale="en"
        initialPage={page}
        initialExecutionId="optimization-1234567890abcdef"
      />,
    );

    expect(screen.getByRole('heading', { name: 'Strategy optimizations' })).toBeInTheDocument();
    expect(screen.getByTestId('optimization-run-form')).toHaveTextContent(
      'optimization-1234567890abcdef',
    );
    expect(screen.getByText('Queued')).toBeInTheDocument();
    expect(screen.getByText('0/2')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View robustness ranking' })).toHaveAttribute(
      'href',
      '/en/optimizations/optimization-1234567890abcdef',
    );
  });
});
