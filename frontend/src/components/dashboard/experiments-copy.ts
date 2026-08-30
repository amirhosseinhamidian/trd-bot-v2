import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type ExperimentsCopy = {
  eyebrow: string;
  title: string;
  description: string;
  historicalOnly: string;
  total: string;
  loading: string;
  emptyTitle: string;
  emptyDescription: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  previous: string;
  next: string;
  page: string;
  viewDetails: string;
  filters: {
    title: string;
    description: string;
    datasetId: string;
    datasetIdPlaceholder: string;
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
    datasetId: string;
    createdAt: string;
    strategyVersion: string;
    horizonCandles: string;
    generatedSignals: string;
    totalTrades: string;
    totalReturn: string;
    benchmarkReturn: string;
    excessReturn: string;
    winRate: string;
    maxDrawdown: string;
    profitFactor: string;
    parameters: string;
  };
  outcomes: {
    strategy: string;
    benchmark: string;
    tie: string;
  };
};

const copies: Record<DashboardLocale, ExperimentsCopy> = {
  fa: {
    eyebrow: 'Historical strategy research',
    title: 'آزمایش‌ها',
    description:
      'نتایج تاریخی استراتژی‌ها، هزینه‌های شبیه‌سازی‌شده و مقایسه با Benchmark را بررسی کنید.',
    historicalOnly: 'فقط پژوهش تاریخی',
    total: 'تعداد نتایج',
    loading: 'در حال دریافت آزمایش‌ها',
    emptyTitle: 'آزمایشی پیدا نشد',
    emptyDescription: 'هیچ آزمایش تاریخی با فیلترهای فعلی مطابقت ندارد.',
    errorTitle: 'دریافت آزمایش‌ها ناموفق بود',
    errorDescription: 'فیلترها و اتصال Backend را بررسی کرده و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    previous: 'قبلی',
    next: 'بعدی',
    page: 'صفحه',
    viewDetails: 'مشاهده جزئیات',
    filters: {
      title: 'فیلتر و مرتب‌سازی',
      description: 'آزمایش‌های ذخیره‌شده را بر اساس Dataset، Strategy و زمان ایجاد محدود کنید.',
      datasetId: 'شناسه Dataset',
      datasetIdPlaceholder: 'dataset-...',
      strategyName: 'نام Strategy',
      strategyNamePlaceholder: 'ema-crossover / rsi-threshold',
      strategyVersion: 'نسخه Strategy',
      strategyVersionPlaceholder: '1.0.0',
      horizonCandles: 'افق بر حسب کندل',
      createdFrom: 'ایجادشده از',
      createdTo: 'ایجادشده تا',
      sortBy: 'مرتب‌سازی بر اساس',
      sortDirection: 'جهت مرتب‌سازی',
      apply: 'اعمال فیلترها',
      applying: 'در حال اعمال',
      reset: 'پاک‌کردن فیلترها',
      sortFields: {
        createdAt: 'زمان ایجاد',
        horizonCandles: 'افق کندل',
      },
      directions: {
        ascending: 'صعودی',
        descending: 'نزولی',
      },
    },
    fields: {
      datasetId: 'Dataset',
      createdAt: 'زمان ایجاد',
      strategyVersion: 'نسخه',
      horizonCandles: 'افق کندل',
      generatedSignals: 'سیگنال‌های تولیدشده',
      totalTrades: 'معاملات شبیه‌سازی‌شده',
      totalReturn: 'بازده تاریخی Strategy',
      benchmarkReturn: 'بازده تاریخی Benchmark',
      excessReturn: 'بازده مازاد تاریخی',
      winRate: 'نرخ موفقیت تاریخی',
      maxDrawdown: 'حداکثر افت تاریخی',
      profitFactor: 'Profit factor',
      parameters: 'پارامترها',
    },
    outcomes: {
      strategy: 'Strategy بهتر بوده',
      benchmark: 'Benchmark بهتر بوده',
      tie: 'نتیجه برابر',
    },
  },
  en: {
    eyebrow: 'Historical strategy research',
    title: 'Experiments',
    description: 'Review historical strategy results, simulated costs, and benchmark comparisons.',
    historicalOnly: 'Historical research only',
    total: 'Results',
    loading: 'Loading experiments',
    emptyTitle: 'No experiments found',
    emptyDescription: 'No historical experiment matches the currently applied filters.',
    errorTitle: 'Unable to retrieve experiments',
    errorDescription: 'Check the filters and backend connection, then try again.',
    retry: 'Try again',
    previous: 'Previous',
    next: 'Next',
    page: 'Page',
    viewDetails: 'View details',
    filters: {
      title: 'Filter and sort',
      description: 'Narrow stored experiments by dataset, strategy, and creation time.',
      datasetId: 'Dataset ID',
      datasetIdPlaceholder: 'dataset-...',
      strategyName: 'Strategy name',
      strategyNamePlaceholder: 'ema-crossover / rsi-threshold',
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
        horizonCandles: 'Horizon candles',
      },
      directions: {
        ascending: 'Ascending',
        descending: 'Descending',
      },
    },
    fields: {
      datasetId: 'Dataset',
      createdAt: 'Created at',
      strategyVersion: 'Version',
      horizonCandles: 'Horizon candles',
      generatedSignals: 'Generated signals',
      totalTrades: 'Simulated trades',
      totalReturn: 'Historical strategy return',
      benchmarkReturn: 'Historical benchmark return',
      excessReturn: 'Historical excess return',
      winRate: 'Historical win rate',
      maxDrawdown: 'Historical max drawdown',
      profitFactor: 'Profit factor',
      parameters: 'Parameters',
    },
    outcomes: {
      strategy: 'Strategy performed better',
      benchmark: 'Benchmark performed better',
      tie: 'Tie',
    },
  },
};

export function getExperimentsCopy(locale: DashboardLocale): ExperimentsCopy {
  return copies[locale];
}
