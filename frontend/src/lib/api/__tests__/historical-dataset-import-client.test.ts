import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE_URL,
  importHistoricalDataset,
  previewHistoricalDatasetImport,
} from '@/lib/api/client';
import type {
  DatasetSummary,
  HistoricalDatasetCommitRequest,
  HistoricalDatasetImportPreview,
  HistoricalDatasetImportRequest,
} from '@/lib/api/types';

const connectionId = 'market-data-connection-1';
const request: HistoricalDatasetImportRequest = {
  name: 'BTC August sample',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  start_time: '2026-08-20T00:00:00.000Z',
  end_time: '2026-08-21T00:00:00.000Z',
};

const preview: HistoricalDatasetImportPreview = {
  connection_id: connectionId,
  provider_id: 'binance-public',
  name: request.name,
  pair: request.pair,
  timeframe: request.timeframe,
  requested_start_time: request.start_time,
  requested_end_time: request.end_time,
  candle_count: 24,
  first_open_time: '2026-08-20T00:00:00Z',
  last_close_time: '2026-08-20T23:59:59.999Z',
  preview_checksum: 'b'.repeat(64),
  quality_report: {
    candles_checked: 24,
    issues: [],
    coverage: {
      requested_start_time: request.start_time,
      requested_end_time: request.end_time,
      expected_first_open_time: request.start_time,
      expected_last_open_time: '2026-08-20T23:00:00Z',
      actual_first_open_time: request.start_time,
      actual_last_close_time: '2026-08-20T23:59:59.999Z',
      expected_candles: 24,
      received_candles: 24,
      missing_candles: 0,
      coverage_percent: 100,
      complete: true,
    },
    score: {
      score_version: 'quality-score-v1',
      score_percent: 100,
      coverage_percent: 100,
      integrity_percent: 100,
    },
    acceptance: {
      policy_version: 'strict-quality-v1',
      accepted: true,
      minimum_score_percent: 100,
      blocking_issue_codes: [],
    },
  },
  ready_to_import: true,
};

const commitRequest: HistoricalDatasetCommitRequest = {
  ...request,
  preview_checksum: preview.preview_checksum,
};

const dataset: DatasetSummary = {
  dataset_id: 'dataset-1234567890abcdef',
  schema_version: 1,
  name: request.name,
  source: 'binance-public',
  pair: request.pair,
  timeframe: request.timeframe,
  start_time: preview.first_open_time!,
  end_time: preview.last_close_time!,
  created_at: '2026-08-31T14:00:00Z',
  candle_count: 24,
  checksum: 'a'.repeat(64),
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

describe('historical dataset import client', () => {
  it('uses the explicit preview and import endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(preview)))
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(dataset, 201)));
    vi.stubGlobal('fetch', fetchMock);

    await expect(previewHistoricalDatasetImport(connectionId, request)).resolves.toEqual(preview);
    await expect(importHistoricalDataset(connectionId, commitRequest)).resolves.toEqual(dataset);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/market-data/connections/${connectionId}/datasets/preview`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
        cache: 'no-store',
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/market-data/connections/${connectionId}/datasets`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(commitRequest),
        cache: 'no-store',
      }),
    );
  });
});
