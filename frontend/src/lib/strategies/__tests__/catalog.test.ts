import { describe, expect, it } from 'vitest';

import type { ResearchStrategyMetadata } from '@/lib/api/types';
import {
  findStrategyMetadata,
  findStrategyParameterMetadata,
  getStrategyParameterDefault,
  isExecutableResearchStrategyName,
} from '@/lib/strategies/catalog';

const catalog: ResearchStrategyMetadata[] = [
  {
    name: 'ema-crossover',
    version: '1.0.0',
    display_name: 'EMA Crossover',
    description: 'Historical EMA research strategy.',
    parameters: [
      {
        name: 'fast_period',
        kind: 'integer',
        default_value: '9',
        minimum: '2',
        maximum: null,
        minimum_exclusive: false,
        maximum_exclusive: false,
      },
      {
        name: 'slow_period',
        kind: 'integer',
        default_value: '21',
        minimum: '3',
        maximum: null,
        minimum_exclusive: false,
        maximum_exclusive: false,
      },
    ],
  },
  {
    name: 'rsi-threshold',
    version: '1.0.0',
    display_name: 'RSI Threshold',
    description: 'Historical RSI research strategy.',
    parameters: [
      {
        name: 'period',
        kind: 'integer',
        default_value: '14',
        minimum: '2',
        maximum: null,
        minimum_exclusive: false,
        maximum_exclusive: false,
      },
    ],
  },
];

describe('strategy catalog helpers', () => {
  it('resolves versioned strategy and parameter metadata', () => {
    const strategy = findStrategyMetadata(catalog, 'ema-crossover', '1.0.0');

    expect(strategy?.display_name).toBe('EMA Crossover');
    expect(strategy ? findStrategyParameterMetadata(strategy, 'slow_period')?.minimum : null).toBe(
      '3',
    );
    expect(strategy ? getStrategyParameterDefault(strategy, 'fast_period') : null).toBe('9');
  });

  it('does not claim unknown catalog strategies are executable yet', () => {
    expect(isExecutableResearchStrategyName('ema-crossover')).toBe(true);
    expect(isExecutableResearchStrategyName('rsi-threshold')).toBe(true);
    expect(isExecutableResearchStrategyName('future-strategy')).toBe(false);
  });

  it('returns null for missing metadata instead of inventing defaults', () => {
    const strategy = findStrategyMetadata(catalog, 'rsi-threshold');

    expect(strategy).not.toBeNull();
    expect(
      strategy ? getStrategyParameterDefault(strategy, 'missing_parameter') : 'unexpected',
    ).toBeNull();
  });
});
