import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  createWalkForwardExecution,
  getWalkForwardExecution,
  getWalkForwardRuns,
  getWalkForwardRunSummary,
  getWalkForwardStabilityReport,
} from '@/features/walk-forward/api/client';
import {
  createWalkForwardExecution as createWalkForwardExecutionFacade,
  getWalkForwardExecution as getWalkForwardExecutionFacade,
  getWalkForwardRuns as getWalkForwardRunsFacade,
  getWalkForwardRunSummary as getWalkForwardRunSummaryFacade,
  getWalkForwardStabilityReport as getWalkForwardStabilityReportFacade,
} from '@/lib/api/client';

describe('walk-forward API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(createWalkForwardExecutionFacade).toBe(createWalkForwardExecution);
    expect(getWalkForwardExecutionFacade).toBe(getWalkForwardExecution);
    expect(getWalkForwardRunsFacade).toBe(getWalkForwardRuns);
    expect(getWalkForwardRunSummaryFacade).toBe(getWalkForwardRunSummary);
    expect(getWalkForwardStabilityReportFacade).toBe(getWalkForwardStabilityReport);
  });

  it('keeps walk-forward ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const walkForwardClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/walk-forward/api/client.ts'),
      'utf8',
    );
    const walkForwardTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/walk-forward/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/walk-forward-executions');
    expect(clientSource).not.toContain('/api/v1/research/walk-forward/runs');
    expect(clientSource).toContain("from '@/features/walk-forward/api/client'");
    expect(typesSource).not.toContain('export interface WalkForwardExecution');
    expect(typesSource).not.toContain('export interface WalkForwardRunSummary');
    expect(typesSource).toContain("from '@/features/walk-forward/api/types'");
    expect(walkForwardClientSource).not.toContain('@/lib/api/client');
    expect(walkForwardTypesSource).not.toContain('@/lib/api/types');
  });
});
