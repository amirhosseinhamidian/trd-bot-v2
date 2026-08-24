import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { HistoricalLineChart } from '@/components/charts/historical-line-chart';

const defaultProps = {
  ariaLabel: 'Historical equity chart',
  emptyLabel: 'No historical points',
  formatDate: (value: string) => value.slice(0, 10),
  formatValue: (value: number) => value.toFixed(2),
};

describe('HistoricalLineChart', () => {
  it('renders an empty state when no valid points exist', () => {
    render(
      <HistoricalLineChart
        {...defaultProps}
        series={[
          {
            label: 'Strategy',
            color: '#22d3ee',
            points: [],
          },
        ]}
      />,
    );

    expect(screen.getByText('No historical points')).toBeInTheDocument();

    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('renders accessible series and points', () => {
    const { container } = render(
      <HistoricalLineChart
        {...defaultProps}
        series={[
          {
            label: 'Strategy',
            color: '#22d3ee',
            points: [
              {
                timestamp: '2026-08-21T10:00:00Z',
                value: 10000,
              },
              {
                timestamp: '2026-08-21T11:00:00Z',
                value: 10100,
              },
            ],
          },
          {
            label: 'Benchmark',
            color: '#f59e0b',
            points: [
              {
                timestamp: '2026-08-21T11:00:00Z',
                value: 10050,
              },
            ],
          },
        ]}
      />,
    );

    expect(
      screen.getByRole('img', {
        name: 'Historical equity chart',
      }),
    ).toBeInTheDocument();

    expect(screen.getByText('Strategy')).toBeInTheDocument();

    expect(screen.getByText('Benchmark')).toBeInTheDocument();

    expect(container.querySelectorAll('circle')).toHaveLength(3);

    expect(container.querySelectorAll('path')).toHaveLength(1);
  });

  it('ignores invalid numeric and timestamp values', () => {
    const { container } = render(
      <HistoricalLineChart
        {...defaultProps}
        series={[
          {
            label: 'Strategy',
            color: '#22d3ee',
            points: [
              {
                timestamp: 'invalid-date',
                value: 10000,
              },
              {
                timestamp: '2026-08-21T11:00:00Z',
                value: Number.NaN,
              },
              {
                timestamp: '2026-08-21T12:00:00Z',
                value: 10100,
              },
            ],
          },
        ]}
      />,
    );

    expect(container.querySelectorAll('circle')).toHaveLength(1);
  });
});
