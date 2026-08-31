import { afterEach, describe, expect, it, vi } from 'vitest';

import { API_BASE_URL, getMarketDataImport, getMarketDataImportHistory } from '@/lib/api/client';
import type { MarketDataImportRecord, Page } from '@/lib/api/types';

const connectionId = 'market-data-connection-1';
const importRecord: MarketDataImportRecord = {
  import_id: 'market-data-import-1',
  connection_id: connectionId,
  provider_id: 'binance-public',
  dataset_name: 'BTC historical sample',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  requested_start_time: '2026-08-20T00:00:00Z',
  requested_end_time: '2026-08-21T00:00:00Z',
  created_at: '2026-08-31T14:00:00Z',
  completed_at: '2026-08-31T14:00:01Z',
  status: 'succeeded',
  candle_count: 24,
  dataset_id: 'dataset-1234567890abcdef',
  error_code: null,
  error_message: null,
  operation: 'import',
  source_dataset_id: null,
  root_import_id: 'market-data-import-1',
  parent_import_id: null,
  version_number: 1,
  content_changed: null,
};

const page: Page<MarketDataImportRecord> = {
  items: [importRecord],
  total: 1,
  limit: 5,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('market-data import history client', () => {
  it('uses the filtered history and detail endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(page)))
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(importRecord)));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      getMarketDataImportHistory(connectionId, {
        status: 'succeeded',
        limit: 5,
        offset: 0,
      }),
    ).resolves.toEqual(page);
    await expect(getMarketDataImport(connectionId, importRecord.import_id)).resolves.toEqual(
      importRecord,
    );

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/market-data/connections/${connectionId}/imports?limit=5&offset=0&status=succeeded`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/market-data/connections/${connectionId}/imports/${importRecord.import_id}`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });
});
