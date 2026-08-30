import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  createDataset,
  getExperimentPerformanceSeries,
  getExperimentSignals,
  getResearchStrategies,
} from '@/lib/api/client';
import type {
  DatasetImportRequest,
  DatasetSummary,
  ExperimentPerformanceSeries,
  Page,
  ResearchStrategyMetadata,
  StrategySignal,
} from '@/lib/api/types';

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}

const datasetImportRequest: DatasetImportRequest = {
  name: 'Imported historical BTC dataset',
  source: 'manual-import',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  candles: [
    {
      open_time: '2026-08-20T10:00:00.000Z',
      close_time: '2026-08-20T11:00:00.000Z',
      open_price: '100',
      high_price: '102',
      low_price: '99',
      close_price: '101',
      volume: '1500',
      is_closed: true,
    },
  ],
};

const importedDataset: DatasetSummary = {
  dataset_id: 'dataset-1234567890abcdef',
  schema_version: 1,
  name: datasetImportRequest.name,
  source: datasetImportRequest.source,
  pair: datasetImportRequest.pair,
  timeframe: datasetImportRequest.timeframe,
  start_time: '2026-08-20T10:00:00.000Z',
  end_time: '2026-08-20T11:00:00.000Z',
  created_at: '2026-08-24T12:00:00.000Z',
  candle_count: 1,
  checksum: 'a'.repeat(64),
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('research API client', () => {
  it('retrieves the read-only strategy metadata catalog', async () => {
    const catalog: ResearchStrategyMetadata[] = [
      {
        name: 'rsi-threshold',
        version: '1.0.0',
        display_name: 'RSI Threshold',
        description: 'Historical RSI research strategy.',
        parameters: [
          {
            name: 'period',
            kind: 'integer',
            default_value: '14',
            minimum: '2',
            maximum: null,
            minimum_exclusive: false,
            maximum_exclusive: false,
          },
        ],
      },
    ];

    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(catalog));

    vi.stubGlobal('fetch', fetchMock);

    const result = await getResearchStrategies();

    expect(result).toEqual(catalog);
    expect(fetchMock).toHaveBeenCalledOnce();

    const [requestUrl, requestInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];

    expect(requestUrl).toContain('/api/v1/research/strategies');
    expect(requestInit).toMatchObject({
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      cache: 'no-store',
    });
  });

  it('creates a historical dataset with a JSON request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(importedDataset, 201));

    vi.stubGlobal('fetch', fetchMock);

    const result = await createDataset(datasetImportRequest);

    expect(result).toEqual(importedDataset);
    expect(fetchMock).toHaveBeenCalledOnce();

    const [requestUrl, requestInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];

    expect(requestUrl).toContain('/api/v1/research/datasets');

    expect(requestInit).toMatchObject({
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    expect(JSON.parse(String(requestInit.body))).toEqual(datasetImportRequest);
  });

  it('preserves dataset validation error details', async () => {
    const errorPayload = {
      detail: {
        message: 'dataset failed quality checks',
        candles_checked: 1,
        issues: [
          {
            code: 'open_candle',
            message: 'An unclosed candle was detected.',
            timestamp: '2026-08-20T10:00:00.000Z',
          },
        ],
      },
    };

    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(errorPayload, 422));

    vi.stubGlobal('fetch', fetchMock);

    await expect(createDataset(datasetImportRequest)).rejects.toMatchObject({
      name: 'ApiRequestError',
      status: 422,
      payload: errorPayload,
    });
  });

  it('builds experiment signal query parameters', async () => {
    const page: Page<StrategySignal> = {
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
      count: 0,
      has_next: false,
      has_previous: false,
    };

    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(page));

    vi.stubGlobal('fetch', fetchMock);

    const result = await getExperimentSignals('experiment-1234567890abcdef', {
      direction: 'long',
      candleCloseTimeFrom: '2026-08-21T00:00:00.000Z',
      candleCloseTimeTo: '2026-08-22T23:59:59.999Z',
      sortDirection: 'asc',
      limit: 20,
      offset: 40,
    });

    expect(result).toEqual(page);
    expect(fetchMock).toHaveBeenCalledOnce();

    const requestUrl = String(fetchMock.mock.calls[0]?.[0]);

    expect(requestUrl).toContain(
      '/api/v1/research/experiments/' + 'experiment-1234567890abcdef/signals?',
    );

    expect(requestUrl).toContain('direction=long');
    expect(requestUrl).toContain('sort_direction=asc');
    expect(requestUrl).toContain('limit=20');
    expect(requestUrl).toContain('offset=40');
    expect(requestUrl).toContain('candle_close_time_from=');
    expect(requestUrl).toContain('candle_close_time_to=');
  });

  it('retrieves an experiment performance series', async () => {
    const performanceSeries: ExperimentPerformanceSeries = {
      experiment_id: 'experiment-1234567890abcdef',
      dataset_id: 'dataset-123',
      benchmark_type: 'buy_and_hold',
      strategy: {
        run_id: 'backtest-123',
        starting_balance: '10000',
        ending_balance: '10100',
        total_return: '0.01',
        max_drawdown_fraction: '0',
        points: [],
      },
      benchmark: {
        run_id: 'benchmark-123',
        starting_balance: '10000',
        ending_balance: '10050',
        total_return: '0.005',
        max_drawdown_fraction: '0',
        points: [],
      },
      interpretation: 'historical_research_only',
    };

    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(performanceSeries));

    vi.stubGlobal('fetch', fetchMock);

    const result = await getExperimentPerformanceSeries('experiment-1234567890abcdef');

    expect(result).toEqual(performanceSeries);

    const requestUrl = String(fetchMock.mock.calls[0]?.[0]);

    expect(requestUrl).toContain(
      '/api/v1/research/experiments/' + 'experiment-1234567890abcdef/performance-series',
    );
  });
});
