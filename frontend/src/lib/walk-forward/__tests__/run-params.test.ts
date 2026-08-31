import { describe, expect, it } from 'vitest';

import {
  parseWalkForwardExecutionId,
  parseWalkForwardRunSearchParams,
} from '@/lib/walk-forward/run-params';

describe('walk-forward run parameters', () => {
  it('parses an executable strategy preselection', () => {
    expect(
      parseWalkForwardRunSearchParams({
        strategy: 'rsi-threshold',
      }),
    ).toEqual({
      strategyName: 'rsi-threshold',
    });
  });

  it('accepts the first strategy value and ignores unsupported names', () => {
    expect(
      parseWalkForwardRunSearchParams({
        strategy: ['sma-crossover', 'rsi-threshold'],
      }),
    ).toEqual({
      strategyName: 'sma-crossover',
    });

    expect(
      parseWalkForwardRunSearchParams({
        strategy: 'future-strategy',
      }),
    ).toEqual({});
  });

  it('parses a valid walk-forward execution ID', () => {
    expect(
      parseWalkForwardExecutionId({
        execution: 'walk-forward-job-1234567890abcdef',
      }),
    ).toBe('walk-forward-job-1234567890abcdef');
  });

  it('accepts the first execution ID from an array', () => {
    expect(
      parseWalkForwardExecutionId({
        execution: ['walk-forward-job-1234567890abcdef', 'walk-forward-job-fedcba0987654321'],
      }),
    ).toBe('walk-forward-job-1234567890abcdef');
  });

  it.each([
    'invalid-execution',
    'walk-forward-job-1234',
    'walk-forward-job-1234567890ABCDEF',
    'walk-forward-execution-1234567890abcdef',
  ])('ignores invalid execution ID %s', (execution) => {
    expect(
      parseWalkForwardExecutionId({
        execution,
      }),
    ).toBeUndefined();
  });

  it('ignores empty values', () => {
    expect(
      parseWalkForwardExecutionId({
        execution: '   ',
      }),
    ).toBeUndefined();
  });
});
