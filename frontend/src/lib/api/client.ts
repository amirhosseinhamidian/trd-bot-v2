import type {
  DatasetSnapshot,
  DatasetSortDirection,
  DatasetSortField,
  DatasetSummary,
  DatasetTimeframe,
  ExperimentSortDirection,
  ExperimentSortField,
  ExperimentSummary,
  OHLCVCandle,
  Page,
  ResearchActivityItem,
  ResearchActivityType,
  ResearchOverview,
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

export async function getExperimentSummary(experimentId: string): Promise<ExperimentSummary> {
  const encodedExperimentId = encodeURIComponent(experimentId);

  return getJson<ExperimentSummary>(`/api/v1/research/experiments/${encodedExperimentId}/summary`);
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
