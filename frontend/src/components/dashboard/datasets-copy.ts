import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type DatasetsCopy = {
  eyebrow: string;
  title: string;
  description: string;
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
    source: string;
    sourcePlaceholder: string;
    baseAsset: string;
    baseAssetPlaceholder: string;
    quoteAsset: string;
    quoteAssetPlaceholder: string;
    timeframe: string;
    allTimeframes: string;
    createdFrom: string;
    createdTo: string;
    sortBy: string;
    sortDirection: string;
    apply: string;
    applying: string;
    reset: string;
    sortFields: {
      createdAt: string;
      startTime: string;
      candleCount: string;
    };
    directions: {
      ascending: string;
      descending: string;
    };
  };
  fields: {
    pair: string;
    marketType: string;
    timeframe: string;
    candles: string;
    source: string;
    period: string;
    createdAt: string;
    checksum: string;
  };
};

const copies: Record<DashboardLocale, DatasetsCopy> = {
  fa: {
    eyebrow: 'Historical data catalog',
    title: 'مجموعه‌داده‌ها',
    description:
      'Snapshotهای تغییرناپذیر داده تاریخی که برای آزمایش‌ها و ارزیابی‌های Walk-forward استفاده می‌شوند.',
    total: 'تعداد نتایج',
    loading: 'در حال دریافت مجموعه‌داده‌ها',
    emptyTitle: 'مجموعه‌داده‌ای پیدا نشد',
    emptyDescription: 'هیچ مجموعه‌داده‌ای با فیلترهای فعلی مطابقت ندارد.',
    errorTitle: 'دریافت مجموعه‌داده‌ها ناموفق بود',
    errorDescription: 'فیلترها و اتصال Backend را بررسی کرده و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    previous: 'قبلی',
    next: 'بعدی',
    page: 'صفحه',
    viewDetails: 'مشاهده جزئیات',
    filters: {
      title: 'فیلتر و مرتب‌سازی',
      description:
        'فهرست داده‌های تاریخی را بر اساس منبع، دارایی، تایم‌فریم و زمان ایجاد محدود کنید.',
      source: 'منبع',
      sourcePlaceholder: 'مثلاً test-exchange',
      baseAsset: 'دارایی پایه',
      baseAssetPlaceholder: 'BTC',
      quoteAsset: 'دارایی مقابل',
      quoteAssetPlaceholder: 'USDT',
      timeframe: 'تایم‌فریم',
      allTimeframes: 'همه تایم‌فریم‌ها',
      createdFrom: 'ایجادشده از',
      createdTo: 'ایجادشده تا',
      sortBy: 'مرتب‌سازی بر اساس',
      sortDirection: 'جهت مرتب‌سازی',
      apply: 'اعمال فیلترها',
      applying: 'در حال اعمال',
      reset: 'پاک‌کردن فیلترها',
      sortFields: {
        createdAt: 'زمان ایجاد',
        startTime: 'شروع داده',
        candleCount: 'تعداد کندل',
      },
      directions: {
        ascending: 'صعودی',
        descending: 'نزولی',
      },
    },
    fields: {
      pair: 'جفت معاملاتی',
      marketType: 'نوع بازار',
      timeframe: 'تایم‌فریم',
      candles: 'تعداد کندل',
      source: 'منبع',
      period: 'بازه داده',
      createdAt: 'زمان ایجاد',
      checksum: 'Checksum',
    },
  },
  en: {
    eyebrow: 'Historical data catalog',
    title: 'Datasets',
    description:
      'Immutable historical data snapshots used by experiments and walk-forward evaluations.',
    total: 'Results',
    loading: 'Loading datasets',
    emptyTitle: 'No datasets found',
    emptyDescription: 'No historical dataset matches the currently applied filters.',
    errorTitle: 'Unable to retrieve datasets',
    errorDescription: 'Check the filters and backend connection, then try again.',
    retry: 'Try again',
    previous: 'Previous',
    next: 'Next',
    page: 'Page',
    viewDetails: 'View details',
    filters: {
      title: 'Filter and sort',
      description: 'Narrow historical data by source, asset, timeframe, and creation date.',
      source: 'Source',
      sourcePlaceholder: 'For example, test-exchange',
      baseAsset: 'Base asset',
      baseAssetPlaceholder: 'BTC',
      quoteAsset: 'Quote asset',
      quoteAssetPlaceholder: 'USDT',
      timeframe: 'Timeframe',
      allTimeframes: 'All timeframes',
      createdFrom: 'Created from',
      createdTo: 'Created to',
      sortBy: 'Sort by',
      sortDirection: 'Sort direction',
      apply: 'Apply filters',
      applying: 'Applying',
      reset: 'Reset filters',
      sortFields: {
        createdAt: 'Creation time',
        startTime: 'Data start time',
        candleCount: 'Candle count',
      },
      directions: {
        ascending: 'Ascending',
        descending: 'Descending',
      },
    },
    fields: {
      pair: 'Trading pair',
      marketType: 'Market type',
      timeframe: 'Timeframe',
      candles: 'Candles',
      source: 'Source',
      period: 'Data period',
      createdAt: 'Created at',
      checksum: 'Checksum',
    },
  },
};

export function getDatasetsCopy(locale: DashboardLocale): DatasetsCopy {
  return copies[locale];
}
