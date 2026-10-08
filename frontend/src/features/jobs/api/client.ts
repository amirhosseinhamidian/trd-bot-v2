import { getJson } from '@/lib/api/core/transport';

import type { BackgroundJobSummary } from './types';

export async function getBackgroundJob(jobId: string): Promise<BackgroundJobSummary> {
  return getJson<BackgroundJobSummary>(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
}
