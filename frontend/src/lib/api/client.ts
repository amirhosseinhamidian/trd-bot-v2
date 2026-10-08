import type { PortfolioAnalyticsReport } from '@/lib/api/portfolio-analytics';
import { getJson, postJson } from '@/lib/api/core/transport';
import type {
  BackgroundJobSummary,
  CandidateComparisonResult,
  CandidateJournalOccurrence,
  CandidateProjectionDetail,
  CandidateProjectionSummary,
  MonitoringSummary,
  OptimizationExecution,
  OptimizationExecutionSubmission,
  CreateOptimizationExecutionRequest,
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
  WalkForwardRunSortDirection,
  WalkForwardRunSortField,
  WalkForwardRunSummary,
  WalkForwardStabilityReport,
  ExperimentSignalSortDirection,
  SignalDirection,
  StrategySignal,
  StoredDatasetStrategyWalkForwardExecutionRequest,
  WalkForwardExecution,
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

export interface WalkForwardRunFilters {
  sourceDatasetId?: string;
  planId?: string;
  strategyName?: string;
  strategyVersion?: string;
  horizonCandles?: number;
  createdAtFrom?: string;
  createdAtTo?: string;
  sortBy?: WalkForwardRunSortField;
  sortDirection?: WalkForwardRunSortDirection;
  limit?: number;
  offset?: number;
}

export interface OptimizationExecutionFilters {
  limit?: number;
  offset?: number;
}

export interface ResearchActivityFilters {
  activityType?: ResearchActivityType;
  fromTime?: string;
  toTime?: string;
  limit?: number;
  offset?: number;
}

export interface ExperimentSignalFilters {
  direction?: SignalDirection;
  candleCloseTimeFrom?: string;
  candleCloseTimeTo?: string;
  sortDirection?: ExperimentSignalSortDirection;
  limit?: number;
  offset?: number;
}

export async function getResearchOverview(): Promise<ResearchOverview> {
  return getJson<ResearchOverview>('/api/v1/research/overview');
}

export async function getBackgroundJob(jobId: string): Promise<BackgroundJobSummary> {
  return getJson<BackgroundJobSummary>(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
}

export async function createWalkForwardExecution(
  request: StoredDatasetStrategyWalkForwardExecutionRequest,
): Promise<WalkForwardExecution> {
  return postJson<WalkForwardExecution>('/api/v1/research/walk-forward-executions', request);
}

export async function getWalkForwardExecution(executionId: string): Promise<WalkForwardExecution> {
  return getJson<WalkForwardExecution>(
    `/api/v1/research/walk-forward-executions/${encodeURIComponent(executionId)}`,
  );
}

export async function createOptimizationExecution(
  request: CreateOptimizationExecutionRequest,
): Promise<OptimizationExecutionSubmission> {
  return postJson<OptimizationExecutionSubmission>(
    '/api/v1/research/optimization-executions',
    request,
  );
}

export async function getOptimizationExecutions(
  filters: OptimizationExecutionFilters = {},
): Promise<Page<OptimizationExecution>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<OptimizationExecution>>(
    `/api/v1/research/optimization-executions?${params.toString()}`,
  );
}

export async function getOptimizationExecution(
  executionId: string,
): Promise<OptimizationExecution> {
  return getJson<OptimizationExecution>(
    `/api/v1/research/optimization-executions/${encodeURIComponent(executionId)}`,
  );
}

export async function getWalkForwardRuns(
  filters: WalkForwardRunFilters = {},
): Promise<Page<WalkForwardRunSummary>> {
  const params = new URLSearchParams();

  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));
  params.set('sort_by', filters.sortBy ?? 'created_at');
  params.set('sort_direction', filters.sortDirection ?? 'desc');

  if (filters.sourceDatasetId) {
    params.set('source_dataset_id', filters.sourceDatasetId);
  }

  if (filters.planId) {
    params.set('plan_id', filters.planId);
  }

  if (filters.strategyName) {
    params.set('strategy_name', filters.strategyName);
  }

  if (filters.strategyVersion) {
    params.set('strategy_version', filters.strategyVersion);
  }

  if (filters.horizonCandles !== undefined) {
    params.set('horizon_candles', String(filters.horizonCandles));
  }

  if (filters.createdAtFrom) {
    params.set('created_at_from', filters.createdAtFrom);
  }

  if (filters.createdAtTo) {
    params.set('created_at_to', filters.createdAtTo);
  }

  return getJson<Page<WalkForwardRunSummary>>(
    `/api/v1/research/walk-forward/runs?${params.toString()}`,
  );
}

export async function getWalkForwardRunSummary(
  executionId: string,
): Promise<WalkForwardRunSummary> {
  const encodedExecutionId = encodeURIComponent(executionId);

  return getJson<WalkForwardRunSummary>(
    `/api/v1/research/walk-forward/runs/${encodedExecutionId}/summary`,
  );
}

export async function getWalkForwardStabilityReport(
  executionId: string,
): Promise<WalkForwardStabilityReport> {
  const encodedExecutionId = encodeURIComponent(executionId);

  return getJson<WalkForwardStabilityReport>(
    `/api/v1/research/walk-forward/runs/${encodedExecutionId}/stability`,
  );
}

export async function getExperimentSignals(
  experimentId: string,
  filters: ExperimentSignalFilters = {},
): Promise<Page<StrategySignal>> {
  const encodedExperimentId = encodeURIComponent(experimentId);
  const params = new URLSearchParams();

  params.set('limit', String(filters.limit ?? 20));
  params.set('offset', String(filters.offset ?? 0));
  params.set('sort_direction', filters.sortDirection ?? 'desc');

  if (filters.direction) {
    params.set('direction', filters.direction);
  }

  if (filters.candleCloseTimeFrom) {
    params.set('candle_close_time_from', filters.candleCloseTimeFrom);
  }

  if (filters.candleCloseTimeTo) {
    params.set('candle_close_time_to', filters.candleCloseTimeTo);
  }

  return getJson<Page<StrategySignal>>(
    `/api/v1/research/experiments/${encodedExperimentId}/signals?${params.toString()}`,
  );
}

export async function getExperimentSignal(
  experimentId: string,
  signalId: string,
): Promise<StrategySignal> {
  const encodedExperimentId = encodeURIComponent(experimentId);
  const encodedSignalId = encodeURIComponent(signalId);

  return getJson<StrategySignal>(
    `/api/v1/research/experiments/${encodedExperimentId}/signals/${encodedSignalId}`,
  );
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
