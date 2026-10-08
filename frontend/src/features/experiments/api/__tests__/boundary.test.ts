import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
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
} from '@/features/experiments/api/client';
import {
  compareExperiments as compareExperimentsFacade,
  createEmaCrossoverExperimentFromDataset as createEmaCrossoverExperimentFromDatasetFacade,
  createExperimentExecution as createExperimentExecutionFacade,
  getAcceptancePolicyPresets as getAcceptancePolicyPresetsFacade,
  getExperimentAnalytics as getExperimentAnalyticsFacade,
  getExperimentExecution as getExperimentExecutionFacade,
  getExperimentPerformanceSeries as getExperimentPerformanceSeriesFacade,
  getExperimentReportByPreset as getExperimentReportByPresetFacade,
  getExperimentReportCsv as getExperimentReportCsvFacade,
  getExperiments as getExperimentsFacade,
  getExperimentSummary as getExperimentSummaryFacade,
  verifyExperimentReplay as verifyExperimentReplayFacade,
} from '@/lib/api/client';

describe('experiments API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(createExperimentExecutionFacade).toBe(createExperimentExecution);
    expect(getExperimentExecutionFacade).toBe(getExperimentExecution);
    expect(createEmaCrossoverExperimentFromDatasetFacade).toBe(
      createEmaCrossoverExperimentFromDataset,
    );
    expect(getExperimentsFacade).toBe(getExperiments);
    expect(compareExperimentsFacade).toBe(compareExperiments);
    expect(getExperimentSummaryFacade).toBe(getExperimentSummary);
    expect(verifyExperimentReplayFacade).toBe(verifyExperimentReplay);
    expect(getExperimentPerformanceSeriesFacade).toBe(getExperimentPerformanceSeries);
    expect(getExperimentAnalyticsFacade).toBe(getExperimentAnalytics);
    expect(getAcceptancePolicyPresetsFacade).toBe(getAcceptancePolicyPresets);
    expect(getExperimentReportByPresetFacade).toBe(getExperimentReportByPreset);
    expect(getExperimentReportCsvFacade).toBe(getExperimentReportCsv);
  });

  it('keeps experiment and acceptance ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const experimentClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/experiments/api/client.ts'),
      'utf8',
    );
    const experimentTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/experiments/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/experiment-executions');
    expect(clientSource).not.toContain('/api/v1/research/acceptance-policies');
    expect(clientSource).not.toContain('/experiments/${encodedExperimentId}/summary');
    expect(clientSource).not.toContain('/replay-verification');
    expect(clientSource).not.toContain('/performance-series');
    expect(clientSource).not.toContain('/experiments/${encodedExperimentId}/analytics');
    expect(clientSource).not.toContain('/report/presets/');
    expect(clientSource).toContain("from '@/features/experiments/api/client'");
    expect(typesSource).not.toContain('export interface ExperimentSummary');
    expect(typesSource).not.toContain('export interface AcceptancePolicyPreset');
    expect(typesSource).toContain("from '@/features/experiments/api/types'");
    expect(experimentClientSource).not.toContain('@/lib/api/client');
    expect(experimentTypesSource).not.toContain('@/lib/api/types');
  });
});
