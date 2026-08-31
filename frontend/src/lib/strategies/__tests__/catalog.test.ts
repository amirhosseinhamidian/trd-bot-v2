import { describe, expect, it } from 'vitest';

import type { ResearchStrategyMetadata } from '@/lib/api/types';
import {
  findStrategyMetadata,
  findStrategyParameterMetadata,
  getExecutableResearchStrategies,
  getStrategyParameterDefault,
  getStrategyParameterInputProps,
  isExecutableResearchStrategyName,
  isStrategyParameterValueValid,
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
      {
        name: 'oversold_threshold',
        kind: 'decimal',
        default_value: '30',
        minimum: '0',
        maximum: '50',
        minimum_exclusive: true,
        maximum_exclusive: true,
      },
      {
        name: 'overbought_threshold',
        kind: 'decimal',
        default_value: '70',
        minimum: '50',
        maximum: '100',
        minimum_exclusive: true,
        maximum_exclusive: true,
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

  it('filters catalog entries to frontend-executable strategies', () => {
    const result = getExecutableResearchStrategies([
      ...catalog,
      {
        ...catalog[0],
        name: 'sma-crossover',
        display_name: 'SMA Crossover',
        description: 'Historical SMA research strategy.',
      },
      {
        ...catalog[0],
        version: '2.0.0',
      },
      {
        name: 'future-strategy',
        version: '2.0.0',
        display_name: 'Future Strategy',
        description: 'Not executable by this frontend yet.',
        parameters: [],
      },
    ]);

    expect(result.map((strategy) => `${strategy.name}@${strategy.version}`)).toEqual([
      'ema-crossover@1.0.0',
      'rsi-threshold@1.0.0',
      'sma-crossover@1.0.0',
    ]);
    expect(isExecutableResearchStrategyName('sma-crossover')).toBe(true);
    expect(isExecutableResearchStrategyName('future-strategy')).toBe(false);
  });

  it('validates integer and exclusive decimal bounds from metadata', () => {
    const ema = catalog[0];
    const rsi = catalog[1];

    expect(isStrategyParameterValueValid(ema, 'fast_period', '9')).toBe(true);
    expect(isStrategyParameterValueValid(ema, 'fast_period', '2.5')).toBe(false);
    expect(isStrategyParameterValueValid(ema, 'fast_period', '1')).toBe(false);

    expect(isStrategyParameterValueValid(rsi, 'oversold_threshold', '30')).toBe(true);
    expect(isStrategyParameterValueValid(rsi, 'oversold_threshold', '0')).toBe(false);
    expect(isStrategyParameterValueValid(rsi, 'oversold_threshold', '50')).toBe(false);
  });

  it('derives numeric input hints from parameter metadata', () => {
    const rsi = catalog[1];

    expect(getStrategyParameterInputProps(rsi, 'period')).toEqual({
      min: '2',
      step: 1,
    });
    expect(getStrategyParameterInputProps(rsi, 'oversold_threshold')).toEqual({
      min: '0',
      max: '50',
      step: 'any',
    });
  });

  it('returns null for missing metadata instead of inventing defaults', () => {
    const strategy = findStrategyMetadata(catalog, 'rsi-threshold');

    expect(strategy).not.toBeNull();
    expect(
      strategy ? getStrategyParameterDefault(strategy, 'missing_parameter') : 'unexpected',
    ).toBeNull();
  });
});
