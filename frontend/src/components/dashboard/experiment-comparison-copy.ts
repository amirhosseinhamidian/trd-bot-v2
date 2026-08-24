import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type ExperimentComparisonCopy = {
  title: string;
  description: string;
  historicalOnly: string;
  selectExperiment: string;
  incompatibleExperiment: string;
  limitReached: string;
  selectedCount: string;
  selectionHint: string;
  clearSelection: string;
  metricLabel: string;
  compare: string;
  comparing: string;
  insufficientSelection: string;
  error: string;
  retry: string;
  resultTitle: string;
  resultDescription: string;
  firstHistoricalRank: string;
  fields: {
    position: string;
    experiment: string;
    strategy: string;
    parameters: string;
    metricValue: string;
  };
  metrics: {
    excess_return: string;
    total_return: string;
    max_drawdown_fraction: string;
  };
  rankingDirections: {
    higher_is_better: string;
    lower_is_better: string;
  };
};

const copies: Record<DashboardLocale, ExperimentComparisonCopy> = {
  fa: {
    title: 'مقایسه آزمایش‌های تاریخی',
    description: 'بین ۲ تا ۱۰ آزمایش سازگار را با یک معیار یکسان رتبه‌بندی کنید.',
    historicalOnly: 'این رتبه‌بندی فقط براساس داده تاریخی است.',
    selectExperiment: 'انتخاب برای مقایسه',
    incompatibleExperiment: 'Dataset یا Horizon این آزمایش با انتخاب فعلی سازگار نیست.',
    limitReached: 'حداکثر ۱۰ آزمایش قابل مقایسه است.',
    selectedCount: 'آزمایش انتخاب‌شده',
    selectionHint:
      'پس از انتخاب اولین آزمایش، فقط آزمایش‌های دارای Dataset و Horizon یکسان فعال می‌مانند.',
    clearSelection: 'پاک‌کردن انتخاب‌ها',
    metricLabel: 'معیار مقایسه',
    compare: 'اجرای مقایسه تاریخی',
    comparing: 'در حال مقایسه',
    insufficientSelection: 'برای اجرای مقایسه حداقل دو آزمایش انتخاب کنید.',
    error: 'مقایسه انجام نشد. سازگاری آزمایش‌ها و اتصال Backend را بررسی کنید.',
    retry: 'تلاش مجدد',
    resultTitle: 'رتبه‌بندی تاریخی',
    resultDescription:
      'رتبه اول فقط بهترین نتیجه تاریخی در معیار انتخاب‌شده است و پیشنهاد معامله محسوب نمی‌شود.',
    firstHistoricalRank: 'رتبه اول تاریخی',
    fields: {
      position: 'رتبه',
      experiment: 'Experiment',
      strategy: 'Strategy',
      parameters: 'پارامترها',
      metricValue: 'مقدار معیار',
    },
    metrics: {
      excess_return: 'بازده مازاد',
      total_return: 'بازده کل',
      max_drawdown_fraction: 'حداکثر افت سرمایه',
    },
    rankingDirections: {
      higher_is_better: 'مقدار بیشتر در رتبه بالاتر',
      lower_is_better: 'مقدار کمتر در رتبه بالاتر',
    },
  },
  en: {
    title: 'Historical experiment comparison',
    description: 'Rank between 2 and 10 compatible experiments using one consistent metric.',
    historicalOnly: 'This ranking only uses historical results.',
    selectExperiment: 'Select for comparison',
    incompatibleExperiment: 'This experiment has a different dataset or evaluation horizon.',
    limitReached: 'At most 10 experiments can be compared.',
    selectedCount: 'Selected experiments',
    selectionHint:
      'After the first selection, only experiments with the same dataset and horizon remain enabled.',
    clearSelection: 'Clear selection',
    metricLabel: 'Comparison metric',
    compare: 'Run historical comparison',
    comparing: 'Comparing',
    insufficientSelection: 'Select at least two experiments to run a comparison.',
    error: 'Comparison failed. Check experiment compatibility and the backend connection.',
    retry: 'Try again',
    resultTitle: 'Historical ranking',
    resultDescription:
      'The first position only represents the highest historical rank for the selected metric and is not a trade recommendation.',
    firstHistoricalRank: 'First historical rank',
    fields: {
      position: 'Position',
      experiment: 'Experiment',
      strategy: 'Strategy',
      parameters: 'Parameters',
      metricValue: 'Metric value',
    },
    metrics: {
      excess_return: 'Excess return',
      total_return: 'Total return',
      max_drawdown_fraction: 'Maximum drawdown',
    },
    rankingDirections: {
      higher_is_better: 'Higher values rank first',
      lower_is_better: 'Lower values rank first',
    },
  },
};

export function getExperimentComparisonCopy(locale: DashboardLocale): ExperimentComparisonCopy {
  return copies[locale];
}
