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
    total: 'تعداد کل مجموعه‌داده‌ها',
    loading: 'در حال دریافت مجموعه‌داده‌ها',
    emptyTitle: 'مجموعه‌داده‌ای وجود ندارد',
    emptyDescription:
      'پس از ایجاد اولین Snapshot داده تاریخی، اطلاعات آن در این صفحه نمایش داده می‌شود.',
    errorTitle: 'دریافت مجموعه‌داده‌ها ناموفق بود',
    errorDescription: 'اتصال Backend را بررسی کرده و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    previous: 'قبلی',
    next: 'بعدی',
    page: 'صفحه',
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
    total: 'Total datasets',
    loading: 'Loading datasets',
    emptyTitle: 'No datasets available',
    emptyDescription: 'The first historical data snapshot will appear here after it is created.',
    errorTitle: 'Unable to retrieve datasets',
    errorDescription: 'Check the backend connection and try again.',
    retry: 'Try again',
    previous: 'Previous',
    next: 'Next',
    page: 'Page',
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
