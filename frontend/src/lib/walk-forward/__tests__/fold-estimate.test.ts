import { describe, expect, it } from 'vitest';

import { estimateWalkForwardFoldCount } from '@/lib/walk-forward/fold-estimate';

describe('estimateWalkForwardFoldCount', () => {
  it('matches the backend planner for a rolling configuration', () => {
    expect(
      estimateWalkForwardFoldCount(240, {
        trainCandles: 120,
        testCandles: 24,
        stepCandles: 24,
        gapCandles: 0,
      }),
    ).toBe(5);
  });

  it('uses the same count for expanding windows', () => {
    expect(
      estimateWalkForwardFoldCount(168, {
        trainCandles: 120,
        testCandles: 24,
        stepCandles: 24,
        gapCandles: 0,
      }),
    ).toBe(2);
  });

  it('includes a configured gap in the first fold size', () => {
    expect(
      estimateWalkForwardFoldCount(180, {
        trainCandles: 120,
        testCandles: 20,
        stepCandles: 20,
        gapCandles: 10,
      }),
    ).toBe(2);
  });

  it('returns zero when the dataset cannot contain one full fold', () => {
    expect(
      estimateWalkForwardFoldCount(143, {
        trainCandles: 120,
        testCandles: 24,
        stepCandles: 24,
        gapCandles: 0,
      }),
    ).toBe(0);
  });

  it('rejects overlapping test windows', () => {
    expect(
      estimateWalkForwardFoldCount(240, {
        trainCandles: 120,
        testCandles: 24,
        stepCandles: 12,
        gapCandles: 0,
      }),
    ).toBeNull();
  });

  it.each([
    { trainCandles: 1, testCandles: 24, stepCandles: 24, gapCandles: 0 },
    { trainCandles: 120, testCandles: 0, stepCandles: 24, gapCandles: 0 },
    { trainCandles: 120, testCandles: 24, stepCandles: 24, gapCandles: -1 },
    { trainCandles: 120.5, testCandles: 24, stepCandles: 24, gapCandles: 0 },
  ])('rejects invalid window values: %o', (windows) => {
    expect(estimateWalkForwardFoldCount(240, windows)).toBeNull();
  });
});
