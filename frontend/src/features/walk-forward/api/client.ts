import { getJson, postJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/types';

import type {
  StoredDatasetStrategyWalkForwardExecutionRequest,
  WalkForwardExecution,
  WalkForwardRunSortDirection,
  WalkForwardRunSortField,
  WalkForwardRunSummary,
  WalkForwardStabilityReport,
} from './types';

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

export async function getWalkForwardRuns(
  filters: WalkForwardRunFilters = {},
): Promise<Page<WalkForwardRunSummary>> {
  const params = new URLSearchParams();

  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));
  params.set('sort_by', filters.sortBy ?? 'created_at');
  params.set('sort_direction', filters.sortDirection ?? 'desc');

  if (filters.sourceDatasetId) params.set('source_dataset_id', filters.sourceDatasetId);
  if (filters.planId) params.set('plan_id', filters.planId);
  if (filters.strategyName) params.set('strategy_name', filters.strategyName);
  if (filters.strategyVersion) params.set('strategy_version', filters.strategyVersion);
  if (filters.horizonCandles !== undefined) {
    params.set('horizon_candles', String(filters.horizonCandles));
  }
  if (filters.createdAtFrom) params.set('created_at_from', filters.createdAtFrom);
  if (filters.createdAtTo) params.set('created_at_to', filters.createdAtTo);

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
