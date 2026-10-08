import { getJson } from '@/lib/api/core/transport';
import type {
  BackgroundJobSummary,
  MonitoringSummary,
  Page,
  ResearchActivityItem,
  ResearchActivityType,
  ResearchOverview,
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
export {
  compareCandidates,
  getCandidateLineage,
  getCandidateProjection,
  getCandidateProjections,
  type CandidateProjectionFilters,
} from '@/features/candidates/api/client';
export { getRiskDashboard, type RiskDashboardFilters } from '@/features/risk/api/client';
export {
  getPortfolioAnalytics,
  getSimulatedPortfolio,
  getSimulatedPortfolioPositions,
  getSimulatedPortfolios,
  getSimulatedPortfolioTimeline,
  getSimulatedPosition,
  getSimulatedPositionDetail,
  type SimulatedPortfolioFilters,
  type SimulatedPortfolioResourceFilters,
} from '@/features/portfolios/api/client';

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
