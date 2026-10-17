import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  getMarketContextAssessment,
  getMarketContexts,
} from '@/features/market-context/api/client';
import type { MarketContextProductView } from '@/features/market-context/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/core/types';

const view = {
  schema_version: 'market-context-product-view-v1',
  evaluated_at: '2026-10-16T12:30:00Z',
  expected_as_of: '2026-10-16T12:00:00Z',
  consumable: true,
  unavailable_reasons: [],
  boundary_lag_seconds: 0,
  seconds_until_expiry: 1800,
  assessment: { assessment_id: 'market-regime-1234567890abcdef' },
} as unknown as MarketContextProductView;

const page: Page<MarketContextProductView> = {
  items: [view],
  total: 1,
  limit: 12,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

afterEach(() => vi.unstubAllGlobals());

describe('market-context client', () => {
  it('loads a filtered latest-context page as an uncached read', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(page), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      getMarketContexts({
        limit: 12,
        offset: 0,
        source: 'kraken-public',
        baseAsset: 'BTC',
        quoteAsset: 'USDT',
        marketType: 'spot',
      }),
    ).resolves.toEqual(page);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/market-context?limit=12&offset=0&source=kraken-public&base_asset=BTC&quote_asset=USDT&market_type=spot`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('loads one immutable assessment by its encoded ID', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(view), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getMarketContextAssessment('market-regime/id')).resolves.toEqual(view);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/market-context/market-regime%2Fid`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });
});
