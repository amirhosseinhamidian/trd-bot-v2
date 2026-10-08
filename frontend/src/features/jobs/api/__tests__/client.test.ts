import { afterEach, describe, expect, it, vi } from 'vitest';

import { getBackgroundJob } from '@/features/jobs/api/client';
import type { BackgroundJobSummary } from '@/features/jobs/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';

const job: BackgroundJobSummary = {
  job_id: 'job / durable',
  kind: 'market_data_import',
  status: 'queued',
  progress_percent: 0,
  attempt_count: 0,
  max_attempts: 3,
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('jobs client', () => {
  it('encodes a durable job identity and performs an uncached read', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(job), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getBackgroundJob(job.job_id)).resolves.toEqual(job);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/jobs/job%20%2F%20durable`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });
});
