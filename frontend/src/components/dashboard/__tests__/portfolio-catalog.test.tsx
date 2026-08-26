import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PortfolioCatalog from '@/components/dashboard/portfolio-catalog';
import type { Page, SimulatedPortfolioSummary } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getSimulatedPortfolios: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  getSimulatedPortfolios: mocks.getSimulatedPortfolios,
}));

function makePortfolio(portfolioId: string): SimulatedPortfolioSummary {
  return {
    portfolio_id: portfolioId,
    mode: 'paper',
    status: 'completed',
    dataset_id: 'dataset-btc-hourly',
    created_at: '2026-08-25T10:00:00Z',
    updated_at: '2026-08-25T12:00:00Z',
    starting_cash: '10000',
    cash: '10250',
    equity: '10300',
    fees_paid: '12.5',
    realized_pnl: '250',
    unrealized_pnl: '50',
    position_count: 3,
    event_count: 9,
  };
}

function makePage(
  items: SimulatedPortfolioSummary[],
  offset: number,
): Page<SimulatedPortfolioSummary> {
  return {
    items,
    total: 13,
    limit: 12,
    offset,
    count: items.length,
    has_next: offset === 0,
    has_previous: offset > 0,
  };
}

describe('PortfolioCatalog', () => {
  beforeEach(() => {
    mocks.getSimulatedPortfolios.mockReset();
  });

  it('loads the next read-only report page and keeps locale-aware detail links', async () => {
    const user = userEvent.setup();
    const nextPage = makePage([makePortfolio('portfolio-next')], 12);

    mocks.getSimulatedPortfolios.mockResolvedValue(nextPage);

    render(
      <PortfolioCatalog
        locale="en"
        initialPage={makePage([makePortfolio('portfolio-initial')], 0)}
      />,
    );

    expect(screen.getByText('Historical portfolio reports')).toBeInTheDocument();
    expect(screen.getByText('Read-only research')).toBeInTheDocument();
    expect(screen.getByText('portfolio-initial')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(mocks.getSimulatedPortfolios).toHaveBeenCalledWith({
        limit: 12,
        offset: 12,
      });
    });

    expect(await screen.findByText('portfolio-next')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /view report/i })).toHaveAttribute(
      'href',
      '/en/portfolios/portfolio-next',
    );
    expect(screen.queryByRole('button', { name: /create|buy|sell|open|close/i })).toBeNull();
  });
});
