import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  createOptimizationExecution,
  getOptimizationExecution,
  getOptimizationExecutions,
} from '@/features/optimizations/api/client';
import {
  createOptimizationExecution as createOptimizationExecutionFacade,
  getOptimizationExecution as getOptimizationExecutionFacade,
  getOptimizationExecutions as getOptimizationExecutionsFacade,
} from '@/lib/api/client';

describe('optimizations API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(createOptimizationExecutionFacade).toBe(createOptimizationExecution);
    expect(getOptimizationExecutionFacade).toBe(getOptimizationExecution);
    expect(getOptimizationExecutionsFacade).toBe(getOptimizationExecutions);
  });

  it('keeps optimization ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const optimizationClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/optimizations/api/client.ts'),
      'utf8',
    );
    const optimizationTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/optimizations/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/optimization-executions');
    expect(clientSource).toContain("from '@/features/optimizations/api/client'");
    expect(typesSource).not.toContain('export interface OptimizationExecution');
    expect(typesSource).not.toContain('export interface OptimizationRobustnessPlan');
    expect(typesSource).toContain("from '@/features/optimizations/api/types'");
    expect(optimizationClientSource).not.toContain('@/lib/api/client');
    expect(optimizationTypesSource).not.toContain('@/lib/api/client');
  });
});
