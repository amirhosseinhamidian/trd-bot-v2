import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  createDataset as createDatasetFacade,
  getDataset as getDatasetFacade,
  getDatasetCandles as getDatasetCandlesFacade,
  getDatasets as getDatasetsFacade,
  getDatasetSummary as getDatasetSummaryFacade,
  importDatasetFile as importDatasetFileFacade,
  inspectDatasetFile as inspectDatasetFileFacade,
  previewDatasetFile as previewDatasetFileFacade,
} from '@/lib/api/client';
import {
  createDataset,
  getDataset,
  getDatasetCandles,
  getDatasets,
  getDatasetSummary,
  importDatasetFile,
  inspectDatasetFile,
  previewDatasetFile,
} from '@/features/datasets/api/client';

describe('datasets API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getDatasetsFacade).toBe(getDatasets);
    expect(createDatasetFacade).toBe(createDataset);
    expect(inspectDatasetFileFacade).toBe(inspectDatasetFile);
    expect(previewDatasetFileFacade).toBe(previewDatasetFile);
    expect(importDatasetFileFacade).toBe(importDatasetFile);
    expect(getDatasetSummaryFacade).toBe(getDatasetSummary);
    expect(getDatasetCandlesFacade).toBe(getDatasetCandles);
    expect(getDatasetFacade).toBe(getDataset);
  });

  it('keeps dataset endpoints and type definitions outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const datasetClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/datasets/api/client.ts'),
      'utf8',
    );
    const datasetTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/datasets/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/datasets');
    expect(clientSource).toContain("from '@/features/datasets/api/client'");
    expect(typesSource).not.toContain('export interface DatasetSummary');
    expect(typesSource).toContain("from '@/features/datasets/api/types'");
    expect(datasetClientSource).not.toContain('@/lib/api/client');
    expect(datasetTypesSource).not.toContain('@/lib/api/types');
  });
});
