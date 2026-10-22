import { describe, expect, it } from 'vitest';

import { parseOptimizationExecutionId } from '@/lib/optimizations/run-params';

describe('optimization run parameters', () => {
  it('parses a valid execution ID', () => {
    expect(
      parseOptimizationExecutionId({
        execution: 'optimization-1234567890abcdef',
      }),
    ).toBe('optimization-1234567890abcdef');
  });

  it('uses the first execution ID and ignores invalid values', () => {
    expect(
      parseOptimizationExecutionId({
        execution: ['optimization-fedcba0987654321', 'optimization-1234567890abcdef'],
      }),
    ).toBe('optimization-fedcba0987654321');

    expect(
      parseOptimizationExecutionId({
        execution: 'optimization-1234',
      }),
    ).toBeUndefined();
  });
});
