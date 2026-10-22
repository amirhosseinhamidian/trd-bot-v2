import { getJson } from '@/lib/api/core/transport';

import type {
  MarketContextMonitoringSummary,
  MarketDataMonitoringSummary,
  MonitoringSummary,
} from './types';

export async function getMonitoringSummary(): Promise<MonitoringSummary> {
  return getJson<MonitoringSummary>('/api/v1/monitoring/summary');
}

export async function getMarketDataMonitoringSummary(): Promise<MarketDataMonitoringSummary> {
  return getJson<MarketDataMonitoringSummary>('/api/v1/monitoring/market-data');
}

export async function getMarketContextMonitoringSummary(): Promise<MarketContextMonitoringSummary> {
  return getJson<MarketContextMonitoringSummary>('/api/v1/monitoring/market-context');
}
