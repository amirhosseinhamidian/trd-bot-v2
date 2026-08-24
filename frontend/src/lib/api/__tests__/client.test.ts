import { afterEach, describe, expect, it, vi } from 'vitest';

import { getExperimentPerformanceSeries, getExperimentSignals } from '@/lib/api/client';
import type { ExperimentPerformanceSeries, Page, StrategySignal } from '@/lib/api/types';

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

describe('research API client', () => {
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
