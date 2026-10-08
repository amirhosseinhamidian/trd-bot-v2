import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  getPortfolioAnalytics,
  getSimulatedPortfolio,
  getSimulatedPortfolioPositions,
  getSimulatedPortfolios,
  getSimulatedPortfolioTimeline,
  getSimulatedPosition,
  getSimulatedPositionDetail,
} from '@/features/portfolios/api/client';
import {
  getPortfolioAnalytics as getPortfolioAnalyticsFacade,
  getSimulatedPortfolio as getSimulatedPortfolioFacade,
  getSimulatedPortfolioPositions as getSimulatedPortfolioPositionsFacade,
  getSimulatedPortfolios as getSimulatedPortfoliosFacade,
  getSimulatedPortfolioTimeline as getSimulatedPortfolioTimelineFacade,
  getSimulatedPosition as getSimulatedPositionFacade,
  getSimulatedPositionDetail as getSimulatedPositionDetailFacade,
} from '@/lib/api/client';

describe('portfolios API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getSimulatedPortfoliosFacade).toBe(getSimulatedPortfolios);
    expect(getSimulatedPortfolioFacade).toBe(getSimulatedPortfolio);
    expect(getPortfolioAnalyticsFacade).toBe(getPortfolioAnalytics);
    expect(getSimulatedPortfolioPositionsFacade).toBe(getSimulatedPortfolioPositions);
    expect(getSimulatedPositionFacade).toBe(getSimulatedPosition);
    expect(getSimulatedPositionDetailFacade).toBe(getSimulatedPositionDetail);
    expect(getSimulatedPortfolioTimelineFacade).toBe(getSimulatedPortfolioTimeline);
  });

  it('keeps portfolio ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const analyticsTypesSource = readFileSync(
      resolve(process.cwd(), 'src/lib/api/portfolio-analytics.ts'),
      'utf8',
    );
    const portfolioClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/portfolios/api/client.ts'),
      'utf8',
    );
    const portfolioTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/portfolios/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/portfolios');
    expect(clientSource).toContain("from '@/features/portfolios/api/client'");
    expect(typesSource).not.toContain('export interface SimulatedPortfolio');
    expect(typesSource).not.toContain('export interface PositionDetailReport');
    expect(typesSource).toContain("from '@/features/portfolios/api/types'");
    expect(analyticsTypesSource).not.toContain('export interface PortfolioAnalyticsReport');
    expect(analyticsTypesSource).toContain("from '@/features/portfolios/api/types'");
    expect(portfolioClientSource).not.toContain('@/lib/api/client');
    expect(portfolioTypesSource).not.toContain('@/lib/api/types');
  });
});
