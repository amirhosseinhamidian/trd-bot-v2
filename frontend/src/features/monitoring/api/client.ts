import { getJson } from '@/lib/api/core/transport';

import type { MonitoringSummary } from './types';

export async function getMonitoringSummary(): Promise<MonitoringSummary> {
  return getJson<MonitoringSummary>('/api/v1/monitoring/summary');
}
