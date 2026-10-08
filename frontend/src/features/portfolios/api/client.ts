import { getJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/types';

import type {
  PortfolioAnalyticsReport,
  PortfolioTimelineEvent,
  PositionDetailReport,
  SimulatedPortfolio,
  SimulatedPortfolioSummary,
  SimulatedPosition,
} from './types';

export interface SimulatedPortfolioFilters {
  limit?: number;
  offset?: number;
}

export interface SimulatedPortfolioResourceFilters {
  limit?: number;
  offset?: number;
}

export async function getSimulatedPortfolios(
  filters: SimulatedPortfolioFilters = {},
): Promise<Page<SimulatedPortfolioSummary>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<SimulatedPortfolioSummary>>(
    `/api/v1/research/portfolios?${params.toString()}`,
  );
}

export async function getSimulatedPortfolio(portfolioId: string): Promise<SimulatedPortfolio> {
  return getJson<SimulatedPortfolio>(
    `/api/v1/research/portfolios/${encodeURIComponent(portfolioId)}`,
  );
}

export async function getPortfolioAnalytics(
  portfolioId: string,
): Promise<PortfolioAnalyticsReport> {
  return getJson<PortfolioAnalyticsReport>(
    `/api/v1/research/portfolios/${encodeURIComponent(portfolioId)}/analytics`,
  );
}

export async function getSimulatedPortfolioPositions(
  portfolioId: string,
  filters: SimulatedPortfolioResourceFilters = {},
): Promise<Page<SimulatedPosition>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 20));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<SimulatedPosition>>(
    `/api/v1/research/portfolios/${encodeURIComponent(portfolioId)}/positions?${params.toString()}`,
  );
}

export async function getSimulatedPosition(
  portfolioId: string,
  positionId: string,
): Promise<SimulatedPosition> {
  return getJson<SimulatedPosition>(
    `/api/v1/research/portfolios/${encodeURIComponent(portfolioId)}/positions/${encodeURIComponent(positionId)}`,
  );
}

export async function getSimulatedPositionDetail(
  portfolioId: string,
  positionId: string,
): Promise<PositionDetailReport> {
  return getJson<PositionDetailReport>(
    `/api/v1/research/portfolios/${encodeURIComponent(portfolioId)}/positions/${encodeURIComponent(positionId)}/detail`,
  );
}

export async function getSimulatedPortfolioTimeline(
  portfolioId: string,
  filters: SimulatedPortfolioResourceFilters = {},
): Promise<Page<PortfolioTimelineEvent>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 20));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<PortfolioTimelineEvent>>(
    `/api/v1/research/portfolios/${encodeURIComponent(portfolioId)}/timeline?${params.toString()}`,
  );
}
