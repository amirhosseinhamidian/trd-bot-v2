import type { PortfolioAnalyticsReport } from '@/lib/api/portfolio-analytics';
import { getJson, postJson } from '@/lib/api/core/transport';
import type {
  BackgroundJobSummary,
  CandidateComparisonResult,
  CandidateJournalOccurrence,
  CandidateProjectionDetail,
  CandidateProjectionSummary,
  MonitoringSummary,
  Page,
  PositionDetailReport,
  PortfolioTimelineEvent,
  ResearchActivityItem,
  ResearchActivityType,
  ResearchOverview,
  RiskDashboardReport,
  SimulatedPortfolio,
  SimulatedPortfolioSummary,
  SimulatedPosition,
} from '@/lib/api/types';

export { API_BASE_URL, ApiRequestError } from '@/lib/api/core/transport';
export {
  createDataset,
  getDataset,
  getDatasetCandles,
  getDatasets,
  getDatasetSummary,
  importDatasetFile,
  inspectDatasetFile,
  previewDatasetFile,
  type DatasetCandleFilters,
  type DatasetFilters,
} from '@/features/datasets/api/client';
export {
  createMarketDataConnection,
  disableMarketDataConnection,
  enableMarketDataConnection,
  enqueueHistoricalDatasetImport,
  enqueueMarketDataImportRefresh,
  getMarketDataConnections,
  getMarketDataImport,
  getMarketDataImportHistory,
  getMarketDataImportVersions,
  getMarketDataProviders,
  importHistoricalDataset,
  previewHistoricalDatasetImport,
  refreshMarketDataImport,
  testMarketDataConnection,
  type MarketDataConnectionFilters,
  type MarketDataImportHistoryFilters,
  type MarketDataImportVersionFilters,
} from '@/features/connections/api/client';
export {
  getResearchStrategies,
  getResearchStrategyVersion,
  getResearchStrategyVersions,
} from '@/features/strategies/api/client';
export {
  compareExperiments,
  createEmaCrossoverExperimentFromDataset,
  createExperimentExecution,
  getAcceptancePolicyPresets,
  getExperimentAnalytics,
  getExperimentExecution,
  getExperimentPerformanceSeries,
  getExperimentReportByPreset,
  getExperimentReportCsv,
  getExperiments,
  getExperimentSummary,
  verifyExperimentReplay,
  type ExperimentFilters,
} from '@/features/experiments/api/client';
export {
  createWalkForwardExecution,
  getWalkForwardExecution,
  getWalkForwardRuns,
  getWalkForwardRunSummary,
  getWalkForwardStabilityReport,
  type WalkForwardRunFilters,
} from '@/features/walk-forward/api/client';
export {
  createOptimizationExecution,
  getOptimizationExecution,
  getOptimizationExecutions,
  type OptimizationExecutionFilters,
} from '@/features/optimizations/api/client';
export {
  getExperimentSignal,
  getExperimentSignals,
  type ExperimentSignalFilters,
} from '@/features/signals/api/client';

export interface ResearchActivityFilters {
  activityType?: ResearchActivityType;
  fromTime?: string;
  toTime?: string;
  limit?: number;
  offset?: number;
}

export async function getResearchOverview(): Promise<ResearchOverview> {
  return getJson<ResearchOverview>('/api/v1/research/overview');
}

export async function getBackgroundJob(jobId: string): Promise<BackgroundJobSummary> {
  return getJson<BackgroundJobSummary>(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
}

export async function getResearchActivity(
  filters: ResearchActivityFilters = {},
): Promise<Page<ResearchActivityItem>> {
  const params = new URLSearchParams();

  params.set('limit', String(filters.limit ?? 20));
  params.set('offset', String(filters.offset ?? 0));

  if (filters.activityType) {
    params.set('activity_type', filters.activityType);
  }

  if (filters.fromTime) {
    params.set('from_time', filters.fromTime);
  }

  if (filters.toTime) {
    params.set('to_time', filters.toTime);
  }

  return getJson<Page<ResearchActivityItem>>(
    `/api/v1/research/overview/activity?${params.toString()}`,
  );
}

export async function getMonitoringSummary(): Promise<MonitoringSummary> {
  return getJson<MonitoringSummary>('/api/v1/monitoring/summary');
}

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

export interface CandidateProjectionFilters {
  limit?: number;
  offset?: number;
}

export async function getCandidateProjections(
  filters: CandidateProjectionFilters = {},
): Promise<Page<CandidateProjectionSummary>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<CandidateProjectionSummary>>(
    `/api/v1/research/candidates?${params.toString()}`,
  );
}

export async function compareCandidates(
  candidateIds: string[],
): Promise<CandidateComparisonResult> {
  return postJson<CandidateComparisonResult>('/api/v1/research/candidates/compare', {
    candidate_ids: candidateIds,
  });
}

export async function getCandidateProjection(
  candidateId: string,
): Promise<CandidateProjectionDetail> {
  return getJson<CandidateProjectionDetail>(
    `/api/v1/research/candidates/${encodeURIComponent(candidateId)}`,
  );
}

export async function getCandidateLineage(
  candidateId: string,
  filters: CandidateProjectionFilters = {},
): Promise<Page<CandidateJournalOccurrence>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 10));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<CandidateJournalOccurrence>>(
    `/api/v1/research/candidates/${encodeURIComponent(candidateId)}/lineage?${params.toString()}`,
  );
}
