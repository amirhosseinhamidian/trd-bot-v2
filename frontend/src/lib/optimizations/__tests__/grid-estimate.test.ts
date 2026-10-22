import { describe, expect, it } from 'vitest';

import type { ResearchStrategyMetadata } from '@/features/strategies/api/types';
import {
  estimateOptimizationGrid,
  isOptimizationGridValueValid,
  splitOptimizationGridValues,
} from '@/lib/optimizations/grid-estimate';

const strategy: ResearchStrategyMetadata = {
  name: 'ema-crossover',
  version: '1.0.0',
  display_name: 'EMA Crossover',
  description: 'test strategy',
  parameters: [
    {
      name: 'fast_period',
      kind: 'integer',
      default_value: '12',
      minimum: '1',
      maximum: '500',
      minimum_exclusive: false,
      maximum_exclusive: false,
    },
    {
      name: 'slow_period',
      kind: 'integer',
      default_value: '26',
      minimum: '2',
      maximum: '1000',
      minimum_exclusive: false,
      maximum_exclusive: false,
    },
  ],
};

describe('optimization grid estimate', () => {
  it('splits English and Persian comma-separated values', () => {
    expect(splitOptimizationGridValues(' 5, 10،20 ,, ')).toEqual(['5', '10', '20']);
  });

  it('counts valid moving-average combinations like the backend planner', () => {
    expect(
      estimateOptimizationGrid(strategy, {
        fast_period: ['10', '20'],
        slow_period: ['15', '30'],
      }),
    ).toEqual({
      requestedCombinations: 4,
      skippedCombinations: 1,
      validTrials: 3,
    });
  });

  it('returns null while a parameter grid is empty', () => {
    expect(
      estimateOptimizationGrid(strategy, {
        fast_period: ['10'],
        slow_period: [],
      }),
    ).toBeNull();
  });

  it('rejects integer spellings that Python int would not parse', () => {
    expect(isOptimizationGridValueValid(strategy, 'fast_period', '2.0')).toBe(false);
    expect(isOptimizationGridValueValid(strategy, 'fast_period', '2e0')).toBe(false);
    expect(isOptimizationGridValueValid(strategy, 'fast_period', '+2')).toBe(true);
  });
});
