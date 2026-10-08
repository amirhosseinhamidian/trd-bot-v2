import { getJson, postJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/types';

import type {
  CreateOptimizationExecutionRequest,
  OptimizationExecution,
  OptimizationExecutionSubmission,
} from './types';

export interface OptimizationExecutionFilters {
  limit?: number;
  offset?: number;
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
