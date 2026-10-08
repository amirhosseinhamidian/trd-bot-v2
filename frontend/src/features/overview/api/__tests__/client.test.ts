import { afterEach, describe, expect, it, vi } from 'vitest';

import { getResearchActivity, getResearchOverview } from '@/features/overview/api/client';
import type { ResearchActivityItem, ResearchOverview } from '@/features/overview/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/core/types';

const overview: ResearchOverview = {
  dataset_count: 0,
  experiment_count: 0,
  walk_forward_run_count: 0,
  acceptance_policy_preset_count: 0,
  research_stage: 'empty',
  acceptance_policy_presets: [],
  latest_dataset: null,
  latest_experiment: null,
  latest_walk_forward_run: null,
};

const activityPage: Page<ResearchActivityItem> = {
  items: [],
  total: 0,
  limit: 20,
  offset: 0,
  count: 0,
  has_next: false,
  has_previous: false,
};

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('overview client', () => {
  it('loads the research overview as an uncached read', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(overview));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getResearchOverview()).resolves.toEqual(overview);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/overview`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('uses stable pagination defaults for the activity feed', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(activityPage));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getResearchActivity()).resolves.toEqual(activityPage);

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `${API_BASE_URL}/api/v1/research/overview/activity?limit=20&offset=0`,
    );
  });

  it('encodes activity type and inclusive time filters', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(activityPage));
    vi.stubGlobal('fetch', fetchMock);

    await getResearchActivity({
      activityType: 'walk_forward_run',
      fromTime: '2026-08-01T00:00:00.000Z',
      toTime: '2026-08-31T23:59:59.999Z',
      limit: 10,
      offset: 20,
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `${API_BASE_URL}/api/v1/research/overview/activity?limit=10&offset=20&activity_type=walk_forward_run&from_time=2026-08-01T00%3A00%3A00.000Z&to_time=2026-08-31T23%3A59%3A59.999Z`,
    );
  });
});
