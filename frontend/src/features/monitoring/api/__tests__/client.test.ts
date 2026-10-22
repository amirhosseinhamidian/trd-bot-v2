import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  getMarketContextMonitoringSummary,
  getMarketDataMonitoringSummary,
  getMonitoringSummary,
} from '@/features/monitoring/api/client';
import type {
  MarketContextMonitoringSummary,
  MarketDataMonitoringSummary,
  MonitoringSummary,
} from '@/features/monitoring/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';

const summary: MonitoringSummary = {
  overall_status: 'healthy',
  latest_metrics: [],
  active_recommendations: [],
  operations: null,
  interpretation: 'capacity_planning_only',
};

const marketDataSummary: MarketDataMonitoringSummary = {
  schema_version: 'market-data-monitoring-v1',
  generated_at: '2026-10-14T12:00:00Z',
  overall_status: 'no_data',
  stream_count: 0,
  healthy_count: 0,
  degraded_count: 0,
  stale_count: 0,
  no_data_count: 0,
  paused_count: 0,
  backlog: {
    poll_jobs: 0,
    replay_jobs: 0,
    overdue_watchlists: 0,
    finalization_windows: 0,
    unrequested_revisions: 0,
    pending_replays: 0,
    failed_replays: 0,
    completed_revisions: 0,
  },
  streams: [],
  recent_replays: [],
};

const marketContextSummary: MarketContextMonitoringSummary = {
  schema_version: 'market-context-monitoring-v1',
  generated_at: '2026-10-16T12:30:00Z',
  overall_status: 'no_data',
  stream_count: 0,
  healthy_count: 0,
  degraded_count: 0,
  stale_count: 0,
  no_data_count: 0,
  backlog: {
    queued_jobs: 0,
    running_jobs: 0,
    retrying_jobs: 0,
    failed_streams: 0,
    expired_assessments: 0,
    lagging_streams: 0,
    missing_assessments: 0,
  },
  streams: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('monitoring client', () => {
  it('loads the monitoring summary as an uncached read', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(summary), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getMonitoringSummary()).resolves.toEqual(summary);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/monitoring/summary`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('loads the market-data health projection as an uncached read', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(marketDataSummary), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getMarketDataMonitoringSummary()).resolves.toEqual(marketDataSummary);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/monitoring/market-data`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('loads the market-context health projection as an uncached read', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(marketContextSummary), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getMarketContextMonitoringSummary()).resolves.toEqual(marketContextSummary);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/monitoring/market-context`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });
});
