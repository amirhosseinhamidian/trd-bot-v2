import { isValidElement } from 'react';

import { describe, expect, it, vi } from 'vitest';

import type { Locale } from '@/i18n/config';

const screens = vi.hoisted(() => ({
  candidateCatalog: () => null,
  candidateDetail: () => null,
  connections: () => null,
  datasetCatalog: () => null,
  datasetDetail: () => null,
  experimentCatalog: () => null,
  experimentDetail: () => null,
  monitoring: () => null,
  overview: () => null,
  portfolioCatalog: () => null,
  portfolioDetail: () => null,
  positionDetail: () => null,
  risk: () => null,
  walkForwardCatalog: () => null,
  walkForwardDetail: () => null,
}));

const api = vi.hoisted(() => ({
  getAcceptancePolicyPresets: vi.fn(async () => 'acceptance-policy-presets'),
  getCandidateLineage: vi.fn(async () => 'candidate-lineage'),
  getCandidateProjection: vi.fn(async () => 'candidate-projection'),
  getCandidateProjections: vi.fn(async () => 'candidate-page'),
  getDatasetCandles: vi.fn(async () => 'dataset-candles'),
  getDatasetSummary: vi.fn(async () => 'dataset-summary'),
  getDatasets: vi.fn(async () => 'dataset-page'),
  getExperimentAnalytics: vi.fn(async () => 'experiment-analytics'),
  getExperimentPerformanceSeries: vi.fn(async () => 'experiment-performance'),
  getExperimentSummary: vi.fn(async () => 'experiment-summary'),
  getExperiments: vi.fn(async () => 'experiment-page'),
  getMarketDataConnections: vi.fn(async () => 'connection-page'),
  getMarketDataProviders: vi.fn(async () => 'market-data-providers'),
  getMonitoringSummary: vi.fn(async () => 'monitoring-summary'),
  getPortfolioAnalytics: vi.fn(async () => 'portfolio-analytics'),
  getResearchActivity: vi.fn(async () => 'research-activity'),
  getResearchOverview: vi.fn(async () => 'research-overview'),
  getRiskDashboard: vi.fn(async () => 'risk-report'),
  getSimulatedPortfolio: vi.fn(async () => 'portfolio-summary'),
  getSimulatedPortfolioPositions: vi.fn(async () => 'portfolio-positions'),
  getSimulatedPortfolioTimeline: vi.fn(async () => 'portfolio-timeline'),
  getSimulatedPortfolios: vi.fn(async () => ({ items: ['portfolio-summary'] })),
  getSimulatedPositionDetail: vi.fn(async () => 'position-report'),
  getWalkForwardRuns: vi.fn(async () => 'walk-forward-page'),
  getWalkForwardRunSummary: vi.fn(async () => 'walk-forward-summary'),
  getWalkForwardStabilityReport: vi.fn(async () => 'walk-forward-stability'),
  notFound: vi.fn(() => {
    throw new Error('not found');
  }),
}));

vi.mock('next/navigation', () => ({ notFound: api.notFound }));

vi.mock('@/features/overview/api/client', () => ({
  getResearchActivity: api.getResearchActivity,
  getResearchOverview: api.getResearchOverview,
}));
vi.mock('@/features/overview/overview-dashboard', () => ({ default: screens.overview }));

vi.mock('@/features/datasets/api/client', () => ({
  getDatasetCandles: api.getDatasetCandles,
  getDatasetSummary: api.getDatasetSummary,
  getDatasets: api.getDatasets,
}));
vi.mock('@/features/datasets/dataset-catalog', () => ({ default: screens.datasetCatalog }));
vi.mock('@/features/datasets/dataset-detail', () => ({ default: screens.datasetDetail }));

vi.mock('@/features/experiments/api/client', () => ({
  getAcceptancePolicyPresets: api.getAcceptancePolicyPresets,
  getExperimentAnalytics: api.getExperimentAnalytics,
  getExperimentPerformanceSeries: api.getExperimentPerformanceSeries,
  getExperimentSummary: api.getExperimentSummary,
  getExperiments: api.getExperiments,
}));
vi.mock('@/features/experiments/experiment-catalog', () => ({
  default: screens.experimentCatalog,
}));
vi.mock('@/features/experiments/experiment-detail', () => ({
  ExperimentDetail: screens.experimentDetail,
}));

vi.mock('@/features/walk-forward/api/client', () => ({
  getWalkForwardRuns: api.getWalkForwardRuns,
  getWalkForwardRunSummary: api.getWalkForwardRunSummary,
  getWalkForwardStabilityReport: api.getWalkForwardStabilityReport,
}));
vi.mock('@/features/walk-forward/walk-forward-catalog', () => ({
  default: screens.walkForwardCatalog,
}));
vi.mock('@/features/walk-forward/walk-forward-detail', () => ({
  WalkForwardDetail: screens.walkForwardDetail,
}));

vi.mock('@/features/candidates/api/client', () => ({
  getCandidateLineage: api.getCandidateLineage,
  getCandidateProjection: api.getCandidateProjection,
  getCandidateProjections: api.getCandidateProjections,
}));
vi.mock('@/features/candidates/candidate-catalog', () => ({
  default: screens.candidateCatalog,
}));
vi.mock('@/features/candidates/candidate-detail', () => ({ default: screens.candidateDetail }));

vi.mock('@/features/risk/api/client', () => ({ getRiskDashboard: api.getRiskDashboard }));
vi.mock('@/features/risk/risk-dashboard', () => ({ default: screens.risk }));

vi.mock('@/features/portfolios/api/client', () => ({
  getPortfolioAnalytics: api.getPortfolioAnalytics,
  getSimulatedPortfolio: api.getSimulatedPortfolio,
  getSimulatedPortfolioPositions: api.getSimulatedPortfolioPositions,
  getSimulatedPortfolios: api.getSimulatedPortfolios,
  getSimulatedPortfolioTimeline: api.getSimulatedPortfolioTimeline,
  getSimulatedPositionDetail: api.getSimulatedPositionDetail,
}));
vi.mock('@/features/portfolios/portfolio-catalog', () => ({
  default: screens.portfolioCatalog,
}));
vi.mock('@/features/portfolios/portfolio-detail', () => ({ default: screens.portfolioDetail }));
vi.mock('@/features/portfolios/position-detail', () => ({ default: screens.positionDetail }));

vi.mock('@/features/connections/api/client', () => ({
  getMarketDataConnections: api.getMarketDataConnections,
  getMarketDataProviders: api.getMarketDataProviders,
}));
vi.mock('@/features/connections/market-data-connections-panel', () => ({
  default: screens.connections,
}));

vi.mock('@/features/monitoring/api/client', () => ({
  getMonitoringSummary: api.getMonitoringSummary,
}));
vi.mock('@/features/monitoring/monitoring-dashboard', () => ({ default: screens.monitoring }));

import CandidateDetailPage from '@/app/[locale]/candidates/[candidateId]/page';
import CandidatesPage from '@/app/[locale]/candidates/page';
import ConnectionsPage from '@/app/[locale]/connections/page';
import DatasetDetailPage from '@/app/[locale]/datasets/[datasetId]/page';
import DatasetsPage from '@/app/[locale]/datasets/page';
import ExperimentDetailPage from '@/app/[locale]/experiments/[experimentId]/page';
import ExperimentsPage from '@/app/[locale]/experiments/page';
import MonitoringPage from '@/app/[locale]/monitoring/page';
import LocalePage from '@/app/[locale]/page';
import PortfolioDetailPage from '@/app/[locale]/portfolios/[portfolioId]/page';
import PositionDetailPage from '@/app/[locale]/portfolios/[portfolioId]/positions/[positionId]/page';
import PortfoliosPage from '@/app/[locale]/portfolios/page';
import RiskPage from '@/app/[locale]/risk/page';
import WalkForwardDetailPage from '@/app/[locale]/walk-forward/[executionId]/page';
import WalkForwardPage from '@/app/[locale]/walk-forward/page';

type LocalizedScreenProps = {
  locale: Locale;
  [key: string]: unknown;
};

function expectLocalizedScreen(element: unknown, screen: unknown, locale: Locale) {
  expect(isValidElement(element)).toBe(true);

  if (!isValidElement<LocalizedScreenProps>(element)) {
    throw new Error('Expected a valid localized screen element');
  }

  expect(element.type).toBe(screen);
  expect(element.props.locale).toBe(locale);

  return element.props;
}

describe.each(['fa', 'en'] as const)('P6 critical user journeys in %s', (locale) => {
  it('loads the overview and research entry point', async () => {
    const props = expectLocalizedScreen(
      await LocalePage({ params: Promise.resolve({ locale }) }),
      screens.overview,
      locale,
    );

    expect(props.overview).toBe('research-overview');
    expect(props.activityPage).toBe('research-activity');
    expect(api.getResearchActivity).toHaveBeenCalledWith({ limit: 10, offset: 0 });
  });

  it('moves from the dataset catalog to a selected dataset', async () => {
    const catalogProps = expectLocalizedScreen(
      await DatasetsPage({ params: Promise.resolve({ locale }) }),
      screens.datasetCatalog,
      locale,
    );
    const detailProps = expectLocalizedScreen(
      await DatasetDetailPage({
        params: Promise.resolve({ datasetId: 'dataset-01', locale }),
      }),
      screens.datasetDetail,
      locale,
    );

    expect(catalogProps.initialPage).toBe('dataset-page');
    expect(detailProps.dataset).toBe('dataset-summary');
    expect(detailProps.initialCandlesPage).toBe('dataset-candles');
    expect(api.getDatasetSummary).toHaveBeenCalledWith('dataset-01');
    expect(api.getDatasetCandles).toHaveBeenCalledWith('dataset-01', {
      limit: 25,
      offset: 0,
    });
  });

  it('loads experiment and walk-forward catalogs, details, and analytics', async () => {
    const experimentCatalogProps = expectLocalizedScreen(
      await ExperimentsPage({
        params: Promise.resolve({ locale }),
        searchParams: Promise.resolve({}),
      }),
      screens.experimentCatalog,
      locale,
    );
    const experimentDetailProps = expectLocalizedScreen(
      await ExperimentDetailPage({
        params: Promise.resolve({ experimentId: 'experiment-01', locale }),
      }),
      screens.experimentDetail,
      locale,
    );
    const walkForwardCatalogProps = expectLocalizedScreen(
      await WalkForwardPage({
        params: Promise.resolve({ locale }),
        searchParams: Promise.resolve({}),
      }),
      screens.walkForwardCatalog,
      locale,
    );
    const walkForwardDetailProps = expectLocalizedScreen(
      await WalkForwardDetailPage({
        params: Promise.resolve({ executionId: 'walk-forward-01', locale }),
      }),
      screens.walkForwardDetail,
      locale,
    );

    expect(experimentCatalogProps.initialPage).toBe('experiment-page');
    expect(experimentDetailProps.experiment).toBe('experiment-summary');
    expect(experimentDetailProps.analytics).toBe('experiment-analytics');
    expect(experimentDetailProps.performanceSeries).toBe('experiment-performance');
    expect(walkForwardCatalogProps.initialPage).toBe('walk-forward-page');
    expect(walkForwardDetailProps.run).toBe('walk-forward-summary');
    expect(walkForwardDetailProps.stability).toBe('walk-forward-stability');
    expect(api.getExperimentAnalytics).toHaveBeenCalledWith('experiment-01');
    expect(api.getWalkForwardStabilityReport).toHaveBeenCalledWith('walk-forward-01');
  });

  it('loads candidate decision evidence and the risk status screen', async () => {
    const catalogProps = expectLocalizedScreen(
      await CandidatesPage({ params: Promise.resolve({ locale }) }),
      screens.candidateCatalog,
      locale,
    );
    const detailProps = expectLocalizedScreen(
      await CandidateDetailPage({
        params: Promise.resolve({ candidateId: 'candidate-01', locale }),
      }),
      screens.candidateDetail,
      locale,
    );
    const riskProps = expectLocalizedScreen(
      await RiskPage({ params: Promise.resolve({ locale }) }),
      screens.risk,
      locale,
    );

    expect(catalogProps.initialPage).toBe('candidate-page');
    expect(detailProps.candidate).toBe('candidate-projection');
    expect(detailProps.initialLineage).toBe('candidate-lineage');
    expect(riskProps.initialReport).toBe('risk-report');
    expect(riskProps.portfolios).toEqual(['portfolio-summary']);
    expect(api.getCandidateProjection).toHaveBeenCalledWith('candidate-01');
  });

  it('moves through historical portfolios down to position evidence', async () => {
    const catalogProps = expectLocalizedScreen(
      await PortfoliosPage({ params: Promise.resolve({ locale }) }),
      screens.portfolioCatalog,
      locale,
    );
    const detailProps = expectLocalizedScreen(
      await PortfolioDetailPage({
        params: Promise.resolve({ locale, portfolioId: 'portfolio-01' }),
      }),
      screens.portfolioDetail,
      locale,
    );
    const positionProps = expectLocalizedScreen(
      await PositionDetailPage({
        params: Promise.resolve({
          locale,
          portfolioId: 'portfolio-01',
          positionId: 'position-01',
        }),
      }),
      screens.positionDetail,
      locale,
    );

    expect(catalogProps.initialPage).toEqual({ items: ['portfolio-summary'] });
    expect(detailProps.portfolio).toBe('portfolio-summary');
    expect(detailProps.initialPositions).toBe('portfolio-positions');
    expect(detailProps.initialTimeline).toBe('portfolio-timeline');
    expect(detailProps.analytics).toBe('portfolio-analytics');
    expect(positionProps.report).toBe('position-report');
    expect(api.getSimulatedPositionDetail).toHaveBeenCalledWith('portfolio-01', 'position-01');
  });

  it('loads data connections and operational monitoring', async () => {
    const connectionProps = expectLocalizedScreen(
      await ConnectionsPage({ params: Promise.resolve({ locale }) }),
      screens.connections,
      locale,
    );
    const monitoringProps = expectLocalizedScreen(
      await MonitoringPage({ params: Promise.resolve({ locale }) }),
      screens.monitoring,
      locale,
    );

    expect(connectionProps.initialProviders).toBe('market-data-providers');
    expect(connectionProps.initialPage).toBe('connection-page');
    expect(monitoringProps.summary).toBe('monitoring-summary');
  });
});
