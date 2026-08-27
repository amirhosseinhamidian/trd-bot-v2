import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PortfolioDetail from '@/components/dashboard/portfolio-detail';
import type {
  Page,
  PortfolioTimelineEvent,
  SimulatedPortfolio,
  SimulatedPosition,
} from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getSimulatedPortfolioPositions: vi.fn(),
  getSimulatedPortfolioTimeline: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  getSimulatedPortfolioPositions: mocks.getSimulatedPortfolioPositions,
  getSimulatedPortfolioTimeline: mocks.getSimulatedPortfolioTimeline,
}));

function position(positionId: string): SimulatedPosition {
  return {
    position_id: positionId,
    portfolio_id: 'portfolio-test',
    pair: { base_asset: 'BTC', quote_asset: 'USDT', market_type: 'spot' },
    side: 'long',
    status: 'closed',
    quantity: '1',
    entry_price: '100',
    opened_at: '2026-08-25T10:00:00Z',
    current_price: '110',
    current_at: '2026-08-25T12:00:00Z',
    reserved_notional: '100',
    entry_fee: '1',
    unrealized_pnl: '0',
    exit_price: '110',
    closed_at: '2026-08-25T12:00:00Z',
    exit_fee: '1',
    gross_realized_pnl: '10',
    realized_pnl: '8',
  };
}

function timelineEvent(eventId: string, sequenceNumber: number): PortfolioTimelineEvent {
  return {
    event_id: eventId,
    portfolio_id: 'portfolio-test',
    sequence_number: sequenceNumber,
    event_type: 'position_closed',
    occurred_at: '2026-08-25T12:00:00Z',
    equity: '10008',
    position_id: 'position-initial',
    price: '110',
    quantity: '1',
    realized_pnl: '8',
  };
}

function page<T>(items: T[], offset = 0, total = items.length): Page<T> {
  return {
    items,
    total,
    limit: 10,
    offset,
    count: items.length,
    has_next: offset + 10 < total,
    has_previous: offset > 0,
  };
}

const portfolio: SimulatedPortfolio = {
  portfolio_id: 'portfolio-test',
  mode: 'paper',
  status: 'completed',
  dataset_id: 'dataset-test',
  created_at: '2026-08-25T09:00:00Z',
  updated_at: '2026-08-25T12:00:00Z',
  starting_cash: '10000',
  cash: '10008',
  equity: '10008',
  fee_rate: '0.001',
  fees_paid: '2',
  realized_pnl: '8',
  unrealized_pnl: '0',
  positions: [position('position-initial')],
  timeline: [timelineEvent('event-initial', 3)],
};

describe('PortfolioDetail', () => {
  beforeEach(() => {
    mocks.getSimulatedPortfolioPositions.mockReset();
    mocks.getSimulatedPortfolioTimeline.mockReset();
  });

  it('renders a read-only portfolio report with positions and timeline', () => {
    render(
      <PortfolioDetail
        locale="en"
        portfolio={portfolio}
        initialPositions={page([position('position-initial')])}
        initialTimeline={page([timelineEvent('event-initial', 3)])}
      />,
    );

    expect(screen.getByText('Historical portfolio detail')).toBeInTheDocument();
    expect(screen.getAllByText('portfolio-test')).toHaveLength(2);
    expect(screen.getByText('position-initial')).toBeInTheDocument();
    expect(screen.getByText('Portfolio timeline')).toBeInTheDocument();
    expect(screen.getByText('Position closed')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /create|buy|sell|open|close/i })).toBeNull();
  });

  it('paginates position records through the read API', async () => {
    const user = userEvent.setup();
    const nextPage = page([position('position-next')], 10, 11);
    mocks.getSimulatedPortfolioPositions.mockResolvedValue(nextPage);

    render(
      <PortfolioDetail
        locale="en"
        portfolio={portfolio}
        initialPositions={page([position('position-initial')], 0, 11)}
        initialTimeline={page([timelineEvent('event-initial', 3)])}
      />,
    );

    await user.click(screen.getAllByRole('button', { name: 'Next' })[0]);

    await waitFor(() => {
      expect(mocks.getSimulatedPortfolioPositions).toHaveBeenCalledWith('portfolio-test', {
        limit: 10,
        offset: 10,
      });
    });

    expect(await screen.findByText('position-next')).toBeInTheDocument();
  });
});
