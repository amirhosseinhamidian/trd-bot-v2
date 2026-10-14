import { getJson } from '@/lib/api/core/transport';

import type { MarketDataMonitoringSummary, MonitoringSummary } from './types';

export async function getMonitoringSummary(): Promise<MonitoringSummary> {
  return getJson<MonitoringSummary>('/api/v1/monitoring/summary');
}

export async function getMarketDataMonitoringSummary(): Promise<MarketDataMonitoringSummary> {
  return getJson<MarketDataMonitoringSummary>('/api/v1/monitoring/market-data');
}
