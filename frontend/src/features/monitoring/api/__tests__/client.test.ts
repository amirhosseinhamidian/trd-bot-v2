import { afterEach, describe, expect, it, vi } from 'vitest';

import { getMonitoringSummary } from '@/features/monitoring/api/client';
import type { MonitoringSummary } from '@/features/monitoring/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';

const summary: MonitoringSummary = {
  overall_status: 'healthy',
  latest_metrics: [],
  active_recommendations: [],
  operations: null,
  interpretation: 'capacity_planning_only',
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
});
