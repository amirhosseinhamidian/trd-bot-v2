import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE_URL,
  getSimulatedPortfolio,
  getSimulatedPortfolioPositions,
  getSimulatedPortfolios,
  getSimulatedPortfolioTimeline,
  getSimulatedPosition,
} from '@/lib/api/client';
import type {
  Page,
  PortfolioTimelineEvent,
  SimulatedPortfolio,
  SimulatedPortfolioSummary,
  SimulatedPosition,
} from '@/lib/api/types';

const portfolioId = 'portfolio-1234567890abcdef';
const positionId = 'position-1234567890abcdef';

const summary: SimulatedPortfolioSummary = {
  portfolio_id: portfolioId,
  mode: 'shadow',
  status: 'completed',
  dataset_id: 'dataset-1234567890abcdef',
  created_at: '2026-08-26T12:00:00Z',
  updated_at: '2026-08-26T16:00:00Z',
  starting_cash: '1000.00000000',
  cash: '1019.58000000',
  equity: '1019.58000000',
  fees_paid: '0.42000000',
  realized_pnl: '19.58000000',
  unrealized_pnl: '0',
  position_count: 1,
  event_count: 5,
};

const position: SimulatedPosition = {
  position_id: positionId,
  portfolio_id: portfolioId,
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  side: 'long',
  status: 'closed',
  quantity: '2',
  entry_price: '100',
  opened_at: '2026-08-26T13:00:00Z',
  current_price: '110',
  current_at: '2026-08-26T15:00:00Z',
  reserved_notional: '200.00000000',
  entry_fee: '0.20000000',
  unrealized_pnl: '0',
  exit_price: '110',
  closed_at: '2026-08-26T15:00:00Z',
  exit_fee: '0.22000000',
  gross_realized_pnl: '20.00000000',
  realized_pnl: '19.58000000',
};

const timelineEvent: PortfolioTimelineEvent = {
  event_id: 'portfolio-event-1234567890abcdef',
  portfolio_id: portfolioId,
  sequence_number: 1,
  event_type: 'portfolio_created',
  occurred_at: '2026-08-26T12:00:00Z',
  equity: '1000.00000000',
  position_id: null,
  price: null,
  quantity: null,
  realized_pnl: null,
};

const portfolio: SimulatedPortfolio = {
  portfolio_id: summary.portfolio_id,
  mode: summary.mode,
  status: summary.status,
  dataset_id: summary.dataset_id,
  created_at: summary.created_at,
  updated_at: summary.updated_at,
  starting_cash: summary.starting_cash,
  cash: summary.cash,
  equity: summary.equity,
  fee_rate: '0.001',
  fees_paid: summary.fees_paid,
  realized_pnl: summary.realized_pnl,
  unrealized_pnl: summary.unrealized_pnl,
  positions: [position],
  timeline: [timelineEvent],
};

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('simulated portfolio read-model client', () => {
  it('loads a paginated portfolio catalog', async () => {
    const page: Page<SimulatedPortfolioSummary> = {
      items: [summary],
      total: 1,
      limit: 6,
      offset: 12,
      count: 1,
      has_next: false,
      has_previous: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getSimulatedPortfolios({ limit: 6, offset: 12 })).resolves.toEqual(page);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/portfolios?limit=6&offset=12`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('loads an encoded portfolio identifier', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(portfolio));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getSimulatedPortfolio('portfolio/id')).resolves.toEqual(portfolio);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/portfolios/portfolio%2Fid`,
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('loads paginated positions and an individual position', async () => {
    const page: Page<SimulatedPosition> = {
      items: [position],
      total: 1,
      limit: 10,
      offset: 0,
      count: 1,
      has_next: false,
      has_previous: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(page))
      .mockResolvedValueOnce(jsonResponse(position));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      getSimulatedPortfolioPositions(portfolioId, { limit: 10, offset: 0 }),
    ).resolves.toEqual(page);
    await expect(getSimulatedPosition(portfolioId, positionId)).resolves.toEqual(position);

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      `/api/v1/research/portfolios/${portfolioId}/positions?limit=10&offset=0`,
    );
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      `/api/v1/research/portfolios/${portfolioId}/positions/${positionId}`,
    );
  });

  it('loads a paginated audit timeline', async () => {
    const page: Page<PortfolioTimelineEvent> = {
      items: [timelineEvent],
      total: 5,
      limit: 2,
      offset: 1,
      count: 1,
      has_next: true,
      has_previous: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      getSimulatedPortfolioTimeline(portfolioId, { limit: 2, offset: 1 }),
    ).resolves.toEqual(page);

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      `/api/v1/research/portfolios/${portfolioId}/timeline?limit=2&offset=1`,
    );
  });
});
