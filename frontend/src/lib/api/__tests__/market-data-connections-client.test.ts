import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE_URL,
  createMarketDataConnection,
  disableMarketDataConnection,
  enableMarketDataConnection,
  getMarketDataConnections,
  getMarketDataProviders,
  testMarketDataConnection,
} from '@/lib/api/client';
import type { MarketDataConnection, MarketDataProviderSummary, Page } from '@/lib/api/types';

const provider: MarketDataProviderSummary = {
  provider_id: 'binance-public',
  display_name: 'Binance Public Market Data',
  requires_credentials: false,
  supported_market_types: ['spot'],
  supported_timeframes: ['15m', '1h', '4h', '1d'],
  default_pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  access_mode: 'vpn_required',
  max_closed_candles: null,
};

const connection: MarketDataConnection = {
  connection_id: 'market-data-connection-1',
  provider_id: 'binance-public',
  display_name: 'Historical feed',
  state: 'disabled',
  health_status: 'untested',
  created_at: '2026-08-31T12:00:00Z',
  updated_at: '2026-08-31T12:00:00Z',
  last_tested_at: null,
  last_error_code: null,
  last_error: null,
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('market-data connections client', () => {
  it('reads provider capabilities and paginated connections', async () => {
    const page: Page<MarketDataConnection> = {
      items: [connection],
      total: 1,
      limit: 12,
      offset: 0,
      count: 1,
      has_next: false,
      has_previous: false,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([provider]))
      .mockResolvedValueOnce(jsonResponse(page));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getMarketDataProviders()).resolves.toEqual([provider]);
    await expect(getMarketDataConnections({ limit: 12, offset: 0 })).resolves.toEqual(page);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/market-data/providers`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/market-data/connections?limit=12&offset=0`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('uses the explicit create, test, enable, and disable endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(connection)));
    vi.stubGlobal('fetch', fetchMock);

    await createMarketDataConnection({
      provider_id: 'binance-public',
      display_name: 'Historical feed',
    });
    await testMarketDataConnection(connection.connection_id);
    await enableMarketDataConnection(connection.connection_id);
    await disableMarketDataConnection(connection.connection_id);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/market-data/connections`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          provider_id: 'binance-public',
          display_name: 'Historical feed',
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/market-data/connections/market-data-connection-1/test`,
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      `${API_BASE_URL}/api/v1/market-data/connections/market-data-connection-1/enable`,
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      `${API_BASE_URL}/api/v1/market-data/connections/market-data-connection-1/disable`,
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
