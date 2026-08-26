import type {
  AcceptancePolicyPreset,
  DatasetImportRequest,
  DatasetSnapshot,
  DatasetSortDirection,
  DatasetSortField,
  DatasetSummary,
  DatasetTimeframe,
  ExperimentSortDirection,
  ExperimentSortField,
  ExperimentSummary,
  ExperimentComparisonMetric,
  ExperimentComparisonResult,
  ExperimentPerformanceSeries,
  MonitoringSummary,
  OHLCVCandle,
  Page,
  PortfolioTimelineEvent,
  PresetExperimentResearchReport,
  ResearchActivityItem,
  ResearchActivityType,
  ResearchOverview,
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
  StoredDatasetEMACrossoverWalkForwardRequest,
  WalkForwardExecution,
} from '@/lib/api/types';

const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

export const API_BASE_URL = configuredApiBaseUrl.replace(/\/+$/, '');

export class ApiRequestError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);

    this.name = 'ApiRequestError';
    this.status = status;
    this.payload = payload;
  }
}

async function parseErrorPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);

    throw new ApiRequestError(
      `API request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return response.json() as Promise<T>;
}

async function getBlob(path: string, accept: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    headers: {
      Accept: accept,
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);

    throw new ApiRequestError(
      `API request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return response.blob();
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const hasBody = body !== undefined;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      ...(hasBody
        ? {
            'Content-Type': 'application/json',
          }
        : {}),
    },
    body: hasBody ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);

    throw new ApiRequestError(
      `API request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return response.json() as Promise<T>;
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

export async function getDatasetSummary(datasetId: string): Promise<DatasetSummary> {
  return getJson<DatasetSummary>(
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

export async function createEmaCrossoverExperimentExecution(
  request: StoredDatasetEMACrossoverRequest,
): Promise<ExperimentExecution> {
  return postJson<ExperimentExecution>(
    '/api/v1/research/experiment-executions/ema-crossover',
    request,
  );
}

export async function getExperimentExecution(executionId: string): Promise<ExperimentExecution> {
  return getJson<ExperimentExecution>(
    `/api/v1/research/experiment-executions/${encodeURIComponent(executionId)}`,
  );
}

export async function createEmaCrossoverWalkForwardExecution(
  request: StoredDatasetEMACrossoverWalkForwardRequest,
): Promise<WalkForwardExecution> {
  return postJson<WalkForwardExecution>(
    '/api/v1/research/walk-forward-executions/ema-crossover',
    request,
  );
}

export async function getWalkForwardExecution(executionId: string): Promise<WalkForwardExecution> {
  return getJson<WalkForwardExecution>(
    `/api/v1/research/walk-forward-executions/${encodeURIComponent(executionId)}`,
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

export async function getExperimentPerformanceSeries(
  experimentId: string,
): Promise<ExperimentPerformanceSeries> {
  const encodedExperimentId = encodeURIComponent(experimentId);

  return getJson<ExperimentPerformanceSeries>(
    `/api/v1/research/experiments/${encodedExperimentId}/performance-series`,
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
