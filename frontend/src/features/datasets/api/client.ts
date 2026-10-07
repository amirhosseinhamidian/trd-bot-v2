import { getJson, postFormData, postJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/types';

import type {
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
  OHLCVCandle,
} from '@/features/datasets/api/types';

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

function datasetFileForm(file: File, request?: object): FormData {
  const form = new FormData();

  form.append('file', file);
  if (request) {
    form.append('request', JSON.stringify(request));
  }
  return form;
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
