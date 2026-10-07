import type { PortfolioAnalyticsReport } from '@/lib/api/portfolio-analytics';
import { getBlob, getJson, postFormData, postJson } from '@/lib/api/transport';
import type {
  AcceptancePolicyPreset,
  BackgroundJobSummary,
  CandidateComparisonResult,
  CandidateJournalOccurrence,
  CandidateProjectionDetail,
  CandidateProjectionSummary,
  DatasetDetailSummary,
  DatasetFileCommitRequest,
  DatasetFileImportPreview,
  DatasetFileInspection,
  DatasetFilePreviewRequest,
  DatasetImportRequest,
  DatasetSnapshot,
  DatasetSortDirection,
  DatasetSortField,
  DatasetSummary,
  DatasetTimeframe,
  ExperimentAnalyticsReport,
  ExperimentComparisonMetric,
  ExperimentComparisonResult,
  ExperimentSortDirection,
  ExperimentSortField,
  ExperimentSummary,
  ExperimentPerformanceSeries,
  ExperimentReplayVerification,
  HistoricalDatasetCommitRequest,
  HistoricalDatasetImportPreview,
  HistoricalDatasetImportRequest,
  MarketDataConnection,
  MarketDataConnectionCreateRequest,
  MarketDataImportRecord,
  MarketDataImportStatus,
  MarketDataProviderSummary,
  MonitoringSummary,
  OHLCVCandle,
  OptimizationExecution,
  OptimizationExecutionSubmission,
  CreateOptimizationExecutionRequest,
  Page,
  PositionDetailReport,
  PortfolioTimelineEvent,
  PresetExperimentResearchReport,
  ResearchActivityItem,
  ResearchActivityType,
  ResearchOverview,
  ResearchStrategyMetadata,
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
  CreatedResearchExperiment,
  StoredDatasetEMACrossoverRequest,
  ExperimentExecution,
  StoredDatasetStrategyExecutionRequest,
  StoredDatasetStrategyWalkForwardExecutionRequest,
  WalkForwardExecution,
} from '@/lib/api/types';

export { API_BASE_URL, ApiRequestError } from '@/lib/api/transport';

function datasetFileForm(file: File, request?: object): FormData {
  const form = new FormData();

  form.append('file', file);
  if (request) {
    form.append('request', JSON.stringify(request));
  }
  return form;
}

export interface DatasetFilters {
  source?: string;
  baseAsset?: string;
  quoteAsset?: string;
  timeframe?: DatasetTimeframe;
  createdAtFrom?: string;
  createdAtTo?: string;
  sortBy?: DatasetSortField;
  sortDirection?: DatasetSortDirection;
  limit?: number;
  offset?: number;
}

export interface DatasetCandleFilters {
  limit?: number;
  offset?: number;
}

export interface ExperimentFilters {
  datasetId?: string;
  strategyName?: string;
  strategyVersion?: string;
  horizonCandles?: number;
  createdAtFrom?: string;
  createdAtTo?: string;
  sortBy?: ExperimentSortField;
  sortDirection?: ExperimentSortDirection;
  limit?: number;
  offset?: number;
}

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

export interface MarketDataConnectionFilters {
  limit?: number;
  offset?: number;
}

export async function getResearchOverview(): Promise<ResearchOverview> {
  return getJson<ResearchOverview>('/api/v1/research/overview');
}

export async function getDatasets(filters: DatasetFilters = {}): Promise<Page<DatasetSummary>> {
  const params = new URLSearchParams();

  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));
  params.set('sort_by', filters.sortBy ?? 'created_at');
  params.set('sort_direction', filters.sortDirection ?? 'desc');

  if (filters.source) {
    params.set('source', filters.source);
  }

  if (filters.baseAsset) {
    params.set('base_asset', filters.baseAsset);
  }

  if (filters.quoteAsset) {
    params.set('quote_asset', filters.quoteAsset);
  }

  if (filters.timeframe) {
    params.set('timeframe', filters.timeframe);
  }

  if (filters.createdAtFrom) {
    params.set('created_at_from', filters.createdAtFrom);
  }

  if (filters.createdAtTo) {
    params.set('created_at_to', filters.createdAtTo);
  }

  return getJson<Page<DatasetSummary>>(`/api/v1/research/datasets?${params.toString()}`);
}

export async function createDataset(request: DatasetImportRequest): Promise<DatasetSummary> {
  return postJson<DatasetSummary>('/api/v1/research/datasets', request);
}

export async function inspectDatasetFile(file: File): Promise<DatasetFileInspection> {
  return postFormData<DatasetFileInspection>(
    '/api/v1/research/datasets/files/inspect',
    datasetFileForm(file),
  );
}

export async function previewDatasetFile(
  file: File,
  request: DatasetFilePreviewRequest,
): Promise<DatasetFileImportPreview> {
  return postFormData<DatasetFileImportPreview>(
    '/api/v1/research/datasets/files/preview',
    datasetFileForm(file, request),
  );
}

export async function importDatasetFile(
  file: File,
  request: DatasetFileCommitRequest,
): Promise<DatasetSummary> {
  return postFormData<DatasetSummary>(
    '/api/v1/research/datasets/files',
    datasetFileForm(file, request),
  );
}

export async function getDatasetSummary(datasetId: string): Promise<DatasetDetailSummary> {
  return getJson<DatasetDetailSummary>(
    `/api/v1/research/datasets/${encodeURIComponent(datasetId)}/summary`,
  );
}

export async function getDatasetCandles(
  datasetId: string,
  filters: DatasetCandleFilters = {},
): Promise<Page<OHLCVCandle>> {
  const params = new URLSearchParams();

  params.set('limit', String(filters.limit ?? 25));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<OHLCVCandle>>(
    `/api/v1/research/datasets/${encodeURIComponent(datasetId)}/candles?${params.toString()}`,
  );
}

export async function getDataset(datasetId: string): Promise<DatasetSnapshot> {
  return getJson<DatasetSnapshot>(`/api/v1/research/datasets/${encodeURIComponent(datasetId)}`);
}

export async function getResearchStrategies(): Promise<ResearchStrategyMetadata[]> {
  return getJson<ResearchStrategyMetadata[]>('/api/v1/research/strategies');
}

export async function getResearchStrategyVersion(
  strategyName: string,
  version: string,
): Promise<ResearchStrategyMetadata> {
  return getJson<ResearchStrategyMetadata>(
    `/api/v1/research/strategies/${encodeURIComponent(strategyName)}/versions/${encodeURIComponent(version)}`,
  );
}

export async function getResearchStrategyVersions(
  strategyName: string,
): Promise<ResearchStrategyMetadata[]> {
  return getJson<ResearchStrategyMetadata[]>(
    `/api/v1/research/strategies/${encodeURIComponent(strategyName)}/versions`,
  );
}

export async function getMarketDataProviders(): Promise<MarketDataProviderSummary[]> {
  return getJson<MarketDataProviderSummary[]>('/api/v1/market-data/providers');
}

export async function getMarketDataConnections(
  filters: MarketDataConnectionFilters = {},
): Promise<Page<MarketDataConnection>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<MarketDataConnection>>(
    `/api/v1/market-data/connections?${params.toString()}`,
  );
}

export async function createMarketDataConnection(
  request: MarketDataConnectionCreateRequest,
): Promise<MarketDataConnection> {
  return postJson<MarketDataConnection>('/api/v1/market-data/connections', request);
}

export async function testMarketDataConnection(
  connectionId: string,
): Promise<MarketDataConnection> {
  return postJson<MarketDataConnection>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/test`,
  );
}

export async function enableMarketDataConnection(
  connectionId: string,
): Promise<MarketDataConnection> {
  return postJson<MarketDataConnection>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/enable`,
  );
}

export async function disableMarketDataConnection(
  connectionId: string,
): Promise<MarketDataConnection> {
  return postJson<MarketDataConnection>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/disable`,
  );
}

export async function previewHistoricalDatasetImport(
  connectionId: string,
  request: HistoricalDatasetImportRequest,
): Promise<HistoricalDatasetImportPreview> {
  return postJson<HistoricalDatasetImportPreview>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/datasets/preview`,
    request,
  );
}

export async function importHistoricalDataset(
  connectionId: string,
  request: HistoricalDatasetCommitRequest,
): Promise<DatasetSummary> {
  return postJson<DatasetSummary>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/datasets`,
    request,
  );
}

export async function enqueueHistoricalDatasetImport(
  connectionId: string,
  request: HistoricalDatasetCommitRequest,
): Promise<BackgroundJobSummary> {
  return postJson<BackgroundJobSummary>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/dataset-jobs`,
    request,
  );
}

export async function getBackgroundJob(jobId: string): Promise<BackgroundJobSummary> {
  return getJson<BackgroundJobSummary>(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
}

export interface MarketDataImportHistoryFilters {
  status?: MarketDataImportStatus;
  limit?: number;
  offset?: number;
}

export async function getMarketDataImportHistory(
  connectionId: string,
  filters: MarketDataImportHistoryFilters = {},
): Promise<Page<MarketDataImportRecord>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 5));
  params.set('offset', String(filters.offset ?? 0));

  if (filters.status) {
    params.set('status', filters.status);
  }

  return getJson<Page<MarketDataImportRecord>>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/imports?${params.toString()}`,
  );
}

export async function getMarketDataImport(
  connectionId: string,
  importId: string,
): Promise<MarketDataImportRecord> {
  return getJson<MarketDataImportRecord>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/imports/${encodeURIComponent(importId)}`,
  );
}

export interface MarketDataImportVersionFilters {
  limit?: number;
  offset?: number;
}

export async function getMarketDataImportVersions(
  connectionId: string,
  importId: string,
  filters: MarketDataImportVersionFilters = {},
): Promise<Page<MarketDataImportRecord>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 5));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<MarketDataImportRecord>>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/imports/${encodeURIComponent(importId)}/versions?${params.toString()}`,
  );
}

export async function refreshMarketDataImport(
  connectionId: string,
  importId: string,
): Promise<MarketDataImportRecord> {
  return postJson<MarketDataImportRecord>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/imports/${encodeURIComponent(importId)}/refresh`,
  );
}

export async function enqueueMarketDataImportRefresh(
  connectionId: string,
  importId: string,
): Promise<BackgroundJobSummary> {
  return postJson<BackgroundJobSummary>(
    `/api/v1/market-data/connections/${encodeURIComponent(connectionId)}/imports/${encodeURIComponent(importId)}/refresh-job`,
  );
}

export async function createExperimentExecution(
  request: StoredDatasetStrategyExecutionRequest,
): Promise<ExperimentExecution> {
  return postJson<ExperimentExecution>('/api/v1/research/experiment-executions', request);
}

export async function getExperimentExecution(executionId: string): Promise<ExperimentExecution> {
  return getJson<ExperimentExecution>(
    `/api/v1/research/experiment-executions/${encodeURIComponent(executionId)}`,
  );
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

export async function createEmaCrossoverExperimentFromDataset(
  request: StoredDatasetEMACrossoverRequest,
): Promise<CreatedResearchExperiment> {
  return postJson<CreatedResearchExperiment>(
    '/api/v1/research/experiments/ema-crossover/from-dataset',
    request,
  );
}

export async function getExperiments(
  filters: ExperimentFilters = {},
): Promise<Page<ExperimentSummary>> {
  const params = new URLSearchParams();

  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));
  params.set('sort_by', filters.sortBy ?? 'created_at');
  params.set('sort_direction', filters.sortDirection ?? 'desc');

  if (filters.datasetId) {
    params.set('dataset_id', filters.datasetId);
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

  return getJson<Page<ExperimentSummary>>(`/api/v1/research/experiments?${params.toString()}`);
}

export async function compareExperiments(
  experimentIds: string[],
  metric: ExperimentComparisonMetric,
): Promise<ExperimentComparisonResult> {
  return postJson<ExperimentComparisonResult>('/api/v1/research/experiments/compare', {
    experiment_ids: experimentIds,
    metric,
  });
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

export async function getExperimentSummary(experimentId: string): Promise<ExperimentSummary> {
  const encodedExperimentId = encodeURIComponent(experimentId);

  return getJson<ExperimentSummary>(`/api/v1/research/experiments/${encodedExperimentId}/summary`);
}

export async function verifyExperimentReplay(
  experimentId: string,
): Promise<ExperimentReplayVerification> {
  return postJson<ExperimentReplayVerification>(
    `/api/v1/research/experiments/${encodeURIComponent(experimentId)}/replay-verification`,
  );
}

export async function getExperimentPerformanceSeries(
  experimentId: string,
): Promise<ExperimentPerformanceSeries> {
  const encodedExperimentId = encodeURIComponent(experimentId);

  return getJson<ExperimentPerformanceSeries>(
    `/api/v1/research/experiments/${encodedExperimentId}/performance-series`,
  );
}

export async function getExperimentAnalytics(
  experimentId: string,
): Promise<ExperimentAnalyticsReport> {
  const encodedExperimentId = encodeURIComponent(experimentId);

  return getJson<ExperimentAnalyticsReport>(
    `/api/v1/research/experiments/${encodedExperimentId}/analytics`,
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

export async function getAcceptancePolicyPresets(): Promise<AcceptancePolicyPreset[]> {
  return getJson<AcceptancePolicyPreset[]>('/api/v1/research/acceptance-policies');
}

export async function getExperimentReportByPreset(
  experimentId: string,
  presetId: string,
): Promise<PresetExperimentResearchReport> {
  const encodedExperimentId = encodeURIComponent(experimentId);
  const encodedPresetId = encodeURIComponent(presetId);

  return postJson<PresetExperimentResearchReport>(
    `/api/v1/research/experiments/${encodedExperimentId}/report/presets/${encodedPresetId}`,
  );
}

export async function getExperimentReportCsv(
  experimentId: string,
  presetId: string,
): Promise<Blob> {
  const encodedExperimentId = encodeURIComponent(experimentId);
  const encodedPresetId = encodeURIComponent(presetId);

  return getBlob(
    `/api/v1/research/experiments/${encodedExperimentId}/report/presets/${encodedPresetId}/export.csv`,
    'text/csv',
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
