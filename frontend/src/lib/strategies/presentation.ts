import type { ExperimentParameter } from '@/lib/api/types';

export type StrategyPresentationLocale = 'fa' | 'en';

const STRATEGY_NAMES: Record<
  StrategyPresentationLocale,
  Record<'ema-crossover' | 'rsi-threshold' | 'sma-crossover', string>
> = {
  fa: {
    'ema-crossover': 'EMA Crossover',
    'rsi-threshold': 'RSI Threshold',
    'sma-crossover': 'SMA Crossover',
  },
  en: {
    'ema-crossover': 'EMA Crossover',
    'rsi-threshold': 'RSI Threshold',
    'sma-crossover': 'SMA Crossover',
  },
};

const PARAMETER_LABELS: Record<StrategyPresentationLocale, Partial<Record<string, string>>> = {
  fa: {
    fast_period: 'دوره میانگین متحرک سریع',
    slow_period: 'دوره میانگین متحرک آهسته',
    period: 'دوره RSI',
    oversold_threshold: 'آستانه اشباع فروش',
    overbought_threshold: 'آستانه اشباع خرید',
    starting_balance: 'موجودی آغازین',
    allocation_fraction: 'سهم تخصیص',
    fee_rate: 'نرخ کارمزد شبیه‌سازی‌شده',
    slippage_rate: 'نرخ لغزش شبیه‌سازی‌شده',
  },
  en: {
    fast_period: 'Fast moving-average period',
    slow_period: 'Slow moving-average period',
    period: 'RSI period',
    oversold_threshold: 'Oversold threshold',
    overbought_threshold: 'Overbought threshold',
    starting_balance: 'Starting balance',
    allocation_fraction: 'Allocation fraction',
    fee_rate: 'Simulated fee rate',
    slippage_rate: 'Simulated slippage rate',
  },
};

export function getStrategyDisplayName(
  strategyName: string,
  locale: StrategyPresentationLocale,
): string {
  if (
    strategyName === 'ema-crossover' ||
    strategyName === 'rsi-threshold' ||
    strategyName === 'sma-crossover'
  ) {
    return STRATEGY_NAMES[locale][strategyName];
  }

  return strategyName;
}

export function getStrategyParameterLabel(
  parameterName: string,
  locale: StrategyPresentationLocale,
): string {
  return PARAMETER_LABELS[locale][parameterName] ?? parameterName;
}

export function formatStrategyParameter(
  parameter: ExperimentParameter,
  locale: StrategyPresentationLocale,
): string {
  return `${getStrategyParameterLabel(parameter.name, locale)}=${parameter.value}`;
}
