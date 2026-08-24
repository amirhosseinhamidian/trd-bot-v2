import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type WalkForwardCopy = {
  eyebrow: string;
  title: string;
  description: string;
  historicalOnly: string;
  total: string;
  loading: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  emptyTitle: string;
  emptyDescription: string;
  previous: string;
  next: string;
  page: string;
  viewDetails: string;
  filters: {
    title: string;
    description: string;
    datasetId: string;
    datasetIdPlaceholder: string;
    planId: string;
    planIdPlaceholder: string;
    strategyName: string;
    strategyNamePlaceholder: string;
    strategyVersion: string;
    strategyVersionPlaceholder: string;
    horizonCandles: string;
    createdFrom: string;
    createdTo: string;
    sortBy: string;
    sortDirection: string;
    apply: string;
    applying: string;
    reset: string;
    sortFields: {
      createdAt: string;
      horizonCandles: string;
    };
    directions: {
      ascending: string;
      descending: string;
    };
  };
  fields: {
    version: string;
    createdAt: string;
    datasetId: string;
    planId: string;
    horizon: string;
    totalFolds: string;
    totalSignals: string;
    foldsWithTrades: string;
    strategyWins: string;
    benchmarkWins: string;
    ties: string;
    strategyReturn: string;
    benchmarkReturn: string;
    excessReturn: string;
    worstDrawdown: string;
    mode: string;
    trainCandles: string;
    testCandles: string;
    stepCandles: string;
    gapCandles: string;
    parameters: string;
  };
  modes: {
    rolling: string;
    expanding: string;
  };
};

const copies: Record<DashboardLocale, WalkForwardCopy> = {
  fa: {
    eyebrow: 'Out-of-sample historical validation',
    title: 'تحلیل Walk-forward',
    description: 'پایداری تاریخی استراتژی را در چند پنجره زمانی مستقل و خارج از نمونه بررسی کنید.',
    historicalOnly: 'فقط پژوهش تاریخی',
    total: 'تعداد اجراها',
    loading: 'در حال دریافت اجراهای Walk-forward',
    errorTitle: 'دریافت اجراها ناموفق بود',
    errorDescription: 'اتصال Backend را بررسی کرده و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    emptyTitle: 'اجرای Walk-forward پیدا نشد',
    emptyDescription: 'هنوز هیچ اجرای تاریخی Walk-forward ثبت نشده است.',
    previous: 'قبلی',
    next: 'بعدی',
    page: 'صفحه',
    viewDetails: 'مشاهده گزارش پایداری',
    filters: {
      title: 'فیلتر و مرتب‌سازی',
      description:
        'اجراهای Walk-forward را براساس Dataset، Plan، Strategy و زمان ایجاد محدود کنید.',
      datasetId: 'شناسه Dataset',
      datasetIdPlaceholder: 'dataset-...',
      planId: 'شناسه Plan',
      planIdPlaceholder: 'walk-forward-...',
      strategyName: 'نام Strategy',
      strategyNamePlaceholder: 'ema-crossover',
      strategyVersion: 'نسخه Strategy',
      strategyVersionPlaceholder: '1.0.0',
      horizonCandles: 'افق برحسب کندل',
      createdFrom: 'ایجادشده از',
      createdTo: 'ایجادشده تا',
      sortBy: 'مرتب‌سازی براساس',
      sortDirection: 'جهت مرتب‌سازی',
      apply: 'اعمال فیلترها',
      applying: 'در حال اعمال',
      reset: 'پاک‌کردن فیلترها',
      sortFields: {
        createdAt: 'زمان ایجاد',
        horizonCandles: 'افق ارزیابی',
      },
      directions: {
        ascending: 'صعودی',
        descending: 'نزولی',
      },
    },
    fields: {
      version: 'نسخه',
      createdAt: 'زمان ایجاد',
      datasetId: 'شناسه Dataset',
      planId: 'شناسه Plan',
      horizon: 'افق ارزیابی',
      totalFolds: 'تعداد Fold',
      totalSignals: 'تعداد سیگنال‌ها',
      foldsWithTrades: 'Fold دارای معامله شبیه‌سازی‌شده',
      strategyWins: 'برتری Strategy',
      benchmarkWins: 'برتری Benchmark',
      ties: 'نتیجه برابر',
      strategyReturn: 'میانگین بازده Strategy',
      benchmarkReturn: 'میانگین بازده Benchmark',
      excessReturn: 'میانگین بازده مازاد',
      worstDrawdown: 'بدترین افت سرمایه',
      mode: 'نوع پنجره',
      trainCandles: 'کندل‌های Train',
      testCandles: 'کندل‌های Test',
      stepCandles: 'فاصله حرکت',
      gapCandles: 'فاصله Train و Test',
      parameters: 'پارامترهای Strategy',
    },
    modes: {
      rolling: 'غلتان',
      expanding: 'گسترش‌یابنده',
    },
  },
  en: {
    eyebrow: 'Out-of-sample historical validation',
    title: 'Walk-forward analysis',
    description:
      'Review historical strategy stability across multiple independent out-of-sample windows.',
    historicalOnly: 'Historical research only',
    total: 'Runs',
    loading: 'Loading walk-forward runs',
    errorTitle: 'Unable to retrieve runs',
    errorDescription: 'Check the backend connection and try again.',
    retry: 'Try again',
    emptyTitle: 'No walk-forward run found',
    emptyDescription: 'No historical walk-forward execution has been stored yet.',
    previous: 'Previous',
    next: 'Next',
    page: 'Page',
    viewDetails: 'View stability report',
    filters: {
      title: 'Filter and sort',
      description: 'Narrow walk-forward runs by dataset, plan, strategy, and creation time.',
      datasetId: 'Dataset ID',
      datasetIdPlaceholder: 'dataset-...',
      planId: 'Plan ID',
      planIdPlaceholder: 'walk-forward-...',
      strategyName: 'Strategy name',
      strategyNamePlaceholder: 'ema-crossover',
      strategyVersion: 'Strategy version',
      strategyVersionPlaceholder: '1.0.0',
      horizonCandles: 'Horizon candles',
      createdFrom: 'Created from',
      createdTo: 'Created to',
      sortBy: 'Sort by',
      sortDirection: 'Sort direction',
      apply: 'Apply filters',
      applying: 'Applying',
      reset: 'Reset filters',
      sortFields: {
        createdAt: 'Creation time',
        horizonCandles: 'Evaluation horizon',
      },
      directions: {
        ascending: 'Ascending',
        descending: 'Descending',
      },
    },
    fields: {
      version: 'Version',
      createdAt: 'Created at',
      datasetId: 'Dataset ID',
      planId: 'Plan ID',
      horizon: 'Evaluation horizon',
      totalFolds: 'Total folds',
      totalSignals: 'Total signals',
      foldsWithTrades: 'Folds with simulated trades',
      strategyWins: 'Strategy wins',
      benchmarkWins: 'Benchmark wins',
      ties: 'Ties',
      strategyReturn: 'Average strategy return',
      benchmarkReturn: 'Average benchmark return',
      excessReturn: 'Average excess return',
      worstDrawdown: 'Worst drawdown',
      mode: 'Window mode',
      trainCandles: 'Train candles',
      testCandles: 'Test candles',
      stepCandles: 'Step candles',
      gapCandles: 'Gap candles',
      parameters: 'Strategy parameters',
    },
    modes: {
      rolling: 'Rolling',
      expanding: 'Expanding',
    },
  },
};

export function getWalkForwardCopy(locale: DashboardLocale): WalkForwardCopy {
  return copies[locale];
}
