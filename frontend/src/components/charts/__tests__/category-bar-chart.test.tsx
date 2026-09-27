import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { CategoryBarChart } from '@/components/charts/category-bar-chart';

describe('CategoryBarChart', () => {
  it('renders positive and negative grouped values accessibly', () => {
    const { container } = render(
      <CategoryBarChart
        ariaLabel="Fold returns"
        emptyLabel="No fold data"
        formatValue={(value) => value.toFixed(2)}
        series={[
          {
            color: '#22d3ee',
            label: 'Strategy',
            points: [
              { category: 'Fold 1', value: 0.1 },
              { category: 'Fold 2', value: -0.05 },
            ],
          },
          {
            color: '#f59e0b',
            label: 'Benchmark',
            points: [
              { category: 'Fold 1', value: 0.04 },
              { category: 'Fold 2', value: 0.02 },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByRole('img', { name: 'Fold returns' })).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('Benchmark')).toBeInTheDocument();
    expect(container.querySelectorAll('rect')).toHaveLength(4);
    expect(screen.getAllByText('Fold 1').length).toBeGreaterThan(0);
  });

  it('renders an empty state when no finite values are available', () => {
    render(
      <CategoryBarChart
        ariaLabel="Fold returns"
        emptyLabel="No fold data"
        formatValue={String}
        series={[
          {
            color: '#22d3ee',
            label: 'Strategy',
            points: [{ category: 'Fold 1', value: Number.NaN }],
          },
        ]}
      />,
    );

    expect(screen.getByText('No fold data')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
