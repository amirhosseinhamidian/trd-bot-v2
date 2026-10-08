import { getJson } from '@/lib/api/core/transport';

import type { RiskDashboardReport } from './types';

export interface RiskDashboardFilters {
  fromTime?: string;
  toTime?: string;
  portfolioId?: string;
}

export async function getRiskDashboard(
  filters: RiskDashboardFilters = {},
): Promise<RiskDashboardReport> {
  const params = new URLSearchParams();

  if (filters.fromTime) {
    params.set('from_time', filters.fromTime);
  }

  if (filters.toTime) {
    params.set('to_time', filters.toTime);
  }

  if (filters.portfolioId) {
    params.set('portfolio_id', filters.portfolioId);
  }

  const query = params.toString();
  return getJson<RiskDashboardReport>(`/api/v1/research/risk${query ? `?${query}` : ''}`);
}
