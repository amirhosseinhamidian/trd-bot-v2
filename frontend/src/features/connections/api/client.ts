import type { DatasetSummary } from '@/features/datasets/api/types';
import type { BackgroundJobSummary } from '@/features/jobs/api/types';
import { getJson, postJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/core/types';

import type {
  HistoricalDatasetCommitRequest,
  HistoricalDatasetImportPreview,
  HistoricalDatasetImportRequest,
  MarketDataConnection,
  MarketDataConnectionCreateRequest,
  MarketDataImportRecord,
  MarketDataImportStatus,
  MarketDataProviderSummary,
} from './types';

export interface MarketDataConnectionFilters {
  limit?: number;
  offset?: number;
}

export interface MarketDataImportHistoryFilters {
  status?: MarketDataImportStatus;
  limit?: number;
  offset?: number;
}

export interface MarketDataImportVersionFilters {
  limit?: number;
  offset?: number;
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
