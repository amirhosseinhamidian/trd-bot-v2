import { describe, expect, it } from 'vitest';

import {
  formatStrategyParameter,
  getStrategyDisplayName,
  getStrategyParameterLabel,
} from '@/lib/strategies/presentation';

describe('strategy presentation', () => {
  it('presents registered strategy names without exposing implementation slugs as titles', () => {
    expect(getStrategyDisplayName('ema-crossover', 'en')).toBe('EMA Crossover');
    expect(getStrategyDisplayName('rsi-threshold', 'fa')).toBe('RSI Threshold');
  });

  it('localizes EMA and RSI parameter labels', () => {
    expect(getStrategyParameterLabel('fast_period', 'en')).toBe('Fast EMA period');
    expect(getStrategyParameterLabel('period', 'en')).toBe('RSI period');
    expect(getStrategyParameterLabel('oversold_threshold', 'fa')).toBe('آستانه اشباع فروش');
  });

  it('keeps unknown future strategies and parameters readable', () => {
    expect(getStrategyDisplayName('future-strategy', 'en')).toBe('future-strategy');
    expect(getStrategyParameterLabel('future_parameter', 'fa')).toBe('future_parameter');
  });

  it('formats localized parameter labels with persisted values', () => {
    expect(
      formatStrategyParameter(
        {
          name: 'overbought_threshold',
          value: '70',
        },
        'en',
      ),
    ).toBe('Overbought threshold=70');
  });
});
