import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE_URL,
  enqueueMarketDataImportRefresh,
  getMarketDataImportVersions,
  refreshMarketDataImport,
} from '@/lib/api/client';
import type { BackgroundJobSummary, MarketDataImportRecord, Page } from '@/lib/api/types';

const connectionId = 'connection / one';
const importId = 'import / one';

const record: MarketDataImportRecord = {
  import_id: importId,
  connection_id: connectionId,
  provider_id: 'binance-public',
  dataset_name: 'BTC history',
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
  quality_report: null,
  operation: 'import',
  source_dataset_id: null,
  root_import_id: importId,
  parent_import_id: null,
  version_number: 1,
  content_changed: null,
};

const page: Page<MarketDataImportRecord> = {
  items: [record],
  total: 1,
  limit: 5,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

const refreshJob: BackgroundJobSummary = {
  job_id: 'job-abcdef1234567890abcd',
  kind: 'market_data_import',
  status: 'queued',
  progress_percent: 0,
  attempt_count: 0,
  max_attempts: 1,
  run_after: '2026-09-26T08:00:00Z',
  lease_expires_at: null,
  cancel_requested: false,
  result_reference: null,
  error_code: null,
  error_message: null,
  created_at: '2026-09-26T08:00:00Z',
  updated_at: '2026-09-26T08:00:00Z',
  started_at: null,
  finished_at: null,
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

describe('dataset version lineage client', () => {
  it('encodes lineage ids for version history and refresh endpoints', async () => {
    const refreshed: MarketDataImportRecord = {
      ...record,
      import_id: 'market-data-import-refresh',
      operation: 'refresh',
      source_dataset_id: record.dataset_id,
      root_import_id: importId,
      parent_import_id: importId,
      version_number: 2,
      content_changed: false,
    };

    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(page)))
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(refreshed, 201)));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      getMarketDataImportVersions(connectionId, importId, {
        limit: 5,
        offset: 10,
      }),
    ).resolves.toEqual(page);
    await expect(refreshMarketDataImport(connectionId, importId)).resolves.toEqual(refreshed);

    const encodedConnectionId = encodeURIComponent(connectionId);
    const encodedImportId = encodeURIComponent(importId);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/market-data/connections/${encodedConnectionId}/imports/${encodedImportId}/versions?limit=5&offset=10`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/market-data/connections/${encodedConnectionId}/imports/${encodedImportId}/refresh`,
      expect.objectContaining({ method: 'POST', cache: 'no-store' }),
    );
  });

  it('enqueues a durable refresh job with encoded lineage ids', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(refreshJob, 202)));
    vi.stubGlobal('fetch', fetchMock);

    await expect(enqueueMarketDataImportRefresh(connectionId, importId)).resolves.toEqual(
      refreshJob,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/imports/${encodeURIComponent(importId)}/refresh-job`,
      expect.objectContaining({ method: 'POST', cache: 'no-store' }),
    );
  });
});
