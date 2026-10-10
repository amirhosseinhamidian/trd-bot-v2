import { getBlob, getJson, postJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/core/types';

import type {
  AcceptancePolicyPreset,
  CreatedResearchExperiment,
  ExperimentAnalyticsReport,
  ExperimentComparisonMetric,
  ExperimentComparisonResult,
  ExperimentExecution,
  ExperimentExecutionSubmission,
  ExperimentPerformanceSeries,
  ExperimentReplayVerification,
  ExperimentSortDirection,
  ExperimentSortField,
  ExperimentSummary,
  PresetExperimentResearchReport,
  StoredDatasetEMACrossoverRequest,
  StoredDatasetStrategyExecutionRequest,
} from './types';

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

export async function createExperimentExecution(
  request: StoredDatasetStrategyExecutionRequest,
): Promise<ExperimentExecutionSubmission> {
  return postJson<ExperimentExecutionSubmission>('/api/v1/research/experiment-executions', request);
}

export async function getExperimentExecution(executionId: string): Promise<ExperimentExecution> {
  return getJson<ExperimentExecution>(
    `/api/v1/research/experiment-executions/${encodeURIComponent(executionId)}`,
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

  if (filters.datasetId) params.set('dataset_id', filters.datasetId);
  if (filters.strategyName) params.set('strategy_name', filters.strategyName);
  if (filters.strategyVersion) params.set('strategy_version', filters.strategyVersion);
  if (filters.horizonCandles !== undefined) {
    params.set('horizon_candles', String(filters.horizonCandles));
  }
  if (filters.createdAtFrom) params.set('created_at_from', filters.createdAtFrom);
  if (filters.createdAtTo) params.set('created_at_to', filters.createdAtTo);

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
